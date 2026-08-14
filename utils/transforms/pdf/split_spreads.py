#!/usr/bin/env python3
"""
split_spreads.py — split assembled two-page spreads into individual half-pages
==============================================================================
Takes the single already-assembled `scan_composite.pdf` (each page is a
two-page spread, left + right book side, already upright — no rotation
needed) and splits every spread into two individual page images, then
reassembles them into one output PDF with roughly twice the page count.

Each page's embedded image is pulled out of the PDF as-is rather than
re-rendered, so the halves are pixel-for-pixel the same data as the
original, just cut in half — same resolution, same colorspace. They are
re-encoded in the source's own format, reusing its JPEG quantization
tables and chroma subsampling where applicable, so the halves match the
original's quality rather than approximating it.

Splitting cannot avoid a re-encode (the halves are new images), but it
must never make a page harder to read. Reducing file size is explicitly
not this script's job.

A small number of pages (<5) in the source are already single pages
(portrait aspect ratio) rather than spreads — e.g. trailing
corrigenda/appendix pages scanned individually. These are detected
automatically by aspect ratio and passed through unsplit.

That test assumes a spread is decisively wider than tall (SPREAD_RATIO).
Some books break the assumption: tall pages cropped tight to the text
leave a spread barely wider than square, below the threshold, and the
whole book passes through unsplit. --force-all bypasses the test and
splits every page. It is a per-book override, not a reason to lower
SPREAD_RATIO — the threshold still earns its keep on books where a
handful of genuine single pages need ruling out. Under --force-all
those pages get split too, so check the output for any.

Where to cut: --detect or --fixed
---------------------------------
Every spread needs a cut position, and there are two ways to get one.
Exactly one of these is required:

  --detect
      Search each spread independently for the darkest vertical column
      (the binding shadow) and cut there. Use when the gutter drifts
      spread to spread, which is the usual case for a hand-scanned book.

      The search covers a band around the middle of the page, not the
      whole width. If a book's gutter falls outside that band the search
      cannot report failure — it returns the band's own edge, which looks
      like a confident answer and repeats on every page. A run that
      produces the same cut everywhere under --detect is the signature of
      this, and the run warns about it explicitly; widen SEARCH_WINDOW or
      move DETECT_CENTER below if it fires.

  --fixed [FRAC]
      Cut every spread at the same fraction of width, e.g. --fixed
      0.5173, skipping the search entirely. Use when the dark-band
      assumption doesn't hold for a book but the scan is well-registered
      — read a good starting value off any debug image's red-line label.

      Bare --fixed, with no value, cuts at FIXED_DEFAULT (0.50) — the
      blind halfway cut, and a reasonable first look at a book with no
      binding shadow to detect. Note this is a separate constant from
      --detect's DETECT_CENTER, which happens to share its value.

Neither is expected to be right on every page. Both feed the same
review-and-correct loop below, so the choice is just which baseline
leaves you the fewest pages to fix by hand.

    python split_spreads.py -i scan_composite.pdf --detect
    python split_spreads.py -i scan_composite.pdf --fixed 0.5173
    python split_spreads.py -i scan_composite.pdf --fixed 0.5173 --only-page 204

Everything is written to tmp/ next to this script (gitignored): the
split PDF to tmp/split_result.pdf, debug images and the correction
manifest to tmp/debug/. Those paths hold no matter which directory you
run from. Override with -o/--debug-dir, or pass --no-debug to skip debug
output.

--only-page writes to tmp/split_result_only_page.pdf instead, so
iterating on a single spread never overwrites the full book from an
earlier run.

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
page — note that tmp/split_result.pdf does not, since --only-page writes
its PDF elsewhere.

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
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, JpegImagePlugin


# Internal tuning constants. These are not CLI flags: they shape how
# --detect searches, and are not things a run is normally driven with.
DETECT_CENTER = 0.50    # Center of the search band, as a fraction of width,
                        # and the fallback when detection isn't confident.
SEARCH_WINDOW = 0.10    # Search +/- this fraction of width around DETECT_CENTER.
                        # Wide enough to cover books whose gutter sits well off
                        # centre: a band that stops short of the real gutter does
                        # not fail, it returns its own edge column, which looks
                        # like a confident answer and repeats across the whole
                        # book. Widening is cheap -- the search is a few percent
                        # of per-page cost, dominated by decode and re-encode --
                        # so the band is sized for headroom rather than trimmed.
EDGE_MARGIN = 2         # Columns. A result landing this close to the band edge is
                        # treated as unconfident: the true minimum is most likely
                        # outside the band, and the search merely saturated.
MIN_CONTRAST = 6        # Minimum brightness dip (0-255) below the search band's
                        # average before the darkest column is trusted as a real
                        # gutter. Guards against blank spreads, where some column
                        # is always "darkest" by a fraction of a gray level of
                        # scanner noise.
SPREAD_RATIO = 1.2      # width/height above this = spread (split); below = single.
FIXED_DEFAULT = 0.50    # Cut fraction used by a bare --fixed (no value given).
                        # Deliberately its own constant rather than a reference to
                        # DETECT_CENTER: the two are equal by coincidence, not by
                        # meaning. DETECT_CENTER centres a search band and is
                        # retuned when a book's gutter sits off-centre; this is
                        # just "halfway across", the sane blind cut. Tying them
                        # together would silently move every bare --fixed cut the
                        # next time the detector is retuned.

# Gitignored scratch space next to this script. All generated files land here,
# so the defaults work no matter which directory the script is invoked from.
TMP_DIR = Path(__file__).resolve().parent / "tmp"
DEFAULT_OUTPUT = TMP_DIR / "split_result.pdf"
# --only-page runs write elsewhere by default, so a one-page throwaway can
# never overwrite the full book's output from an earlier run.
DEFAULT_ONLY_PAGE_OUTPUT = TMP_DIR / "split_result_only_page.pdf"
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


def _summarize_pages(pages: list[int], limit: int = 12) -> str:
    """
    Render a page list compactly, collapsing runs ("4-19") and truncating
    once it gets long — a warning naming 66 pages one by one is a warning
    nobody reads.
    """
    if not pages:
        return "none"
    runs: list[tuple[int, int]] = []
    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
            continue
        runs.append((start, prev))
        start = prev = p
    runs.append((start, prev))

    parts = [str(a) if a == b else f"{a}-{b}" for a, b in runs]
    if len(parts) > limit:
        return ", ".join(parts[:limit]) + f", ... (+{len(parts) - limit} more)"
    return ", ".join(parts)


def find_gutter(img: Image.Image) -> tuple[float, str | None]:
    """
    Find the gutter (binding shadow) as the darkest vertical column within
    +/- SEARCH_WINDOW of DETECT_CENTER.

    Returns (cut_fraction, warning). The warning is None on a confident
    detection, otherwise a string naming what went wrong; the fraction then
    falls back to DETECT_CENTER. Two things can go wrong:

    "no contrast"
        The darkest column isn't meaningfully darker than the window average
        (e.g. a blank/near-blank spread with no real shadow to detect).

    "pinned to band edge"
        The darkest column is at the very edge of the search band, which
        means the true minimum is most likely outside it — the search
        saturated rather than found anything. Left unreported this is the
        more dangerous of the two, because the band edge is a perfectly
        plausible-looking cut position that repeats identically across every
        page, so a mis-centred band presents as a suspiciously fixed split
        rather than as a failure.
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
        return DETECT_CENTER, "no contrast"

    # Only meaningful when the band was not clipped by the image edge: a band
    # running off the image legitimately has its minimum at the boundary.
    if (x_start > 0 and darkest_x <= x_start + EDGE_MARGIN) or \
       (x_end < w and darkest_x >= x_end - 1 - EDGE_MARGIN):
        return darkest_x / w, "pinned to band edge"

    return darkest_x / w, None


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


