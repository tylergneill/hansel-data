#!/usr/bin/env python3
"""Page through a PDF in Preview at a fixed rate, without raising its window.

Opens the PDF in the background (open -g), then every DELAY
seconds scrolls Preview's view to the next page through the accessibility API,
starting from whatever page is showing and stopping after the last page or on
Ctrl-C. Set Preview to View > Single Page so each step shows one whole page.

The terminal running this needs Accessibility access (System Settings >
Privacy & Security > Accessibility).

Usage:
    python flip_preview.py book.pdf DELAY=2
    python flip_preview.py book.pdf 1.5
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

# Preview titles a document window "<file> – Page N of M".
TITLE_RE = re.compile(r"Page (\d+) of (\d+)")

WINDOW = """
on findWindow(fname)
    tell application "System Events" to tell process "Preview"
        repeat with w in windows
            if name of w starts with fname then return w
        end repeat
    end tell
    error "no Preview window for " & fname
end findWindow
"""

TITLE = WINDOW + """
on run argv
    tell application "System Events" to return name of my findWindow(item 1 of argv)
end run
"""

GOTO = WINDOW + """
on run argv
    set w to my findWindow(item 1 of argv)
    tell application "System Events"
        -- The page view is the scroll area holding a group; the thumbnail
        -- sidebar, when shown, is a scroll area holding a list.
        repeat with sa in scroll areas of splitter group 1 of w
            if exists group 1 of sa then
                perform action "AXScrollToVisible" of UI element ((item 2 of argv) as integer) of group 1 of sa
                return
            end if
        end repeat
    end tell
    error "no page view in the Preview window"
end run
"""


def osascript(script, *args):
    res = subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip())
    return res.stdout.strip()


def current_page(fname, wait=10.0):
    """Return (page, pages) from the PDF's Preview window title, waiting for it to open."""
    deadline = time.monotonic() + wait
    while True:
        try:
            m = TITLE_RE.search(osascript(TITLE, fname))
            if m:
                return int(m.group(1)), int(m.group(2))
        except RuntimeError:
            pass
        if time.monotonic() > deadline:
            sys.exit(f"could not read the page number of {fname} in Preview")
        time.sleep(0.3)


def parse_delay(arg):
    value = arg.split("=", 1)[1] if arg.upper().startswith("DELAY=") else arg
    delay = float(value)
    if delay <= 0:
        raise argparse.ArgumentTypeError("DELAY must be positive")
    return delay


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("delay", nargs="?", type=parse_delay, default=2.0,
                    metavar="DELAY=SECONDS", help="seconds per page (default 2)")
    args = ap.parse_args()

    if not args.pdf.is_file():
        sys.exit(f"no such file: {args.pdf}")

    subprocess.run(["open", "-g", "-a", "Preview", str(args.pdf)], check=True)
    fname = args.pdf.name
    page, pages = current_page(fname)
    print(f"page {page} of {pages}, flipping every {args.delay:g}s; Ctrl-C to stop")

    # Pace against a fixed schedule so the osascript round trip (~0.5s)
    # doesn't stretch every step.
    due = time.monotonic()
    try:
        while page < pages:
            due += args.delay
            time.sleep(max(0.0, due - time.monotonic()))
            page += 1
            osascript(GOTO, fname, str(page))
            print(f"\rpage {page} of {pages}", end="", flush=True)
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        sys.exit(f"\n{e}")
    print()


if __name__ == "__main__":
    main()
