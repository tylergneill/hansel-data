#!/usr/bin/env python3
"""
split_spreads.py — split assembled two-page spreads into individual half-pages
==============================================================================
Takes the single already-assembled `scan_composite.pdf` (each page is a
two-page spread, left + right book side, already upright — no rotation
needed) and splits every spread into two individual page images, then
reassembles them into one output PDF with roughly twice the page count.

Each page is rendered via PyMuPDF at its native resolution (matching the
embedded image's own pixel dimensions, not an arbitrary fixed DPI), so
the split halves are pixel-for-pixel the same data as the original, just
cut in half.

A small number of pages (<5) in the source are already single pages
(portrait aspect ratio) rather than spreads — e.g. trailing
corrigenda/appendix pages scanned individually. These are detected
automatically by aspect ratio and passed through unsplit.

Where to cut: --detect or --fixed
---------------------------------
Every spread needs a cut position, and there are two ways to get one.
Exactly one of these is required:

  --detect
      Search each spread independently for the darkest vertical column
      (the binding shadow) and cut there. Use when the gutter drifts
      spread to spread, which is the usual case for a hand-scanned book.

  --fixed FRAC
      Cut every spread at the same fraction of width, e.g. --fixed
      0.5173, skipping the search entirely. Use when the dark-band
      assumption doesn't hold for a book but the scan is well-registered
      — read a good starting value off any debug image's red-line label.

Neither is expected to be right on every page. Both feed the same
review-and-correct loop below, so the choice is just which baseline
leaves you the fewest pages to fix by hand.

    python split_spreads.py -i scan_composite.pdf --detect
    python split_spreads.py -i scan_composite.pdf --fixed 0.5173
    python split_spreads.py -i scan_composite.pdf --fixed 0.5173 --only-page 204

Everything is written to tmp/ next to this script (gitignored): the
split PDF to tmp/out.pdf, debug images and the correction manifest to
tmp/debug/. Those paths hold no matter which directory you run from.
Override with -o/--debug-dir, or pass --no-debug to skip debug output.

--only-page writes to tmp/out_only_page.pdf instead, so iterating on a
single spread never overwrites the full book from an earlier run.

Reviewing the cuts
------------------
Every run saves an annotated copy of each split spread to the debug
directory, named debug_NNN.jpg by source page number.

  Red (solid) is the cut position the mode produced for that page: the
  detected column under --detect, or the fixed fraction under --fixed.

  Blue (solid) is the cut actually taken, drawn only when an override
  from overrides.csv shifted it off the red line, and labelled with the
  shift. With no override the two coincide and only red is drawn, so a
  lone red line always means "this is where the page was cut".

Flip through the debug images to spot cuts that landed in text instead
of the binding shadow, and correct those pages in overrides.csv.

Debug images are keyed by source page number alone, so a later
--only-page run overwrites the image for the page it touches. The debug
file for a page therefore always reflects the most recent run over that
page — note that tmp/out.pdf does not, since --only-page writes its PDF
elsewhere.

Per-page corrections: overrides.csv
-----------------------------------
Each run drops a blank manifest at overrides.csv in the debug directory,
pre-filled with one row per split page and no offsets, ready to edit. An
existing overrides.csv is never overwritten, so corrections survive
re-runs — delete it to regenerate a blank one.

The manifest is always read when present and always applied; there is no
flag to opt in. Record one `page,offset_px` row per bad page (page =
1-indexed source page number; offset_px = pixels to shift the cut, at
that page's native resolution, positive = right, negative = left):

    204,15
    186,-8
    133,

A blank offset (e.g. `133,`) records a page as reviewed with no
correction needed (offset 0) — distinct from a page simply absent from
the file (never reviewed).

Each offset is relative to that page's red line, i.e. to whatever the
current mode produced for it. Offsets are not tied to the mode that was
running when they were recorded, so switching between --detect and
--fixed reinterprets them against the new baseline.

Iterate on one page with --only-page, then re-check its debug image
before committing to a full re-run:

    python split_spreads.py -i scan_composite.pdf --fixed 0.5173 --only-page 204

Dependencies:
  pip install pymupdf pillow
"""

