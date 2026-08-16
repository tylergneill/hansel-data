#!/usr/bin/env python3
"""
adjust_spreads.py — set spread cut positions by dragging them in a browser
==========================================================================
An interactive front end for the same review-and-correct loop that
split_spreads.py already runs on: same input PDF, same --detect/--fixed
baselines, same red line, same overrides.csv. The difference is where the
correction is made. Instead of reading a pixel offset off a debug image
and typing it into the CSV by hand, this serves each spread in a browser
and lets the cut be dragged onto the gutter with the mouse; the drag is
written straight back to overrides.csv as that page's offset.

    python adjust_spreads.py -i scan_composite.pdf --detect
    python adjust_spreads.py -i scan_composite.pdf --fixed 0.5173

Either command starts a local server, prints a URL, and opens it. Drag
the line on each spread, move on with the arrow keys, and Ctrl-C the
server when finished.

This script never splits anything and never writes a PDF. Its only
output is overrides.csv. Producing the split pages is still
split_spreads.py's job, run afterwards exactly as before:

    python split_spreads.py -i scan_composite.pdf --detect

Both scripts read the same manifest, so the two ways of correcting a
page are interchangeable — pages dragged here can be fine-tuned by
editing the CSV, and pages already corrected by hand show up here
pre-positioned on their recorded offset.

The two lines
-------------
Same meaning as in split_spreads.py's debug images, so the colours carry
over between the two tools:

  Red is the baseline — where --detect or --fixed put the cut for this
  page, before any correction. It never moves.

  Blue is the cut that will actually be taken. It appears as soon as the
  page has an override, and dragging is what moves it. A page with no
  override has no blue line, and its red line alone is the cut.

Dragging blue back onto red does not delete the override; it records an
explicit offset of 0, which is the manifest's way of saying "reviewed,
nothing to correct" — the same thing a blank offset means. Use the Reset
key to drop the row's offset back to blank instead.

Controls
--------
  drag                 move the cut (grab anywhere on the image)
  click                jump the cut to that column
  <- / ->              previous / next spread
  , / .                nudge the cut 1px left / right
  < / >                nudge the cut 10px left / right
  r                    reset this page to its red baseline (offset blank)
  u                    jump to the next page with no recorded offset

Every change is saved immediately — there is no save button and no
unsaved state. overrides.csv is rewritten in full on each edit, with
its comment header and one row per split page preserved, so it stays
the same file split_spreads.py expects and stays hand-editable.

Only spreads appear. Pages the aspect-ratio test treats as single pages
(SPREAD_RATIO in split_spreads.py) are skipped here, since they are
passed through unsplit and have no cut to place.

Scale and memory
----------------
Spreads are decoded on demand, one per request, and sent to the browser
downscaled to --preview-width (default 1600px) — enough to see the
gutter, small enough to page through quickly. Dragging is recorded
against the page's native resolution regardless, so offsets written here
mean the same thing as offsets typed by hand.

Dependencies:
  pip install pymupdf pillow
"""

import argparse
import http.server
import io
import json
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import pymupdf
from PIL import Image

from split_spreads import (
    DEFAULT_DEBUG_DIR,
    MANIFEST_NAME,
    SPREAD_RATIO,
    find_gutter,
    load_page_image,
)

DEFAULT_PREVIEW_WIDTH = 1600
DEFAULT_PORT = 8765