def load_page_image(doc: pymupdf.Document, page: pymupdf.Page) -> tuple[Image.Image, dict]:
    """
    Pull the page's single embedded image out of the PDF as-is, rather than
    re-rendering the page to a pixmap. This preserves the source's own
    colorspace and pixel data instead of forcing a conversion, and hands
    back the encoding parameters needed to write the halves out the same
    way they came in.
    """
    images = page.get_images(full=True)
    if len(images) != 1:
        raise ValueError(f"expected exactly 1 embedded image, found {len(images)}")

    extracted = doc.extract_image(images[0][0])
    img = Image.open(io.BytesIO(extracted["image"]))
    img.load()

    # Carry the source's own JPEG quantization tables and chroma subsampling
    # through to the halves, so re-encoding reproduces the original quality
    # rather than approximating it with a quality number.
    params: dict = {"format": img.format or extracted["ext"].upper()}
    if params["format"] == "JPEG":
        qtables = getattr(img, "quantization", None)
        if qtables:
            params["qtables"] = qtables
            params["subsampling"] = JpegImagePlugin.get_sampling(img)
    return img, params


def _encoded_bytes(img: Image.Image, params: dict) -> bytes:
    """Re-encode a half using the source image's own format and settings."""
    fmt = params["format"]
    kwargs = {k: v for k, v in params.items() if k != "format"}
    buf = io.BytesIO()
    try:
        img.save(buf, fmt, **kwargs)
    except (OSError, ValueError):
        # A format/mode pair Pillow can't write back (or unusable qtables);
        # fall back to lossless PNG rather than silently degrading quality.
        buf = io.BytesIO()
        img.save(buf, "PNG")
    return buf.getvalue()