import argparse
import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


# Internal tuning constants. These are not CLI flags: they shape how
# --detect searches, and are not things a run is normally driven with.
DETECT_CENTER = 0.50    # Center of the search band, as a fraction of width,
                        # and the fallback when detection isn't confident.
SEARCH_WINDOW = 0.03    # Search +/- this fraction of width around DETECT_CENTER.
MIN_CONTRAST = 6        # Minimum brightness dip (0-255) below the search band's
                        # average before the darkest column is trusted as a real
                        # gutter. Guards against blank spreads, where some column
                        # is always "darkest" by a fraction of a gray level of
                        # scanner noise.
SPREAD_RATIO = 1.2      # width/height above this = spread (split); below = single.

# Interim encoding for the split halves. Pending a follow-up task to match
# the source's format/colorspace/compression instead of forcing grayscale
# JPEG — this script must never make pages harder to read, and file size is
# explicitly not its concern.
JPEG_QUALITY = 90

# Gitignored scratch space next to this script. All generated files land here,
# so the defaults work no matter which directory the script is invoked from.
TMP_DIR = Path(__file__).resolve().parent / "tmp"
DEFAULT_OUTPUT = TMP_DIR / "out.pdf"
# --only-page runs write elsewhere by default, so a one-page throwaway can
# never overwrite the full book's output from an earlier run.
DEFAULT_ONLY_PAGE_OUTPUT = TMP_DIR / "out_only_page.pdf"
DEFAULT_DEBUG_DIR = TMP_DIR / "debug"
MANIFEST_NAME = "overrides.csv"


def load_overrides(path: Path) -> dict[int, int]:
    """
    Parse the overrides manifest: one `page,offset_px` row per line (page =
    1-indexed source page number, offset_px = pixel shift to apply to that
    page's cut, positive = right, negative = left). offset_px may be left
    blank (e.g. `133,`) to record a page as reviewed with no correction
    needed (offset 0), distinct from a page simply absent from the file
    (never reviewed). Blank lines and # comments are skipped.
    """
    overrides: dict[int, int] = {}
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) != 2:
            raise ValueError(f"{path}:{lineno}: expected 'page,offset_px', got {line!r}")
        page_str, offset_str = (p.strip() for p in parts)
        offset_str = offset_str or "0"
        try:
            page, offset = int(page_str), int(offset_str)
        except ValueError:
            raise ValueError(f"{path}:{lineno}: expected two integers, got {line!r}")
        overrides[page] = offset
    return overrides


def find_gutter(img: Image.Image) -> float:
    """
    Find the gutter (binding shadow) as the darkest vertical column within
    +/- SEARCH_WINDOW of DETECT_CENTER. Falls back to DETECT_CENTER if the
    darkest column isn't meaningfully darker than the window average (e.g.
    a blank/near-blank spread with no real shadow to detect).
    """
    w, h = img.size
    x_start = max(0, round(w * (DETECT_CENTER - SEARCH_WINDOW)))
    x_end = min(w, round(w * (DETECT_CENTER + SEARCH_WINDOW)))

    gray = img.convert("L") if img.mode != "L" else img
    # Downsample rows for speed — the gutter runs the full height, so a
    # coarse vertical sample is enough to localize its x-position.
    sample_h = min(h, 400)
    strip = gray.crop((x_start, 0, x_end, h)).resize((x_end - x_start, sample_h))
    pixels = strip.load()

    col_means = []
    for x in range(x_end - x_start):
        total = sum(pixels[x, y] for y in range(sample_h))
        col_means.append((x_start + x, total / sample_h))

    darkest_x, darkest_mean = min(col_means, key=lambda t: t[1])
    window_avg = sum(m for _, m in col_means) / len(col_means)

    if window_avg - darkest_mean < MIN_CONTRAST:
        return DETECT_CENTER
    return darkest_x / w


