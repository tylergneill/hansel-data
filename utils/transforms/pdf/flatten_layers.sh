#!/usr/bin/env bash
#
# flatten_layers.sh — bake a PDF page down to exactly what it shows
# ==================================================================
# A PDF page can carry information it does not display: several stacked
# images that a viewer composites into one, and a cropbox that hides part
# of the sheet. Both are instructions rather than pixels, and tools that
# read a page's embedded image see straight through them — the wrong
# layer, or the margin that was supposed to be cropped away.
#
# This script renders each page and stores the result, so what the file
# contains becomes what the page showed: layers composited, crop applied,
# one image per page, nothing hidden behind it. Everything the render
# needs is read from the source, so there is nothing to configure.
#
#   flatten_layers.sh INPUT [OUTPUT]
#
# OUTPUT defaults to NAME_flat.pdf alongside the input.
#
# The two cases it exists for
# ---------------------------
# Layered scans store each page as a low-resolution background photo plus
# a set of 1-bit stencil masks carrying the sharp text (MRC / "scanned
# document" compression, as produced by Acrobat's optimizer, ABBYY and
# similar). Extracting the largest image from such a file is not a
# workaround: the background carries none of the sharp text, so the result
# is a blurry scan with words silently missing.
#
# Cropped scans keep the full sheet and name a smaller visible region.
# Rendering that region discards the rest, which is the point: the crop
# stops being an instruction a later tool may ignore and becomes the image
# itself. Each page's own cropbox is used, so a book whose pages are
# cropped differently from one another stays correct.
#
# Either case alone is reason to run. A file with one image per page and
# no crop has nothing to bake in, and the script says so rather than
# re-encoding it for nothing.
#
# Settings are read from the source, not assumed
# ----------------------------------------------
# `pdfimages -list` reports every image's resolution, colorspace, depth
# and encoding. Those readings drive the render:
#
#   Resolution   The highest effective PPI of any image on any page. Using
#                the highest means no layer is ever downsampled; coarser
#                layers are upsampled to meet it. Taking the background's
#                resolution instead would halve the text stencils, which
#                are usually the finer layer and the one that matters for
#                OCR.
#
#   Colorspace   Gray in, gray out; color in, color out. A grayscale scan
#                is never promoted to RGB, which would triple its size for
#                no added information.
#
# Rendering is a raster operation, so the output is necessarily a new
# encoding rather than the source's own bytes — that is inherent in
# flattening, since the layers no longer exist separately to preserve.
# What the detection protects is resolution and colorspace: nothing is
# downsampled, and nothing is promoted.
#
# What does not survive
# ---------------------
# Rendering keeps what a page looks like, not how it was built. Outline
# entries (TOC), embedded text, links and annotations are dropped. On a
# pure scan there is usually no text layer to lose; the run reports what
# it found before writing, so a file that would lose more than pixels
# says so on the way past.
#
# Requires: ghostscript (gs), poppler (pdfimages), and python3 with
# pymupdf for the page-box report.

set -euo pipefail

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,18p' "$0" | sed 's/^#\{1,\} \{0,1\}//'; }

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    "") usage; exit 1 ;;
esac

