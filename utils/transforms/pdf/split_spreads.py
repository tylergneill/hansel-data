#!/usr/bin/env python3
"""
split_spreads.py — split assembled two-page spreads into individual half-pages
==============================================================================
Takes the single already-assembled `scan_composite.pdf` (each page is a
two-page spread, left + right book side, already upright — no rotation
needed) and splits every spread into two individual page images, then
reassembles them into one output PDF with roughly twice the page count.

Each page is rendered via PyMuPDF at its native resolution (matching the
embedded image's own pixel dimensions, not an arbitrary fixed DPI) and in
grayscale (matching the source), so the split halves are pixel-for-pixel
the same data as the original, just cut in half. Re-encoded as JPEG with
optimize=True at the same quality as the source, output filesize stays
close to the input rather than ballooning.

The gutter (binding shadow) doesn't sit at a fixed x-position across the
whole book — it drifts spread to spread. So instead of cutting every
spread at one fixed --split-x, each spread is searched independently in
a window around --split-x for the darkest vertical column (the binding
shadow), same technique as the old calibrate_split.py. If no clear dip
is found in the window (e.g. a mostly-blank spread with no real shadow
signal), --split-x is used as a fallback for that spread only.

A small number of pages (<5) in the source are already single pages
(portrait aspect ratio) rather than spreads — e.g. trailing
corrigenda/appendix pages scanned individually. These are detected
automatically by aspect ratio and passed through unsplit.

The three commands:
    python split_spreads.py -i scan_composite.pdf                  # full run
    python split_spreads.py -i scan_composite.pdf --only-page 204   # one page
    python split_spreads.py -i scan_composite.pdf --resplit         # corrections

  Everything is written to tmp/ next to this script (gitignored): the
  split PDF to tmp/out.pdf, debug images and the correction manifest to
  tmp/debug/. Those paths hold no matter which directory you run from.
  Override with -o/--debug-dir, or pass --no-debug to skip debug output.

  --only-page writes to tmp/out_only_page.pdf instead, so iterating on a
  single spread never overwrites the full book from an earlier run.

Debugging bad splits:
  Every run saves an annotated copy of each split spread to the debug
  directory, named debug_NNN.jpg by source page number.

  Each image shows the detected gutter as a solid red line, and (only
  when it differs) the fixed --split-x fallback as a dashed blue line.
  Flip through the debug images to spot cuts that landed in text instead
  of the binding shadow — either the detector locked onto the wrong dark
  column (e.g. a table or image edge near the gutter), or it fell back
  to --split-x on a page that actually needed real detection.

  To iterate on one bad page without re-running the whole book, use
  --only-page (skips straight to that page; its one-page PDF goes to
  tmp/out_only_page.pdf, since you only care about the debug image):
    python split_spreads.py -i scan_composite.pdf --only-page 204

  If a page is consistently wrong, adjust --search-window (how far from
  --split-x to look) or --min-contrast (how much darker the gutter must
  be than the window average before it's trusted over the fallback),
  then re-check with --only-page before committing to a full re-run.

Persisting per-page corrections with --resplit:
  Each run also drops a blank manifest at overrides.csv in the debug
  directory, pre-filled with one row per split page and no offsets, ready
  to edit. An existing overrides.csv is never overwritten, so your
  corrections survive re-runs — delete it to regenerate a blank one.

  Once you've spotted a bad cut in a debug image (the red line lands in
  text instead of the binding shadow), record a correction in that CSV
  manifest, one `page,offset_px` row per bad page (page = 1-indexed
  source page number; offset_px = pixels to shift the cut, at that
  page's native resolution, positive = right, negative = left):

    204,15
    186,-8
    133,

  A blank offset (e.g. `133,`) records a page as reviewed with no
  correction needed (offset 0) — distinct from a page simply absent
  from the file (never reviewed).

  Then pass it via --resplit, which with no argument reads overrides.csv
  from the debug directory (give it a path to use a manifest elsewhere):
    python split_spreads.py -i scan_composite.pdf --resplit

  For any page listed, the offset is added (in pixel space) to whatever
  gutter position would otherwise have been used (detected or
  --split-x fallback) — detection still runs as normal everywhere else,
  including on overridden pages themselves (the offset is a correction
  on top of detection, not a replacement for it). --resplit works with
  a full run or combined with --only-page to regenerate just one page:

    python split_spreads.py -i scan_composite.pdf --resplit --only-page 204

  Re-check the new debug image for that page before committing to a
  full re-run of the whole book.

Dependencies:
  pip install pymupdf pillow
"""

import argparse
import io
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw


DEFAULTS = dict(
    split_x=0.50,          # Gutter position as fraction of image width (fallback)
    search_window=0.03,    # Search +/- this fraction of width around split_x for the gutter
    min_contrast=6,        # Minimum brightness dip (0-255) vs window average to trust detection
    quality=90,            # JPEG output quality for split halves
    spread_ratio=1.2,      # width/height above this = spread (split); below = single page
)