def save_debug_image(img: Image.Image, mode_x: float, cut_x: float,
                      offset_px: int | None, page_num: int,
                      debug_dir: Path) -> None:
    """
    Save a copy of the spread annotated for visual review.

    Red (solid) is the cut position the mode produced for this page — the
    detected column under --detect, or the fixed fraction under --fixed.

    Blue (solid) is the cut actually taken, drawn only when an override
    shifted it off the mode's position. With no override the two coincide
    and only the red line is drawn, so a bare red line always means "this
    is where the page was cut".
    """
    annotated = img.convert("RGB")
    draw = ImageDraw.Draw(annotated)
    w, h = annotated.size

    mx = round(w * mode_x)
    draw.line([(mx, 0), (mx, h)], fill=(220, 30, 30), width=2)
    draw.text((mx + 6, 10), f"split {mode_x:.4f}", fill=(220, 30, 30))

    if abs(cut_x - mode_x) > 1e-9:
        cx = round(w * cut_x)
        draw.line([(cx, 0), (cx, h)], fill=(40, 130, 220), width=2)
        shift = f"{offset_px:+d}px" if offset_px is not None else ""
        draw.text((cx + 6, 28), f"cut {cut_x:.4f} {shift}".rstrip(),
                  fill=(40, 130, 220))

    debug_dir.mkdir(parents=True, exist_ok=True)
    annotated.save(debug_dir / f"debug_{page_num:03d}.jpg", "JPEG", quality=85)


def write_overrides_template(pages: list[int], debug_dir: Path) -> Path | None:
    """
    Write a blank overrides manifest alongside the debug images, one row per
    split page with an empty offset (reviewed-pending). Returns the path, or
    None if the file already exists — an existing manifest holds hand-entered
    corrections and is never overwritten.
    """
    path = debug_dir / MANIFEST_NAME
    if path.exists():
        return None

    lines = [
        "# Per-page cut corrections, applied automatically on every run.",
        "# Set offset_px on any page whose cut is wrong, then re-run.",
        "# offset_px = pixel shift at the page's native resolution,",
        "# relative to that page's red line in the debug image;",
        "# positive = right, negative = left. A blank offset means",
        "# reviewed, no correction needed.",
        "# page,offset_px",
    ]
    lines.extend(f"{page}," for page in pages)

    debug_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def split_spread(img: Image.Image, cut_x: float) -> tuple[Image.Image, Image.Image]:
    """Split a two-page spread into left and right halves."""
    w, h = img.size
    cut = round(w * cut_x)
    left = img.crop((0, 0, cut, h))
    right = img.crop((cut, 0, w, h))
    return left, right


def _jpeg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def native_scale(page: pymupdf.Page) -> float:
    """
    Scale factor to render the page at the native pixel resolution of its
    single embedded image, rather than an arbitrary fixed DPI.
    """
    images = page.get_images(full=True)
    if len(images) != 1:
        raise ValueError(f"expected exactly 1 embedded image, found {len(images)}")
    img_w = images[0][2]  # (xref, smask, width, height, ...)
    return img_w / page.rect.width