def process(input_path: Path, output_path: Path, fixed_x: float | None,
            debug_dir: Path | None = None, only_page: int | None = None,
            overrides: dict[int, int] | None = None,
            force_all: bool = False) -> None:
    """
    Split every spread in the input. fixed_x is the --fixed fraction, or
    None to detect each spread's gutter independently (--detect).

    force_all (--force-all) bypasses the SPREAD_RATIO test and splits every
    page, for books whose spreads are too square to clear the threshold.
    """
    doc = pymupdf.open(str(input_path))
    n_pages = len(doc)
    print(f"Input: {input_path} ({n_pages} pages)")

    out_doc = pymupdf.open()
    split_pages: list[int] = []
    unconfident: dict[str, list[int]] = {}
    n_single = 0

    page_range = range(n_pages) if only_page is None else [only_page - 1]

    for i in page_range:
        page = doc[i]
        img, encode_params = load_page_image(doc, page)
        img_w, img_h = img.size

        ratio = img_w / img_h

        if force_all or ratio > SPREAD_RATIO:
            # The mode's cut for this page, before any per-page correction.
            if fixed_x is None:
                mode_x, warning = find_gutter(img)
                if warning is not None:
                    unconfident.setdefault(warning, []).append(i + 1)
            else:
                mode_x = fixed_x
            cut_x = mode_x
            offset_px = (overrides or {}).get(i + 1)
            if offset_px is not None:
                cut_x = min(max(cut_x * img_w + offset_px, 0), img_w) / img_w
            if debug_dir is not None:
                save_debug_image(img, mode_x, cut_x, offset_px, i + 1, debug_dir)
            left, right = split_spread(img, cut_x)
            halves_bytes = [_encoded_bytes(left, encode_params),
                            _encoded_bytes(right, encode_params)]
            sizes = [left.size, right.size]
            split_pages.append(i + 1)
        else:
            halves_bytes = [_encoded_bytes(img, encode_params)]
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

    # Detection that quietly returned something unusable is worse than
    # detection that failed, so say so plainly and point at the knob to turn.
    for reason, pages in sorted(unconfident.items()):
        share = len(pages) / max(len(split_pages), 1)
        print(f"\nWARNING: gutter detection was unconfident on "
              f"{len(pages)}/{len(split_pages)} spreads ({reason}): "
              f"{_summarize_pages(pages)}", file=sys.stderr)
        if reason == "pinned to band edge":
            print(f"  The darkest column sat at the edge of the "
                  f"{DETECT_CENTER-SEARCH_WINDOW:.2f}-{DETECT_CENTER+SEARCH_WINDOW:.2f} "
                  f"search band, so the real gutter is probably outside it and "
                  f"these cuts are all landing in the same wrong place.",
                  file=sys.stderr)
            if share > 0.5:
                print(f"  Most of the book is affected: widen SEARCH_WINDOW "
                      f"(now {SEARCH_WINDOW}) or move DETECT_CENTER "
                      f"(now {DETECT_CENTER}) in {Path(__file__).name}, or "
                      f"switch to --fixed after reading a good fraction off a "
                      f"debug image.", file=sys.stderr)
        else:
            print(f"  These spreads fell back to a cut at {DETECT_CENTER}.",
                  file=sys.stderr)

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
    mode.add_argument("--fixed", type=float, nargs="?", default=None,
                      const=FIXED_DEFAULT, metavar="FRAC",
                      help=f"Cut every spread at this fixed fraction of width (e.g. "
                           f"0.5173), skipping detection. Use when the dark-band "
                           f"assumption doesn't hold but the scan is well-registered. "
                           f"Bare --fixed with no value cuts at {FIXED_DEFAULT}.")

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
    p.add_argument("--force-all", action="store_true",
                   help=f"Split every page, bypassing the width/height > {SPREAD_RATIO} "
                        f"test used to tell spreads from single pages. For books whose "
                        f"spreads are too square to clear it (tall pages scanned tight, "
                        f"so two side by side are barely wider than tall). Splits "
                        f"genuine single pages too — check the output for any.")
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
        force_all=args.force_all,
    )
