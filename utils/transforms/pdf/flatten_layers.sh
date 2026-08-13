#!/usr/bin/env bash
#
# flatten_layers.sh — composite layered scan PDFs into one image per page
# =======================================================================
# Some scanned PDFs store each page as several stacked images rather than
# one: a low-resolution background photo plus a set of 1-bit stencil masks
# carrying the sharp text (MRC / "scanned document" compression, as
# produced by Acrobat's optimizer, ABBYY, and similar). The page renders
# correctly because the viewer composites the layers, but tools that pull
# out the embedded image see only one layer at a time.
#
# Extracting the largest image from such a file is not a workaround: on a
# typical page the background carries none of the sharp text, so the result
# is a blurry scan with words silently missing. This script composites the
# layers instead, so every page becomes a single image containing
# everything that was visible.
#
# Settings are detected from the source, not assumed
# --------------------------------------------------
# `pdfimages -list` reports every image's resolution, colorspace, depth and
# encoding. Those readings choose the rasterizer settings, so the output
# stays as close to the input as a composite allows:
#
#   Resolution   The highest effective PPI of any image on any page. Using
#                the highest means no layer is ever downsampled; the
#                coarser layers are upsampled to meet it. Picking the
#                background's resolution instead would halve the text
#                layers, which are usually the finer of the two and the
#                ones that matter for OCR.
#
#   Colorspace   Gray in, gray out; color in, color out. A grayscale scan
#                is never promoted to RGB, which would triple its size for
#                no added information.
#
# Compositing is a raster operation, so the output is necessarily a new
# encoding rather than the source's own bytes — the layers no longer exist
# separately to preserve. What the detection protects is resolution and
# colorspace: nothing is downsampled, and nothing is promoted.
#
# Pages that already hold a single image are still re-rasterized, since
# the whole document goes through one rasterizer pass. Run this only on
# files that need it — check with --inspect first.
#
# Usage
# -----
#   flatten_layers.sh INPUT [-o OUTPUT] [--dpi N] [--gray|--rgb]
#   flatten_layers.sh INPUT --inspect
#
#   -o OUTPUT   Write here (default: alongside INPUT as NAME_flat.pdf).
#   --dpi N     Override the detected resolution.
#   --gray      Force grayscale output.
#   --rgb       Force RGB output.
#   --inspect   Report what was detected and the settings it implies,
#               then exit without rasterizing.
#
# Examples
#   flatten_layers.sh tmp/pages.pdf --inspect
#   flatten_layers.sh tmp/pages.pdf
#   flatten_layers.sh tmp/pages.pdf -o tmp/flat.pdf --dpi 300
#
# Requires: ghostscript (gs), poppler (pdfimages).

set -euo pipefail

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '2,60p' "$0" | sed 's/^#\{1,\} \{0,1\}//'
}

for tool in gs pdfimages; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool not found (brew install ghostscript poppler)"
done

input=""
output=""
force_dpi=""
force_color=""
inspect=0

while (( $# )); do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --inspect) inspect=1; shift ;;
        --gray|--grey) force_color="gray"; shift ;;
        --rgb) force_color="rgb"; shift ;;
        --dpi)
            [[ ${2:-} ]] || die "--dpi needs a value"
            force_dpi="$2"; shift 2 ;;
        -o|--output)
            [[ ${2:-} ]] || die "-o needs a path"
            output="$2"; shift 2 ;;
        -*) die "unknown option: $1" ;;
        *)
            [[ -z $input ]] || die "only one input file (got '$input' and '$1')"
            input="$1"; shift ;;
    esac
done

[[ $input ]] || { usage; exit 1; }
[[ -f $input ]] || die "no such file: $input"

if [[ -n $force_dpi ]] && ! [[ $force_dpi =~ ^[0-9]+$ ]]; then
    die "--dpi must be a positive integer, got '$force_dpi'"
fi

listing=$(pdfimages -list "$input" 2>/dev/null) \
    || die "pdfimages could not read $input"

# Rows are fixed-width at 16 fields; stencil rows carry '-' in the color
# column but are otherwise laid out identically to image rows.
#   $3 type   $6 color   $7 comp   $8 bpc   $9 enc   $13 x-ppi   $14 y-ppi
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

pages=$(awk 'NR>2 && NF==16 {c[$1]=1} END {print length(c)}' <<<"$listing")
layered=$(awk 'NR>2 && NF==16 {c[$1]++} END {n=0; for (p in c) if (c[p] > 1) n++; print n}' <<<"$listing")

dpi=${force_dpi:-$max_ppi}
(( dpi > 0 )) || die "could not determine a resolution; pass --dpi"

if [[ -n $force_color ]]; then
    colorspace="$force_color"
elif (( n_color > 0 )); then
    colorspace="rgb"
else
    colorspace="gray"
fi

# pdfimage8 writes 8-bit gray, pdfimage24 writes 24-bit rgb. Both emit one
# composited image per page, which is the point of the exercise.
if [[ $colorspace == rgb ]]; then
    device="pdfimage24"
else
    device="pdfimage8"
fi

printf 'Input:   %s\n' "$input"
printf '  pages:            %s\n' "$pages"
printf '  images:           %s (%s layered page(s), %s stencil mask(s))\n' \
    "$n_images" "$layered" "$n_stencil"
printf '  highest ppi:      %s\n' "$max_ppi"
printf '  colorspace:       %s\n' "$colorspace"
printf 'Render:  %s dpi, %s (%s)%s\n' \
    "$dpi" "$colorspace" "$device" \
    "$( [[ -n $force_dpi || -n $force_color ]] && printf ' [overridden]' )"

if (( layered == 0 )); then
    printf '\nNote: no page has more than one image — this file does not need\n'
    printf '      flattening, and rasterizing it would only lose quality.\n'
    (( inspect )) || die "refusing to flatten a file with no layered pages (use --dpi to force a re-raster if that is really what you want)"
fi

if (( inspect )); then
    printf '\nInspect only — nothing written.\n'
    exit 0
fi

if [[ -z $output ]]; then
    dir=$(dirname "$input")
    base=$(basename "$input")
    output="$dir/${base%.*}_flat.pdf"
fi

[[ $(cd "$(dirname "$output")" && pwd -P)/$(basename "$output") \
   != $(cd "$(dirname "$input")" && pwd -P)/$(basename "$input") ]] \
    || die "refusing to overwrite the input; choose a different -o"

# Rasterize to a temporary file and move it into place only on success, so
# an interrupted run cannot leave a truncated PDF at the output path.
tmp="${output}.tmp.$$"
cleanup() { rm -f "$tmp"; }
trap cleanup EXIT

printf 'Writing %s ...\n' "$output"
gs -dNOPAUSE -dBATCH -dSAFER -dQUIET \
   -sDEVICE="$device" \
   -r"$dpi" \
   -dDownScaleFactor=1 \
   -sOutputFile="$tmp" \
   "$input" \
    || die "ghostscript failed"

mv "$tmp" "$output"
trap - EXIT

printf 'Done. %s\n' "$(du -h "$output" | cut -f1) written"