def process(input_path: Path, output_path: Path, fixed_x: float | None,
            debug_dir: Path | None = None, only_page: int | None = None,
            overrides: dict[int, int] | None = None) -> None:
    """
    Split every spread in the input. fixed_x is the --fixed fraction, or
    None to detect each spread's gutter independently (--detect).
    """
    doc = pymupdf.open(str(input_path))
    n_pages = len(doc)
    print(f"Input: {input_path} ({n_pages} pages)")

    out_doc = pymupdf.open()
    split_pages: list[int] = []
    n_single = 0

    page_range = range(n_pages) if only_page is None else [only_page - 1]

    for i in page_range:
        page = doc[i]
        scale = native_scale(page)
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, colorspace=pymupdf.csGRAY, alpha=False)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)

        ratio = pix.width / pix.height

        if ratio > SPREAD_RATIO:
            # The mode's cut for this page, before any per-page correction.
            mode_x = find_gutter(img) if fixed_x is None else fixed_x
            cut_x = mode_x
            offset_px = (overrides or {}).get(i + 1)
            if offset_px is not None:
                w = pix.width
                cut_x = min(max(cut_x * w + offset_px, 0), w) / w
            if debug_dir is not None:
                save_debug_image(img, mode_x, cut_x, offset_px, i + 1, debug_dir)
            left, right = split_spread(img, cut_x)
            halves_bytes = [_jpeg_bytes(left), _jpeg_bytes(right)]
            sizes = [left.size, right.size]
            split_pages.append(i + 1)
        else:
            halves_bytes = [_jpeg_bytes(img)]
            sizes = [img.size]
            n_single += 1
            print(f"  page {i+1}/{n_pages}: treated as single page "
                  f"(ratio {ratio:.3f} <= {SPREAD_RATIO})")

        for (hw, hh), jpeg_bytes in zip(sizes, halves_bytes):
            out_page = out_doc.new_page(width=hw, height=hh)
            out_page.insert_image(out_page.rect, stream=jpeg_bytes)

        if (i + 1) % 25 == 0 or (i + 1) == n_pages:
            print(f"  ...{i+1}/{n_pages} spreads processed, "
                  f"{out_doc.page_count} output pages so far")

    doc.close()

    if debug_dir is not None and split_pages:
        manifest = write_overrides_template(split_pages, debug_dir)
        if manifest is not None:
            print(f"Wrote blank overrides manifest to {manifest}")

    print(f"\nSplit {len(split_pages)} spreads, passed through {n_single} single pages.")
    print(f"Writing {out_doc.page_count} pages to {output_path} ...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_doc.save(str(output_path))
    out_doc.close()
    print("Done.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Split two-page spreads in an assembled PDF into individual pages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="Path to the assembled spreads PDF (e.g. scan_composite.pdf).")
    p.add_argument("--output", "-o", type=Path, default=None,
                   help=f"Path to write the split-page PDF (default {DEFAULT_OUTPUT}, "
                        f"or {DEFAULT_ONLY_PAGE_OUTPUT} with --only-page).")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--detect", action="store_true",
                      help="Cut each spread at its own detected gutter (the darkest "
                           "vertical column near the middle). Use when the binding "
                           "shadow drifts from spread to spread.")
    mode.add_argument("--fixed", type=float, default=None, metavar="FRAC",
                      help="Cut every spread at this fixed fraction of width (e.g. "
                           "0.5173), skipping detection. Use when the dark-band "
                           "assumption doesn't hold but the scan is well-registered.")

    p.add_argument("--debug-dir", type=Path, default=DEFAULT_DEBUG_DIR,
                   metavar="DIR",
                   help="Save an annotated copy of every split spread (the mode's cut "
                        "in red, and the actual cut in blue when an override moved it) "
                        "to this directory, named debug_NNN.jpg by source page number; "
                        "later runs over a page overwrite its image. Also writes a "
                        f"blank {MANIFEST_NAME} there, unless one already exists "
                        f"(default {DEFAULT_DEBUG_DIR}).")
    p.add_argument("--no-debug", action="store_true",
                   help="Skip writing debug images and the overrides manifest.")
    p.add_argument("--only-page", type=int, default=None,
                   metavar="N",
                   help="Process only source page N (1-indexed) instead of the "
                        "whole document — useful for iterating on a single bad split.")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.fixed is not None and not 0.0 < args.fixed < 1.0:
        raise SystemExit(
            f"--fixed must be a fraction of width strictly between 0 and 1 "
            f"(e.g. 0.5173), got {args.fixed}"
        )

    debug_dir = None if args.no_debug else args.debug_dir

    output_path = args.output
    if output_path is None:
        output_path = (DEFAULT_OUTPUT if args.only_page is None
                       else DEFAULT_ONLY_PAGE_OUTPUT)

    # The manifest is always applied when it exists — no opt-in flag. It
    # lives alongside the debug images, so --no-debug leaves it unread too.
    overrides = None
    manifest_path = (debug_dir or args.debug_dir) / MANIFEST_NAME
    if debug_dir is not None and manifest_path.exists():
        overrides = load_overrides(manifest_path)
        if overrides:
            print(f"Applying {len(overrides)} page overrides from {manifest_path}")

    process(
        input_path=args.input,
        output_path=output_path,
        fixed_x=args.fixed,
        debug_dir=debug_dir,
        only_page=args.only_page,
        overrides=overrides,
    )