# Gitignored scratch space next to this script. All generated files land here,
# so the defaults work no matter which directory the script is invoked from.
TMP_DIR = Path(__file__).resolve().parent / "tmp"
DEFAULT_OUTPUT = TMP_DIR / "out.pdf"
# --only-page runs write elsewhere by default, so a one-page throwaway can
# never overwrite the full book's output from an earlier run.
DEFAULT_ONLY_PAGE_OUTPUT = TMP_DIR / "out_only_page.pdf"
DEFAULT_DEBUG_DIR = TMP_DIR / "debug"
MANIFEST_NAME = "overrides.csv"


def load_resplit_overrides(path: Path) -> dict[int, int]:
    """
    Parse a --resplit manifest: one `page,offset_px` row per line (page =
    1-indexed source page number, offset_px = pixel shift to apply to
    that page's gutter, positive = right, negative = left). offset_px may
    be left blank (e.g. `133,`) to record a page as reviewed with no
    correction needed (offset 0), distinct from a page simply absent from
    the file (never reviewed). Blank lines and # comments are skipped.
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


def find_gutter(img: Image.Image, split_x: float, search_window: float,
                 min_contrast: float) -> float:
    """
    Find the gutter (binding shadow) as the darkest vertical column within
    +/- search_window of split_x. Falls back to split_x if the darkest
    column isn't meaningfully darker than the window average (e.g. a
    blank/near-blank spread with no real shadow to detect).
    """
    w, h = img.size
    x_start = max(0, round(w * (split_x - search_window)))
    x_end = min(w, round(w * (split_x + search_window)))

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

    if window_avg - darkest_mean < min_contrast:
        return split_x
    return darkest_x / w


def save_debug_image(img: Image.Image, gutter_x: float, split_x: float,
                      page_num: int, debug_dir: Path) -> None:
    """Save a copy of the spread annotated with the detected gutter (red,
    solid) and the fallback split_x (blue, dashed) for visual review."""
    annotated = img.convert("RGB")
    draw = ImageDraw.Draw(annotated)
    w, h = annotated.size

    if abs(gutter_x - split_x) > 1e-9:
        fx = round(w * split_x)
        for y in range(0, h, 30):
            draw.line([(fx, y), (fx, min(y + 15, h))], fill=(40, 130, 220), width=2)

    gx = round(w * gutter_x)
    draw.line([(gx, 0), (gx, h)], fill=(220, 30, 30), width=2)
    draw.text((gx + 6, 10), f"gutter {gutter_x:.4f}", fill=(220, 30, 30))

    debug_dir.mkdir(parents=True, exist_ok=True)
    annotated.save(debug_dir / f"debug_{page_num:03d}.jpg", "JPEG", quality=85)


def write_resplit_template(pages: list[int], debug_dir: Path) -> Path | None:
    """
    Write a blank --resplit manifest alongside the debug images, one row per
    split page with an empty offset (reviewed-pending). Returns the path, or
    None if the file already exists — an existing manifest holds hand-entered
    corrections and is never overwritten.
    """
    path = debug_dir / MANIFEST_NAME
    if path.exists():
        return None

    lines = [
        "# --resplit manifest: set offset_px on any page whose cut is wrong,",
        "# then re-run with --resplit pointing at this file.",
        "# offset_px = pixel shift at the page's native resolution,",
        "# positive = right, negative = left. A blank offset means",
        "# reviewed, no correction needed.",
        "# page,offset_px",
    ]
    lines.extend(f"{page}," for page in pages)

    debug_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def split_spread(img: Image.Image, split_x: float) -> tuple[Image.Image, Image.Image]:
    """Split a two-page spread into left and right halves."""
    w, h = img.size
    cut = round(w * split_x)
    left = img.crop((0, 0, cut, h))
    right = img.crop((cut, 0, w, h))
    return left, right


def _jpeg_bytes(img: Image.Image, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
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


def process(input_path: Path, output_path: Path, split_x: float,
            search_window: float, min_contrast: float,
            quality: int, spread_ratio: float,
            debug_dir: Path | None = None, only_page: int | None = None,
            resplit_overrides: dict[int, int] | None = None) -> None:
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

        if ratio > spread_ratio:
            gutter_x = find_gutter(img, split_x, search_window, min_contrast)
            offset_px = (resplit_overrides or {}).get(i + 1)
            if offset_px is not None:
                w = pix.width
                gutter_x = min(max(gutter_x * w + offset_px, 0), w) / w
            if debug_dir is not None:
                save_debug_image(img, gutter_x, split_x, i + 1, debug_dir)
            left, right = split_spread(img, gutter_x)
            halves_bytes = [_jpeg_bytes(left, quality), _jpeg_bytes(right, quality)]
            sizes = [left.size, right.size]
            split_pages.append(i + 1)
        else:
            halves_bytes = [_jpeg_bytes(img, quality)]
            sizes = [img.size]
            n_single += 1
            print(f"  page {i+1}/{n_pages}: treated as single page "
                  f"(ratio {ratio:.3f} <= {spread_ratio})")

        for (hw, hh), jpeg_bytes in zip(sizes, halves_bytes):
            out_page = out_doc.new_page(width=hw, height=hh)
            out_page.insert_image(out_page.rect, stream=jpeg_bytes)

        if (i + 1) % 25 == 0 or (i + 1) == n_pages:
            print(f"  ...{i+1}/{n_pages} spreads processed, "
                  f"{out_doc.page_count} output pages so far")

    doc.close()

    if debug_dir is not None and split_pages:
        manifest = write_resplit_template(split_pages, debug_dir)
        if manifest is not None:
            print(f"Wrote blank resplit manifest to {manifest}")

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
    p.add_argument("--split-x", type=float, default=DEFAULTS["split_x"],
                   metavar="FRAC",
                   help="Fallback/center gutter position as fraction of width "
                        f"(default {DEFAULTS['split_x']}). Each spread's actual gutter "
                        "is auto-detected near this value; this is only used verbatim "
                        "when detection is not confident.")
    p.add_argument("--search-window", type=float, default=DEFAULTS["search_window"],
                   metavar="FRAC",
                   help="Search +/- this fraction of width around --split-x for the "
                        f"gutter on each spread (default {DEFAULTS['search_window']}).")
    p.add_argument("--min-contrast", type=float, default=DEFAULTS["min_contrast"],
                   metavar="N",
                   help="Minimum brightness dip (0-255) required to trust the detected "
                        f"gutter over the --split-x fallback (default {DEFAULTS['min_contrast']}).")
    p.add_argument("--quality", type=int, default=DEFAULTS["quality"],
                   help=f"JPEG output quality 1-95 for split halves (default {DEFAULTS['quality']}).")
    p.add_argument("--spread-ratio", type=float, default=DEFAULTS["spread_ratio"],
                   metavar="RATIO",
                   help="Width/height ratio above which a page is treated as a "
                        f"spread to split (default {DEFAULTS['spread_ratio']}).")
    p.add_argument("--debug-dir", type=Path, default=DEFAULT_DEBUG_DIR,
                   metavar="DIR",
                   help="Save an annotated copy of every split spread (detected "
                        "gutter in red, fallback split-x dashed in blue) to this "
                        "directory, named debug_NNN.jpg by source page number. "
                        f"Also writes a blank {MANIFEST_NAME} manifest there for "
                        f"--resplit, unless one already exists (default {DEFAULT_DEBUG_DIR}).")
    p.add_argument("--no-debug", action="store_true",
                   help="Skip writing debug images and the resplit manifest.")
    p.add_argument("--only-page", type=int, default=None,
                   metavar="N",
                   help="Process only source page N (1-indexed) instead of the "
                        "whole document — useful for iterating on a single bad split.")
    p.add_argument("--resplit", type=Path, nargs="?", const=Path(""), default=None,
                   metavar="CSV",
                   help="Apply per-page gutter corrections from a manifest of "
                        "'page,offset_px' rows (page = 1-indexed source page "
                        "number, offset_px = pixel shift at that page's native "
                        "resolution, positive = right, negative = left). Listed "
                        "pages get their detected/fallback gutter shifted by "
                        "offset_px; all other pages are unaffected. Pass without "
                        f"a path to use {MANIFEST_NAME} in the debug directory.")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    debug_dir = None if args.no_debug else args.debug_dir

    output_path = args.output
    if output_path is None:
        output_path = (DEFAULT_OUTPUT if args.only_page is None
                       else DEFAULT_ONLY_PAGE_OUTPUT)

    resplit_path = args.resplit
    if resplit_path == Path(""):
        # Bare --resplit: use the manifest written alongside the debug images.
        resplit_path = (debug_dir or args.debug_dir) / MANIFEST_NAME
    if resplit_path is not None and not resplit_path.exists():
        raise SystemExit(
            f"--resplit manifest not found: {resplit_path}\n"
            "Run once with debug output enabled to generate a blank one."
        )

    resplit_overrides = (
        load_resplit_overrides(resplit_path) if resplit_path is not None else None
    )
    process(
        input_path=args.input,
        output_path=output_path,
        split_x=args.split_x,
        search_window=args.search_window,
        min_contrast=args.min_contrast,
        quality=args.quality,
        spread_ratio=args.spread_ratio,
        debug_dir=debug_dir,
        only_page=args.only_page,
        resplit_overrides=resplit_overrides,
    )
