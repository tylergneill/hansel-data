#!/usr/bin/env python3
"""
transform_plaintext_to_tei.py

CLI wrapper around the core *build_tei()* transformer.  Parsing logic lives
here; helper utilities are imported from **tei_utils.py**.

Enhancement (2025-08-05)
-----------------------
* In `--verse-only` mode the segment letters ("ab", "cd", …) are now stored on
  each `<l>` as `@n`, e.g. `<l n="ab">…`.
"""

import argparse
import html
import re
from pathlib import Path
from typing import Optional
from lxml import etree

from tei_utils import _XML_NS, make_xml_id, serialize, post_process

_TAB = "\t"  # leading tab indicates verse line in mixed mode
_RE_BAR_NUM = re.compile(r"\|\|\s*(\d+)\s*\|\|\s*$")  # || 12 ||
_RE_SINGLE_BAR = re.compile(r"\|\s*$")                      # … |

# ───────────── core transformer ────────────

def build_tei(src_path: Path, *, verse_only: bool = False) -> etree._Element:
    """Parse *src_path* into a TEI XML tree."""

    root = etree.Element("TEI", nsmap={"xml": _XML_NS})
    body = etree.SubElement(root, "body")

    # Parser state -----------------------------------------------------------
    container = body               # current <div> parent
    current_p: Optional[etree._Element] = None
    current_lg: Optional[etree._Element] = None
    current_l: Optional[etree._Element] = None
    current_verse_num: Optional[str] = None  # numeric part (e.g. 1.1)
    segment_letters: str = ""                 # letters part (e.g. ab, cd)
    text_parent: etree._Element = body
    lb_counter = 2

    # Helpers ----------------------------------------------------------------
    def _open_paragraph(meta: str) -> None:
        nonlocal current_p, current_lg, current_l, text_parent, current_verse_num
        current_lg = current_l = None
        current_verse_num = meta if verse_only else None
        current_p = etree.SubElement(
            container,
            "p",
            attrib={f"{{{_XML_NS}}}id": make_xml_id(meta), "n": meta},
        )
        text_parent = current_p
        if verse_only:
            _open_lg()

    def _open_lg() -> None:
        nonlocal current_lg, current_l, text_parent
        if current_p is None:
            _open_paragraph("implicit")
        current_lg = etree.SubElement(current_p, "lg")
        if verse_only and current_verse_num:
            current_lg.set("n", current_verse_num)
        _open_new_l()  # always create first <l>

    def _open_new_l() -> None:
        nonlocal current_l, text_parent
        if current_lg is None:
            _open_lg()
        attrib = {"n": segment_letters} if verse_only and segment_letters else {}
        current_l = etree.SubElement(current_lg, "l", attrib=attrib)
        text_parent = current_l

    # ----------------------------------------------------------------------
    for raw in src_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")

        # Section <div>
        if (m := re.match(r"^\{([^}]+)\}", line)):
            container = etree.SubElement(
                body, "div", attrib={f"{{{_XML_NS}}}id": m.group(1).strip()}
            )
            current_p = current_lg = current_l = None
            current_verse_num = None
            text_parent = container
            line = line[m.end():].lstrip()
            if not line:
                continue

        # Paragraph / verse label ------------------------------------------
        if (m := re.match(r"^\[([^]]+)\]", line)):
            label = m.group(1).strip()
            if verse_only:
                m2 = re.match(r"^([0-9.]+)([a-z]*)$", label)
                verse_num, letters = m2.groups() if m2 else (label, "")
                segment_letters = letters or ""
                if letters.startswith("a") or current_p is None:
                    _open_paragraph(verse_num)
                else:
                    # continue existing lg, start new l for next segment
                    current_l = None
            else:
                _open_paragraph(label)
            # Remove label and leading tab (if any)
            after = line[m.end():]
            line = after[1:] if after.startswith(_TAB) else after.lstrip()
            if not line:
                continue
        else:
            # Not a label line – keep previous segment letters
            pass

        # Page-break milestone ---------------------------------------------
        if (m := re.match(r"^<([^>]+)>", line)):
            if text_parent is None:
                _open_paragraph("implicit")
            etree.SubElement(text_parent, "pb", attrib={"n": m.group(1).strip()})
            lb_counter = 2
            line = line[m.end():].lstrip()
            if not line:
                continue

        if not line.strip():
            continue  # skip blank

        # Verse / prose handling -------------------------------------------
        if verse_only:
            if current_l is None:
                _open_new_l()
        else:
            is_tabbed = line.startswith(_TAB)
            if is_tabbed:
                line = line.lstrip(_TAB)
                if current_lg is None:
                    _open_lg()
                elif current_l is None:
                    _open_new_l()
            else:
                if current_p is None:
                    _open_paragraph("implicit")
                text_parent = current_p

        # Bar analysis ------------------------------------------------------
        close_l = False
        num_match = _RE_BAR_NUM.search(line)
        single_match = _RE_SINGLE_BAR.search(line) if not num_match else None
        if num_match and not verse_only:
            current_lg.set("n", num_match.group(1))
            close_l = True
        elif single_match:
            close_l = True

        # Append escaped text ----------------------------------------------
        escaped = html.escape(line, quote=False)
        if text_parent.text is None:
            text_parent.text = escaped
        else:
            last_child = text_parent[-1] if len(text_parent) else None
            if last_child is not None:
                last_child.tail = (last_child.tail or "") + escaped
            else:
                text_parent.text += escaped

        # Caesura -----------------------------------------------------------
        if (verse_only or line.startswith(_TAB)) and not (num_match or single_match):
            etree.SubElement(text_parent, "caesura")

        # Line-break milestone ---------------------------------------------
        etree.SubElement(text_parent, "lb", attrib={"n": str(lb_counter)})
        lb_counter += 1

        if close_l:
            current_l = None
            text_parent = current_lg if current_lg is not None else current_p

    return root

# ──────────────────────── CLI entry ─────────────────────────

def _cli() -> None:
    ap = argparse.ArgumentParser(description="Convert custom plaintext to TEI-XML.")
    ap.add_argument("src", help="input plaintext file")
    ap.add_argument("out", help="output TEI-XML file")
    ap.add_argument("-p", "--pretty", action="store_true", help="indent block elements for readability")
    ap.add_argument("--verse-only", action="store_true", help="treat input as verse-only")
    args = ap.parse_args()

    tree = build_tei(Path(args.src), verse_only=args.verse_only)
    post_process(tree)

    xml_out = serialize(tree, pretty=args.pretty)
    if args.pretty:
        xml_out = re.sub(r"(<[lp]b?[^>]*?>)([^\n])", r"\1\n\2", xml_out)

    Path(args.out).write_text(xml_out, encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    _cli()