def read_manifest(path: Path) -> dict[int, int]:
    """
    Read the manifest, keeping only rows that carry an actual offset.

    split_spreads.load_overrides is deliberately not reused here. It maps a
    blank offset (`133,`) to 0, which is right for splitting — "reviewed, no
    correction" and "shift by zero" cut in the same place — but it erases the
    one distinction this tool navigates by. Blank means *unreviewed* here, and
    the "next unreviewed" jump needs to see it as such, so blank rows are left
    out of the dict entirely rather than flattened to 0.

    Parsing stays deliberately permissive about everything else: a row this
    tool skips is still a row split_spreads.py will read, so nothing is
    silently dropped from the file — write_overrides preserves every page.
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
        if not offset_str:
            continue
        try:
            overrides[int(page_str)] = int(offset_str)
        except ValueError:
            raise ValueError(f"{path}:{lineno}: expected two integers, got {line!r}")
    return overrides


def build_page_index(doc: pymupdf.Document, fixed_x: float | None) -> list[dict]:
    """
    Walk the document once and collect the spreads, recording for each the
    baseline cut its mode produces. Single pages (portrait aspect ratio) are
    left out — they are passed through unsplit and have no cut to place.

    Done up front so the browser can show total page counts and jump around
    freely. Only the gutter search runs here; the image bytes are decoded
    again per request rather than held, so a 200-page book costs one page of
    memory at a time.
    """
    pages: list[dict] = []
    for i in range(len(doc)):
        img, _ = load_page_image(doc, doc[i])
        w, h = img.size
        if w / h <= SPREAD_RATIO:
            continue
        if fixed_x is None:
            mode_x, warning = find_gutter(img)
        else:
            mode_x, warning = fixed_x, None
        pages.append({
            "page": i + 1,
            "width": w,
            "height": h,
            "mode_x": mode_x,
            "warning": warning,
        })
    return pages


def write_overrides(path: Path, pages: list[int], overrides: dict[int, int]) -> None:
    """
    Rewrite the manifest in full: the same comment header and the same
    one-row-per-split-page shape split_spreads.py writes, with each page's
    current offset filled in and pages without one left blank.

    Rewriting wholesale rather than appending keeps the file canonical after
    hundreds of small edits, and keeps it readable and hand-editable — this
    tool is an alternative way to write the manifest, not a different format.
    """
    lines = [
        "# Per-page cut corrections, applied automatically on every run.",
        "# Set offset_px on any page whose cut is wrong, then re-run.",
        "# offset_px = pixel shift at the page's native resolution,",
        "# relative to that page's red line in the debug image;",
        "# positive = right, negative = left. A blank offset means",
        "# reviewed, no correction needed.",
        "# page,offset_px",
    ]
    for page in pages:
        offset = overrides.get(page)
        lines.append(f"{page}," if offset is None else f"{page},{offset}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


class AdjustState:
    """
    Everything the request handlers share: the open document, the spread
    index, and the offsets recorded so far.

    The PDF and the manifest are both touched from handler threads, so all
    access goes through the lock — pymupdf documents are not thread-safe,
    and two overlapping saves could otherwise interleave a half-written
    manifest.
    """

    def __init__(self, doc: pymupdf.Document, pages: list[dict],
                 manifest_path: Path, overrides: dict[int, int],
                 preview_width: int):
        self.doc = doc
        self.pages = pages
        self.by_number = {p["page"]: p for p in pages}
        self.manifest_path = manifest_path
        self.overrides = overrides
        self.preview_width = preview_width
        self.lock = threading.Lock()

    def preview_jpeg(self, page_num: int) -> bytes:
        """Decode one spread and re-encode it small enough to page through."""
        with self.lock:
            img, _ = load_page_image(self.doc, self.doc[page_num - 1])
        if img.width > self.preview_width:
            height = round(img.height * self.preview_width / img.width)
            img = img.resize((self.preview_width, height), Image.LANCZOS)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=80)
        return buf.getvalue()

    def set_offset(self, page_num: int, offset: int | None) -> None:
        """
        Record (or clear) one page's offset and flush the whole manifest.

        Saving on every drag rather than on exit means a browser closed
        mid-review, or a Ctrl-C, loses nothing — the file on disk is always
        what the screen shows.
        """
        with self.lock:
            if offset is None:
                self.overrides.pop(page_num, None)
            else:
                self.overrides[page_num] = offset
            write_overrides(self.manifest_path,
                            [p["page"] for p in self.pages],
                            self.overrides)

    def index_payload(self) -> dict:
        return {
            "pages": [
                {**p, "offset": self.overrides.get(p["page"])}
                for p in self.pages
            ],
            "manifest": str(self.manifest_path),
        }


PAGE_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>adjust_spreads</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; background: #16181c; color: #e8e8ea;
         font: 13px/1.5 ui-sans-serif, system-ui, sans-serif; }
  header { display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
           padding: 10px 16px; background: #1e2127;
           border-bottom: 1px solid #2c3038; position: sticky; top: 0; z-index: 5; }
  .nav button { background: #2c3038; color: #e8e8ea; border: 1px solid #3a3f49;
                border-radius: 5px; padding: 4px 11px; font-size: 13px; cursor: pointer; }
  .nav button:hover { background: #363b45; }
  .nav button:disabled { opacity: 0.4; cursor: default; }
  #where { font-weight: 600; min-width: 150px; }
  #status { color: #9aa0aa; }
  #status b { color: #e8e8ea; font-weight: 600; }
  .swatch { display: inline-block; width: 9px; height: 9px; border-radius: 2px;
            margin-right: 5px; vertical-align: baseline; }
  .red { background: #dc1e1e; } .blue { background: #2882dc; }
  #warn { color: #e0a030; }
  #saved { color: #4caf6a; opacity: 0; transition: opacity 0.25s; }
  #saved.on { opacity: 1; }
  #stage { position: relative; display: inline-block; margin: 16px;
           cursor: ew-resize; user-select: none; }
  #stage img { display: block; max-width: calc(100vw - 32px); height: auto; }
  .line { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px;
          pointer-events: none; }
  .line span { position: absolute; top: 8px; left: 6px; padding: 1px 5px;
               border-radius: 3px; font-size: 11px; white-space: nowrap;
               color: #fff; }
  #mode { background: #dc1e1e; } #mode span { background: #dc1e1e; }
  #cut  { background: #2882dc; } #cut span  { background: #2882dc; top: 30px; }
  #cut.hidden { display: none; }
  footer { padding: 4px 16px 20px; color: #7d838d; }
  kbd { background: #2c3038; border: 1px solid #3a3f49; border-radius: 3px;
        padding: 0 4px; font-family: inherit; font-size: 11px; }
</style>
</head>
<body>
<header>
  <span class="nav">
    <button id="prev">&larr;</button>
    <button id="next">&rarr;</button>
  </span>
  <span id="where"></span>
  <span id="status"></span>
  <span id="warn"></span>
  <span id="saved">saved</span>
</header>

<div id="stage">
  <img id="spread" alt="">
  <div class="line" id="mode"><span id="modelabel"></span></div>
  <div class="line hidden" id="cut"><span id="cutlabel"></span></div>
</div>

<footer>
  <span class="swatch red"></span>baseline &nbsp;
  <span class="swatch blue"></span>cut &nbsp;&nbsp;|&nbsp;&nbsp;
  drag or click to place the cut &nbsp;&nbsp;
  <kbd>&larr;</kbd><kbd>&rarr;</kbd> page &nbsp;
  <kbd>,</kbd><kbd>.</kbd> nudge 1px &nbsp;
  <kbd>&lt;</kbd><kbd>&gt;</kbd> nudge 10px &nbsp;
  <kbd>r</kbd> reset &nbsp;
  <kbd>u</kbd> next unreviewed
</footer>

<script>
let PAGES = [], idx = 0;
const img = document.getElementById("spread"),
      stage = document.getElementById("stage"),
      modeLine = document.getElementById("mode"),
      cutLine = document.getElementById("cut");

// The offset is stored at the page's native resolution, but everything on
// screen is a downscaled preview, so every read and write of a screen x
// goes through the displayed width -- never the preview width, which is
// itself scaled again by max-width on narrow windows.
const cur = () => PAGES[idx];
const nativeCutX = p => p.mode_x * p.width + (p.offset ?? 0);

function draw() {
  const p = cur();
  document.getElementById("where").textContent =
    `page ${p.page}  (${idx + 1}/${PAGES.length})`;
  document.getElementById("warn").textContent =
    p.warning ? `detection: ${p.warning}` : "";

  const w = img.clientWidth || 1;
  modeLine.style.left = (p.mode_x * w) + "px";
  document.getElementById("modelabel").textContent = p.mode_x.toFixed(4);

  if (p.offset === null || p.offset === undefined) {
    cutLine.classList.add("hidden");
    document.getElementById("status").innerHTML = "no override";
  } else {
    const frac = nativeCutX(p) / p.width;
    cutLine.classList.remove("hidden");
    cutLine.style.left = (frac * w) + "px";
    document.getElementById("cutlabel").textContent =
      `${frac.toFixed(4)}  ${p.offset >= 0 ? "+" : ""}${p.offset}px`;
    document.getElementById("status").innerHTML =
      `offset <b>${p.offset >= 0 ? "+" : ""}${p.offset}px</b>`;
  }
  document.getElementById("prev").disabled = idx === 0;
  document.getElementById("next").disabled = idx === PAGES.length - 1;
}

function show(i) {
  idx = Math.max(0, Math.min(PAGES.length - 1, i));
  img.src = `/image/${cur().page}`;
  draw();
}

let savedTimer = null;
function flashSaved() {
  const el = document.getElementById("saved");
  el.classList.add("on");
  clearTimeout(savedTimer);
  savedTimer = setTimeout(() => el.classList.remove("on"), 700);
}

// Drags fire far faster than the disk should be written, so the wire is
// kept to one in-flight save per page: the newest value waits its turn and
// any value superseded while waiting is simply dropped, since only the
// final resting place of the line is worth recording.
let inflight = false, pending = null;
async function save(page, offset) {
  pending = { page, offset };
  if (inflight) return;
  inflight = true;
  while (pending) {
    const body = pending; pending = null;
    await fetch("/offset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    flashSaved();
  }
  inflight = false;
}

function setOffset(offset) {
  const p = cur();
  p.offset = offset;
  draw();
  save(p.page, offset);
}

function offsetFromClientX(clientX) {
  const p = cur(), rect = img.getBoundingClientRect();
  const frac = Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1);
  return Math.round(frac * p.width - p.mode_x * p.width);
}

let dragging = false;
stage.addEventListener("pointerdown", e => {
  dragging = true;
  stage.setPointerCapture(e.pointerId);
  setOffset(offsetFromClientX(e.clientX));
});
stage.addEventListener("pointermove", e => {
  if (dragging) setOffset(offsetFromClientX(e.clientX));
});
stage.addEventListener("pointerup", e => {
  dragging = false;
  stage.releasePointerCapture(e.pointerId);
});

function nudge(px) { setOffset((cur().offset ?? 0) + px); }

document.addEventListener("keydown", e => {
  // The coarse nudge is shift+comma / shift+period. Test for the shift
  // modifier rather than for the shifted characters "<" and ">": which
  // character those keys produce is layout-dependent, and some senders
  // report the unshifted key with shiftKey set. The key/code pair covers
  // both how a browser reports a real keystroke and how a synthetic one
  // arrives.
  const isComma  = e.key === "," || e.key === "<" || e.code === "Comma";
  const isPeriod = e.key === "." || e.key === ">" || e.code === "Period";
  const step = e.shiftKey ? 10 : 1;

  if (isComma)  { nudge(-step); e.preventDefault(); return; }
  if (isPeriod) { nudge(step);  e.preventDefault(); return; }

  switch (e.key) {
    case "ArrowLeft":  show(idx - 1); break;
    case "ArrowRight": show(idx + 1); break;
    case "r": case "R": setOffset(null); break;
    case "u": case "U": {
      const next = PAGES.findIndex((p, i) =>
        i > idx && (p.offset === null || p.offset === undefined));
      if (next !== -1) show(next);
      break;
    }
    default: return;
  }
  e.preventDefault();
});

document.getElementById("prev").onclick = () => show(idx - 1);
document.getElementById("next").onclick = () => show(idx + 1);
// The lines are positioned from the image's displayed width, so they have
// to be re-placed whenever that width changes -- on load and on resize.
img.addEventListener("load", draw);
window.addEventListener("resize", draw);

fetch("/index").then(r => r.json()).then(data => {
  PAGES = data.pages;
  document.title = `adjust_spreads — ${PAGES.length} spreads`;
  show(0);
});
</script>
</body>
</html>
"""


