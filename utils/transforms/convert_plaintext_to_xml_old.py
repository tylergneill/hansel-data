#!/usr/bin/env python3
"""
convert_plaintext_to_xml.py
--------------------------
Transforms Śukasaptati‑style plaintext into TEI‑XML while honouring the original
CLI flags (`--uglier`, `--prettier`, `--verse-only`).

**2025‑08‑05 cleanup** – removed the now‑unused `text_parent` variable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The line‑by‑line logic already chooses a `target_node` each turn, so the extra
state was redundant. All assignments and the original declaration are gone.
Nothing else changed.
"""

import argparse
import html
import re
from pathlib import Path
from typing import Optional
from lxml import etree

from tei_utils import _XML_NS, make_xml_id, serialize, post_process

# ───────────────────────── constants & regexes ──────────────────────────────
_TAB = "\t"  # tab → verse
_RE_BAR_NUM = re.compile(r"(?:\u2022)?\|\|\s*([0-9.]+)\s*=\s*(\d+)\s*\|\|\u2022?", re.UNICODE)
_RE_SINGLE_BAR = re.compile(r"\|\s*$")
_LETTER_PAIRS = [chr(a) + chr(a + 1) for a in range(ord("a"), ord("z"), 2)]

# ─────────────────────────── parser builder ─────────────────────────────────

def build_tei(src: Path, *, verse_only: bool = False) -> etree._Element:
    root = etree.Element("TEI", nsmap={"xml": _XML_NS})
    body = etree.SubElement(root, "body")

    # mutable state ---------------------------------------------------------
    container = body              # current <div>
    current_p: Optional[etree._Element] = None
    current_lg: Optional[etree._Element] = None
    current_l: Optional[etree._Element] = None
    letter_index = 0
    lb_counter = 2

    # helper closures -------------------------------------------------------
    def _open_paragraph(label: str) -> None:
        nonlocal current_p, current_lg, current_l, letter_index
        current_lg = current_l = None
        letter_index = 0
        current_p = etree.SubElement(
            container,
            "p",
            attrib={f"{{{_XML_NS}}}id": make_xml_id(label), "n": label},
        )

    def _open_lg() -> None:
        nonlocal current_lg, current_l, letter_index
        if current_p is None:
            _open_paragraph("implicit")
        current_lg = etree.SubElement(current_p, "lg")
        letter_index = 0
        _open_new_l()

    def _next_letters() -> str:
        nonlocal letter_index
        if letter_index >= len(_LETTER_PAIRS):
            letter_index = 0
        pair = _LETTER_PAIRS[letter_index]
        letter_index += 1
        return pair

    def _open_new_l() -> None:
        nonlocal current_l
        if current_lg is None:
            _open_lg()
        current_l = etree.SubElement(current_lg, "l", attrib={"n": _next_letters()})

    def _append_text(node: etree._Element, txt: str) -> None:
        if not txt:
            return
        escaped = html.escape(txt, quote=False)
        if node.text is None:
            node.text = escaped
        else:
            node.text += escaped

    # helper for tail text --------------------------------------------------
    def _append_after(prev: etree._Element, txt: str) -> None:
        if not txt:
            return
        escaped = html.escape(txt, quote=False)
        prev.tail = (prev.tail or "") + escaped

    # ─────────────────────────── main loop ────────────────────────────────
    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")

        # section / folio markers ------------------------------------------
        if (m := re.match(r"^\{([^}]+)\}", line)):
            container = etree.SubElement(body, "div", attrib={f"{{{_XML_NS}}}id": m.group(1).strip()})
            current_p = current_lg = current_l = None
            line = line[m.end():].lstrip()
            if not line:
                continue

        if (m := re.match(r"^\[([^]]+)\]", line)):
            _open_paragraph(m.group(1).strip())
            line = line[m.end():].lstrip()
            if not line:
                continue

        if (m := re.match(r"^<([^>]+)>", line)):
            if current_p is None:
                _open_paragraph("implicit")
            etree.SubElement(current_p, "pb", attrib={"n": m.group(1).strip()})
            lb_counter = 2
            line = line[m.end():].lstrip()
            if not line:
                continue

        if not line.strip():
            continue

        # split prose vs verse ---------------------------------------------
        pre_prose = ""
        if _TAB in line and not line.startswith(_TAB):
            pre_prose, line = line.split(_TAB, 1)
            pre_prose = pre_prose.rstrip()
            line = _TAB + line.lstrip()
            if pre_prose:
                if current_p is None:
                    _open_paragraph("implicit")
                _append_text(current_p, pre_prose)

        # detect verse milestone -------------------------------------------
        post_prose = ""
        bar_match = _RE_BAR_NUM.search(line)
        if bar_match and bar_match.end() < len(line):
            post_prose = line[bar_match.end():].lstrip()
            line = line[: bar_match.end()]

        is_verse = line.startswith(_TAB)
        if is_verse:
            line = line.lstrip(_TAB)
            if current_lg is None:
                _open_lg()
            elif current_l is None:
                _open_new_l()
            target_node = current_l
            append_to_tail = False
        else:
            if current_p is None:
                _open_paragraph("implicit")
            if len(current_p):
                target_node = current_p[-1]
                append_to_tail = True
            else:
                target_node = current_p
                append_to_tail = False

        # write line text ---------------------------------------------------
        if append_to_tail:
            _append_after(target_node, line)
        else:
            _append_text(target_node, line)

        # caesura -----------------------------------------------------------
        if is_verse and not bar_match and not _RE_SINGLE_BAR.search(line):
            etree.SubElement(target_node, "caesura")

        # line break --------------------------------------------------------
        # If the line ends a numbered verse (bar_match) **or** is pure prose,
        # the physical break belongs at the paragraph level. Otherwise it
        # belongs inside the current <l>.
        if bar_match or not is_verse:
            lb_container = current_p
        else:
            lb_container = current_l

        lb_elem = etree.SubElement(lb_container, "lb", attrib={"n": str(lb_counter)})
        lb_counter += 1

        closed_lg: Optional[etree._Element] = None
        if bar_match:
            current_l = None
            closed_lg = current_lg
            current_lg = None
        elif is_verse and _RE_SINGLE_BAR.search(line):
            current_l = None

        # prose after bar ---------------------------------------------------
        if post_prose:
            if closed_lg is not None:
                _append_after(closed_lg, post_prose)
            else:
                if len(current_p):
                    _append_after(current_p[-1], post_prose)
                else:
                    _append_text(current_p, post_prose)

    return root

# ─────────────────────────── CLI wrapper ───────────────────────────────────

def _cli() -> None:
    ap = argparse.ArgumentParser(description="Convert custom plaintext to TEI‑XML")
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("-u", "--uglier", action="store_true", help="compact (no indent)")
    ap.add_argument("-p", "--prettier", action="store_true", help="newline after lb/pb for readability")
    ap.add_argument("--verse-only", action="store_true", help="legacy verse‑only mode")
    args = ap.parse_args()

    tree = build_tei(Path(args.src), verse_only=args.verse_only)
    post_process(tree)
    xml = serialize(tree, pretty_print=not args.uglier)
    if args.prettier:
        xml = re.sub(r"(</?[lp][bg]?[^>]*?>)([^\n])", r"\1\n\2", xml)
    Path(args.out).write_text(xml, encoding="utf-8")
    print("Wrote", args.out)

if __name__ == "__main__":
    _cli()
