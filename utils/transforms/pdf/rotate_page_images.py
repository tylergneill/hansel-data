#!/usr/bin/env python3
"""
rotate_page_images.py — rotate the pixels of pages' embedded images
===================================================================
Distinct from `qpdf --rotate` (and from rotate-images.sh next to this
file), which sets a page's /Rotate attribute and leaves the stored image
untouched.

Some scanners store an image sideways and compensate with a rotation
matrix in the content stream. The page then *renders* upright while the
bytes on disk are rotated 90 degrees. Tools that read the embedded image
directly rather than rendering the page see the sideways version and
misbehave — e.g. a two-page spread whose stored image is portrait gets
misclassified as a single page and passed through unsplit.

This script rewrites the pixels so stored orientation matches displayed
orientation, leaving nothing for downstream tools to compensate for.

Pages you do not name are copied through untouched, with no decode and no
re-encode, so they take zero additional generation loss. Named pages must
be re-encoded, since rotation is a pixel operation; JPEGs are written back
with the source's own quantization tables and chroma subsampling, so
quality matches the original rather than approximating it with a quality
number.

Correcting automatically: --auto
--------------------------------
--auto finds the pages that need rotating and rotates each by the angle
that cancels its placement, so you never have to hunt for them:

    python rotate_page_images.py scan.pdf --auto

This is not a heuristic about page content. Each page's content stream
records the rotation the PDF applies when drawing its image, and --auto
corrects exactly those pages where that rotation is non-zero — the pages
whose stored bytes disagree with how the page displays. Pages that already
agree are left alone, so running it on a clean file does nothing. It is
therefore safe to run over a whole batch.

Aspect ratio is never consulted, so a genuinely portrait page (a
single-page scan among spreads) is not touched: what matters is whether
stored and displayed orientation disagree, not what shape the page is.

Pages whose placement can't be read — several images on a page, or a
skewed matrix — are reported to stderr and skipped rather than guessed at.

Which way to rotate, by hand
----------------------------
Name pages explicitly to rotate them regardless of placement, e.g. for a
scan that is uniformly sideways with no matrix to detect. --angle is the
rotation applied to the stored pixels, counter-clockwise positive
(matching Pillow and qpdf's sign convention):

    -90   clockwise (the default)
     90   counter-clockwise
    180   upside down

--inspect reports each page's stored size, aspect ratio, and whether the
content stream applies a rotation matrix, without writing anything. Use it
to see what --auto would do before doing it, or to confirm a rotation
landed the way you meant:

    python rotate_page_images.py scan.pdf --inspect

--dry-run prints the pages and angles either mode would apply, then exits
without writing.

Usage
-----
    python rotate_page_images.py INPUT --auto [-o OUT]
    python rotate_page_images.py INPUT PAGES [--angle DEG] [-o OUT]
    python rotate_page_images.py INPUT --inspect

PAGES selects which pages to rotate (1-indexed, in the input's numbering):

    19          a single page
    3,19,42     a list
    5-9         a range
    5-z         page 5 through the end
    z | all     every page

Examples
--------
    python rotate_page_images.py scan.pdf --auto           # fix every rotated page
    python rotate_page_images.py scan.pdf --auto --dry-run # ...preview it first
    python rotate_page_images.py scan.pdf 19               # page 19, clockwise
    python rotate_page_images.py scan.pdf 19 --angle 90    # counter-clockwise
    python rotate_page_images.py scan.pdf 3,19 -o fixed.pdf
    python rotate_page_images.py scan.pdf z --angle 180

Writing happens in place only when you pass no -o, and never before the
whole document has been rebuilt successfully — the input is replaced via
an atomic swap, so an error partway through leaves the original intact.

Dependencies:
  pip install pymupdf pillow
"""

import argparse
import io
import os
import sys
from pathlib import Path

import pymupdf
from PIL import Image, JpegImagePlugin

# A content-stream matrix (a, b, c, d, e, f) places the image on the page.
# An upright placement has b and c at zero; a 90-degree one has a and d at
# zero instead. Compare against a tolerance rather than exact zero, since
# these are floats carrying scan-derived scale factors.
MATRIX_TOL = 1e-6


def parse_pages(spec: str, n_pages: int) -> list[int]:
    """
    Parse a page spec into a sorted list of 1-indexed page numbers:
    '19', '3,19,42', '5-9', '5-z', or 'z'/'all' for the whole document.
    Ranges are inclusive and accept their endpoints in either order.
    """
    spec = spec.strip().lower()
    if spec in ("z", "all"):
        return list(range(1, n_pages + 1))

    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part.lstrip("-"):
            a, _, b = part.partition("-")
            a, b = a.strip(), b.strip()
            try:
                start = 1 if a in ("", "z") else int(a)
                end = n_pages if b in ("", "z") else int(b)
            except ValueError:
                raise SystemExit(f"bad page range {part!r}")
            if start > end:
                start, end = end, start
            pages.extend(range(start, end + 1))
        else:
            try:
                pages.append(int(part))
            except ValueError:
                raise SystemExit(f"bad page number {part!r}")

    if not pages:
        raise SystemExit(f"no pages selected by {spec!r}")

    bad = sorted({p for p in pages if not 1 <= p <= n_pages})
    if bad:
        raise SystemExit(
            f"page(s) {', '.join(map(str, bad))} out of range — "
            f"document has {n_pages} pages"
        )
    return sorted(set(pages))