def make_handler(state: AdjustState):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            # Previews are regenerated per request and offsets change as you
            # drag, so nothing here may be cached.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler's naming)
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(200, PAGE_HTML.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/index":
                body = json.dumps(state.index_payload()).encode("utf-8")
                self._send(200, body, "application/json")
            elif path.startswith("/image/"):
                try:
                    page_num = int(path.rsplit("/", 1)[1])
                except ValueError:
                    self._send(400, b"bad page", "text/plain")
                    return
                if page_num not in state.by_number:
                    self._send(404, b"not a spread", "text/plain")
                    return
                self._send(200, state.preview_jpeg(page_num), "image/jpeg")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            if urllib.parse.urlparse(self.path).path != "/offset":
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                payload = json.loads(self.rfile.read(length))
                page_num = int(payload["page"])
                raw = payload.get("offset")
                offset = None if raw is None else int(raw)
            except (ValueError, KeyError, TypeError):
                self._send(400, b"bad payload", "text/plain")
                return
            if page_num not in state.by_number:
                self._send(404, b"not a spread", "text/plain")
                return
            state.set_offset(page_num, offset)
            self._send(200, b'{"ok":true}', "application/json")

        def log_message(self, *args):
            # One line per drag would bury the startup banner and the
            # Ctrl-C hint under thousands of 200s.
            pass

    return Handler


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Place spread cut positions by dragging them in a browser, "
                    "writing the result to overrides.csv.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="Path to the assembled spreads PDF (e.g. scan_composite.pdf).")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--detect", action="store_true",
                      help="Baseline each spread at its own detected gutter, exactly "
                           "as split_spreads.py --detect does.")
    mode.add_argument("--fixed", type=float, default=None, metavar="FRAC",
                      help="Baseline every spread at this fixed fraction of width "
                           "(e.g. 0.5173), exactly as split_spreads.py --fixed does.")

    p.add_argument("--debug-dir", type=Path, default=DEFAULT_DEBUG_DIR, metavar="DIR",
                   help=f"Directory holding {MANIFEST_NAME} — the same manifest "
                        f"split_spreads.py reads and writes, so corrections made here "
                        f"apply to the next split (default {DEFAULT_DEBUG_DIR}).")
    p.add_argument("--preview-width", type=int, default=DEFAULT_PREVIEW_WIDTH,
                   metavar="PX",
                   help="Width in pixels to downscale spreads to for display. Offsets "
                        "are always recorded at native resolution regardless "
                        f"(default {DEFAULT_PREVIEW_WIDTH}).")
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"Port to serve on (default {DEFAULT_PORT}).")
    p.add_argument("--no-browser", action="store_true",
                   help="Print the URL but don't open a browser automatically.")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.fixed is not None and not 0.0 < args.fixed < 1.0:
        raise SystemExit(
            f"--fixed must be a fraction of width strictly between 0 and 1 "
            f"(e.g. 0.5173), got {args.fixed}"
        )

    doc = pymupdf.open(str(args.input))
    print(f"Input: {args.input} ({len(doc)} pages)")
    print("Indexing spreads ...")
    pages = build_page_index(doc, args.fixed)
    if not pages:
        raise SystemExit(
            f"No spreads found in {args.input} — every page is below the "
            f"{SPREAD_RATIO} width/height threshold, so there is nothing to cut."
        )

    manifest_path = args.debug_dir / MANIFEST_NAME
    overrides = read_manifest(manifest_path) if manifest_path.exists() else {}
    if overrides:
        print(f"Loaded {len(overrides)} existing offsets from {manifest_path}")

    # Write the manifest up front, so the file exists (and lists every spread)
    # even if the session is closed without dragging anything.
    write_overrides(manifest_path, [p["page"] for p in pages], overrides)

    state = AdjustState(doc, pages, manifest_path, overrides, args.preview_width)

    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port),
                                                 make_handler(state))
    except OSError as exc:
        raise SystemExit(
            f"Could not listen on port {args.port}: {exc}. "
            f"Another adjust_spreads may already be running — "
            f"pass a different --port."
        ) from exc

    url = f"http://127.0.0.1:{args.port}/"
    print(f"\n{len(pages)} spreads ready. Serving at {url}")
    print(f"Writing offsets to {manifest_path} as you drag.")
    print("Ctrl-C when done, then run split_spreads.py to produce the split PDF.\n")
    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\nStopped. {len(overrides)} offsets recorded in {manifest_path}.")
    finally:
        server.server_close()
        doc.close()


if __name__ == "__main__":
    main()