(( $# <= 2 )) || die "expected INPUT [OUTPUT], got $# arguments"

for tool in gs pdfimages; do
    command -v "$tool" >/dev/null 2>&1 \
        || die "$tool not found (brew install ghostscript poppler)"
done

input="$1"
[[ -f $input ]] || die "no such file: $input"

if (( $# == 2 )); then
    output="$2"
else
    output="$(dirname "$input")/$(basename "${input%.*}")_flat.pdf"
fi

[[ $(cd "$(dirname "$output")" 2>/dev/null && pwd -P)/$(basename "$output") \
   != $(cd "$(dirname "$input")" && pwd -P)/$(basename "$input") ]] \
    || die "refusing to overwrite the input; name a different output"

listing=$(pdfimages -list "$input" 2>/dev/null) \
    || die "pdfimages could not read $input"

# Rows are a fixed 16 fields; stencil rows carry '-' in the color column
# but are otherwise laid out identically to image rows.
#   $1 page  $3 type  $6 color  $7 comp  $13 x-ppi  $14 y-ppi
read -r n_images max_ppi n_color n_stencil <<<"$(
    awk 'NR>2 && NF==16 {
            n++
            if ($13 > mx) mx = $13
            if ($14 > mx) mx = $14
            if ($6 == "rgb" || $6 == "cmyk" || $7 > 1) color++
            if ($3 == "stencil") stencil++
         }
         END { printf "%d %d %d %d\n", n, (mx ? mx : 0), color+0, stencil+0 }' <<<"$listing"
)"

(( n_images > 0 )) || die "$input contains no images — nothing to flatten"
(( max_ppi > 0 )) || die "could not determine a resolution from $input"

pages=$(awk 'NR>2 && NF==16 {c[$1]=1} END {print length(c)}' <<<"$listing")
layered=$(awk 'NR>2 && NF==16 {c[$1]++} END {n=0; for (p in c) if (c[p]>1) n++; print n}' <<<"$listing")

if (( n_color > 0 )); then
    colorspace="rgb"; device="pdfimage24"
else
    colorspace="gray"; device="pdfimage8"
fi

# Page boxes and the non-raster content a render would drop. pdfimages
# cannot report these, and they are what most needs saying before writing:
# whether a crop is about to be baked in, and whether anything other than
# pixels is about to be lost.
n_cropped=0 n_shapes=1 n_toc=0 n_text=0
if box_report=$(python3 - "$input" 2>/dev/null <<'PY'
import sys
try:
    import pymupdf
except ImportError:
    sys.exit(1)

doc = pymupdf.open(sys.argv[1])
cropped, shapes = 0, set()
for page in doc:
    mb, cb = page.mediabox, page.cropbox
    if (round(cb.width, 1), round(cb.height, 1)) != (round(mb.width, 1), round(mb.height, 1)):
        cropped += 1
    shapes.add((round(cb.width, 1), round(cb.height, 1)))
text = sum(1 for page in doc if page.get_text().strip())
print(f"{cropped}\t{len(shapes)}\t{len(doc.get_toc())}\t{text}")
doc.close()
PY
    ); then
    IFS=$'\t' read -r n_cropped n_shapes n_toc n_text <<<"$box_report"
fi

printf 'Input:  %s\n' "$input"
printf '  pages:       %s\n' "$pages"
printf '  images:      %s (%s layered page(s), %s stencil mask(s))\n' \
    "$n_images" "$layered" "$n_stencil"
printf '  resolution:  %s ppi\n' "$max_ppi"
printf '  colorspace:  %s\n' "$colorspace"
if (( n_cropped > 0 )); then
    printf '  cropbox:     %s/%s page(s) hide part of the sheet' "$n_cropped" "$pages"
    (( n_shapes > 1 )) && printf ', %s distinct crop size(s)' "$n_shapes"
    printf '\n'
fi
(( n_toc > 0 )) && printf '  outline:     %s entry(ies) — dropped\n' "$n_toc"
(( n_text > 0 )) && printf '  text layer:  %s page(s) — dropped\n' "$n_text"

# Layers and crops are two forms of the same thing: information the file
# keeps that the page does not show. Either alone is reason to run, so
# stop only when there is neither.
if (( layered == 0 && n_cropped == 0 )); then
    printf '\nEvery page already holds a single image and nothing is cropped,\n'
    printf 'so there is nothing to make permanent.\n'
    die "nothing to flatten or crop — re-rendering would only lose quality"
fi

printf 'Render: %s ppi, %s, cropped to each page'"'"'s cropbox\n' \
    "$max_ppi" "$colorspace"

# Render to a temporary file and move it into place only on success, so an
# interrupted run cannot leave a truncated PDF at the output path.
tmp="${output}.tmp.$$"
trap 'rm -f "$tmp"' EXIT

printf 'Writing %s ...\n' "$output"

# -dUseCropBox renders the visible region; without it gs renders the
# mediabox, which un-hides the margin the crop was suppressing instead of
# discarding it.
gs -dNOPAUSE -dBATCH -dSAFER -dQUIET \
   -dUseCropBox \
   -sDEVICE="$device" \
   -r"$max_ppi" \
   -dDownScaleFactor=1 \
   -sOutputFile="$tmp" \
   "$input" \
    || die "ghostscript failed"

mv "$tmp" "$output"
trap - EXIT

printf 'Done. %s written\n' "$(du -h "$output" | cut -f1 | tr -d ' ')"