def placement_rotation(page: pymupdf.Page) -> int | None:
    """
    Report the rotation the content stream applies to the page's image, in
    degrees counter-clockwise (0, 90, 180 or 270), or None if the page has
    no single image or an unrecognized placement.

    A page whose stored image is sideways compensates here, so a non-zero
    value is the signal that stored and displayed orientation disagree.
    """
    infos = page.get_image_info(xrefs=True)
    if len(infos) != 1:
        return None
    a, b, c, d = infos[0]["transform"][:4]

    upright = abs(b) < MATRIX_TOL and abs(c) < MATRIX_TOL
    quarter = abs(a) < MATRIX_TOL and abs(d) < MATRIX_TOL

    if upright:
        return 180 if (a < 0 and d < 0) else 0
    if quarter:
        return 90 if b > 0 else 270
    return None


def read_image(doc: pymupdf.Document, page: pymupdf.Page,
               page_num: int) -> tuple[bytes, str, tuple[int, int]]:
    """Return the page's single embedded image as (raw bytes, ext, size)."""
    images = page.get_images(full=True)
    if len(images) != 1:
        raise SystemExit(
            f"page {page_num}: expected exactly 1 embedded image, "
            f"found {len(images)} — this script only handles scans with one "
            f"image per page"
        )
    extracted = doc.extract_image(images[0][0])
    with Image.open(io.BytesIO(extracted["image"])) as probe:
        size = probe.size
    return extracted["image"], extracted["ext"], size


def rotate_bytes(raw: bytes, ext: str, angle: int) -> tuple[bytes, tuple[int, int]]:
    """
    Rotate raw encoded image bytes, returning re-encoded bytes and the new
    size. JPEGs are written back with the source's own quantization tables
    and chroma subsampling so the rotation does not re-quantize to a
    different quality; anything Pillow cannot write back in its original
    format falls back to lossless PNG rather than silently degrading.
    """
    img = Image.open(io.BytesIO(raw))
    img.load()
    fmt = img.format or ext.upper()

    kwargs: dict = {}
    if fmt == "JPEG":
        qtables = getattr(img, "quantization", None)
        if qtables:
            kwargs["qtables"] = qtables
            kwargs["subsampling"] = JpegImagePlugin.get_sampling(img)

    rotated = img.rotate(angle, expand=True)

    buf = io.BytesIO()
    try:
        rotated.save(buf, fmt, **kwargs)
    except (OSError, ValueError):
        buf = io.BytesIO()
        rotated.save(buf, "PNG")
    return buf.getvalue(), rotated.size


# The rotation that cancels a given content-stream placement, bringing the
# stored pixels into agreement with how the page displays. A placement of 90
# degrees counter-clockwise is undone by rotating the pixels 90 clockwise,
# and vice versa; 180 is its own inverse.
CORRECTION = {90: -90, 270: 90, 180: 180}


def survey(doc: pymupdf.Document) -> list[dict]:
    """
    Examine every page once, returning a row per page describing its stored
    image, the rotation its content stream applies, and the rotation needed
    to bring the two into agreement (None when nothing is needed).

    Both --inspect and --auto read this, so what the report shows and what
    the correction does can never drift apart.
    """
    rows: list[dict] = []
    for i in range(len(doc)):
        page = doc[i]
        row: dict = {"page": i + 1, "size": None, "placement": None,
                     "correction": None, "problem": None}
        try:
            _, _, row["size"] = read_image(doc, page, i + 1)
        except SystemExit as exc:
            row["problem"] = str(exc)
            rows.append(row)
            continue

        rot = placement_rotation(page)
        row["placement"] = rot
        if rot is None:
            row["problem"] = "unrecognized image placement"
        else:
            row["correction"] = CORRECTION.get(rot)
        rows.append(row)
    return rows


def inspect(rows: list[dict]) -> None:
    """
    Print each page's stored image orientation alongside the rotation its
    content stream applies, flagging pages where the two disagree.
    """
    print(f"{'page':>5}  {'stored':>11}  {'ratio':>6}  {'placement':>9}  note")
    for row in rows:
        if row["size"] is None:
            print(f"{row['page']:>5}  {'—':>11}  {'—':>6}  {'—':>9}  "
                  f"{row['problem']}")
            continue
        w, h = row["size"]
        rot = row["placement"]
        rot_label = "?" if rot is None else f"{rot}°"
        if row["correction"] is not None:
            note = f"stored rotated — fix with --angle {row['correction']}"
        elif row["problem"]:
            note = row["problem"]
        else:
            note = ""
        print(f"{row['page']:>5}  {w:>5}x{h:<5}  {w/h:>6.3f}  "
              f"{rot_label:>9}  {note}")

    needed = [r for r in rows if r["correction"] is not None]
    unknown = [r for r in rows if r["correction"] is None and r["problem"]]
    print()
    if needed:
        pages = ",".join(str(r["page"]) for r in needed)
        print(f"{len(needed)} page(s) stored rotated relative to how they "
              f"display: {pages}")
        print("Correct them all with --auto.")
    else:
        print("No pages stored rotated.")
    if unknown:
        pages = ",".join(str(r["page"]) for r in unknown)
        print(f"{len(unknown)} page(s) could not be assessed: {pages}")


def process(input_path: Path, output_path: Path | None,
            plan: dict[int, int]) -> None:
    """
    Rebuild the document, rotating each page named in `plan` by its own
    angle and copying every other page's image through without touching
    its bytes.
    """
    doc = pymupdf.open(str(input_path))
    out = pymupdf.open()

    for i in range(len(doc)):
        page = doc[i]
        page_num = i + 1
        raw, ext, size = read_image(doc, page, page_num)

        angle = plan.get(page_num)
        if angle is not None:
            before = size
            raw, size = rotate_bytes(raw, ext, angle)
            print(f"  page {page_num}: {before[0]}x{before[1]} -> "
                  f"{size[0]}x{size[1]} ({angle:+d}°)")

        w, h = size
        new_page = out.new_page(width=w, height=h)
        new_page.insert_image(new_page.rect, stream=raw)

    doc.close()

    # Write to a temporary file first, then swap, so a failure partway
    # through can never leave a half-written PDF where the input was.
    dest = output_path or input_path
    tmp = dest.with_name(dest.name + ".tmp")
    out.save(str(tmp))
    out.close()
    os.replace(tmp, dest)

    verb = "Rewrote" if output_path is None else "Wrote"
    print(f"{verb} {dest} — rotated {len(plan)} page(s).")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Rotate the pixels of pages' embedded images in a PDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("input", type=Path, help="PDF to read.")
    p.add_argument("pages", nargs="?", default=None,
                   help="Pages to rotate: '19', '3,19', '5-9', '5-z', or 'z' "
                        "for all. Omit with --auto or --inspect.")
    p.add_argument("--auto", action="store_true",
                   help="Rotate exactly those pages whose stored image "
                        "disagrees with the rotation their content stream "
                        "applies, each by the angle that cancels it. Reads "
                        "the placement matrix, so it corrects only real "
                        "disagreements. Cannot be combined with a page spec "
                        "or --angle.")
    p.add_argument("--angle", type=int, default=-90, choices=(-90, 90, 180),
                   metavar="DEG",
                   help="Rotation applied to the stored pixels, "
                        "counter-clockwise positive: -90 (clockwise, the "
                        "default), 90 (counter-clockwise), or 180. Ignored "
                        "under --auto, which derives each page's angle.")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Write here instead of replacing the input in place.")
    p.add_argument("--inspect", action="store_true",
                   help="Report each page's stored orientation and the "
                        "rotation its content stream applies, then exit "
                        "without writing anything.")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the pages that would be rotated and the angle "
                        "each would get, then exit without writing.")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise SystemExit(f"no such file: {args.input}")

    # --angle is meaningless under --auto, which derives a per-page angle.
    # Catch it explicitly rather than silently ignoring what was asked for.
    angle_given = "--angle" in sys.argv
    if args.auto and (args.pages is not None or angle_given):
        raise SystemExit(
            "--auto derives both the pages and each page's angle; "
            "drop the page spec and --angle, or drop --auto"
        )

    doc = pymupdf.open(str(args.input))
    n_pages = len(doc)
    print(f"{args.input} ({n_pages} pages)")

    if args.inspect:
        print()
        inspect(survey(doc))
        doc.close()
        return

    if args.auto:
        rows = survey(doc)
        doc.close()
        plan = {r["page"]: r["correction"]
                for r in rows if r["correction"] is not None}
        skipped = [r for r in rows if r["correction"] is None and r["problem"]]
        for r in skipped:
            print(f"  page {r['page']}: skipped — {r['problem']}", file=sys.stderr)
        if not plan:
            print("No pages stored rotated; nothing to do.")
            return
        pages = ",".join(str(p) for p in sorted(plan))
        print(f"Auto-detected {len(plan)} page(s) to correct: {pages}")
    else:
        if args.pages is None:
            doc.close()
            raise SystemExit(
                "which pages? pass a page spec (e.g. 19, 3-7, z), --auto to "
                "correct every rotated page, or --inspect to see what needs "
                "rotating"
            )
        targets = parse_pages(args.pages, n_pages)
        doc.close()
        plan = {p: args.angle for p in targets}

    if args.dry_run:
        for page_num, angle in sorted(plan.items()):
            print(f"  page {page_num}: would rotate {angle:+d}°")
        print(f"Dry run — nothing written ({len(plan)} page(s) would change).")
        return

    process(args.input, args.output, plan)


if __name__ == "__main__":
    sys.exit(main())
