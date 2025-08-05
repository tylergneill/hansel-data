#!/usr/bin/env python3
"""
transform_plaintext_to_tei.py

Plain‑text → TEI‑XML converter **plus post‑processor** (lxml‑based).

* Milestones (`<pb/>`, `<lb/>`) stay **inside** paragraphs/lines (TEI‑conformant)
* Optional `--pretty` flag invokes `lxml.etree.indent()` *after* conversion for
  human‑readable indentation.  No custom whitespace hacks.

Usage
-----
```bash
python transform_plaintext_to_tei.py hansel.txt hansel.xml           # minimal
python transform_plaintext_to_tei.py hansel.txt hansel.xml --pretty  # extra newlines for human reading
```
"""

import argparse
import html
import re
from pathlib import Path
from typing import Optional
from lxml import etree

_XML_NS = "http://www.w3.org/XML/1998/namespace"
_TAB = "\t"
_RE_BAR_NUM = re.compile(r"\|\|\s*(\d+)\s*\|\|\s*$")
_RE_SINGLE_BAR = re.compile(r"\|\s*$")

# ───────────────── helpers ─────────────────

def _make_xml_id(label: str) -> str:
    label = label.strip()
    if "," in label:
        page, line = map(str.strip, label.split(",", 1))
        if page and line:
            return f"p{page}_l{line}"
    return "p" + re.sub(r"\W+", "_", label)


def _serialize(root: etree._Element, pretty: bool) -> str:
    if pretty and hasattr(etree, "indent"):
        etree.indent(root, space="  ")  # lxml ≥ 4.5
    return etree.tostring(root, encoding="unicode", pretty_print=pretty)

# ───────────── post‑processing ─────────────

def _remove_lb_before_pb(root):
    for lb in root.xpath('.//lb'):
        nxt = lb.getnext()
        if nxt is not None and nxt.tag == 'pb':
            lb.getparent().remove(lb)


def _move_trailing_pb(root):
    for pb in list(root.xpath('.//pb')):
        parent = pb.getparent()
        if parent is not None and parent.tag == 'p' and parent[-1] is pb:
            grand = parent.getparent()
            parent.remove(pb)
            grand.insert(grand.index(parent) + 1, pb)


def _fix_hyphen_join(root):
    for tag in ('lb', 'pb'):
        for el in root.xpath(f'.//{tag}'):
            prev = el.getprevious()
            candidate = prev
            if prev is not None and prev.tag == 'caesura':
                candidate = prev.getprevious()
            # Candidate may be None (milestone is first child)
            if candidate is not None and candidate.tail and candidate.tail.endswith('-'):
                candidate.tail = candidate.tail[:-1]
                el.set('break', 'no')
                continue
            if candidate is not None and candidate.text and candidate.text.endswith('-'):
                candidate.text = candidate.text[:-1]
                el.set('break', 'no')
                continue
            parent = el.getparent()
            if parent is not None and parent.text and parent.text.endswith('-'):
                parent.text = parent.text[:-1]
                el.set('break', 'no')

def post_process(root):
    _remove_lb_before_pb(root)
    _move_trailing_pb(root)
    _fix_hyphen_join(root)

# ───────────── transformer / builder ────────────

def build_tei(src_path: Path) -> etree._Element:
    root = etree.Element('TEI', nsmap={'xml': _XML_NS})
    body = etree.SubElement(root, 'body')

    container = body
    current_p = current_lg = current_l = None
    text_parent = body
    lb_counter = 2

    def _open_paragraph(meta: str):
        nonlocal current_p, current_lg, current_l, text_parent
        current_lg = current_l = None
        current_p = etree.SubElement(container, 'p', attrib={f'{{{_XML_NS}}}id': _make_xml_id(meta), 'n': meta})
        text_parent = current_p

    def _open_lg():
        nonlocal current_lg, current_l, text_parent
        current_lg = etree.SubElement(current_p, 'lg')
        current_l = etree.SubElement(current_lg, 'l')
        text_parent = current_l

    def _ensure_l():
        nonlocal current_l, text_parent
        if current_l is None and current_lg is not None:
            current_l = etree.SubElement(current_lg, 'l')
            text_parent = current_l

    for raw in src_path.read_text(encoding='utf-8').splitlines():
        line = raw.rstrip('\n')

        # Section div
        if (m := re.match(r'^\{([^}]+)\}', line)):
            container = etree.SubElement(body, 'div', attrib={f'{{{_XML_NS}}}id': m.group(1).strip()})
            current_p = current_lg = current_l = None
            text_parent = container
            line = line[m.end():].lstrip()
            if not line:
                continue

        # Paragraph marker
        if (m := re.match(r'^\[([^]]+)\]', line)):
            _open_paragraph(m.group(1).strip())
            line = line[m.end():].lstrip()
            if not line:
                continue

        # Page break milestone
        if (m := re.match(r'^<([^>]+)>', line)):
            if text_parent is None:
                _open_paragraph('implicit')
            assert text_parent is not None
            etree.SubElement(text_parent, 'pb', attrib={'n': m.group(1).strip()})
            lb_counter = 2
            line = line[m.end():].lstrip()
            if not line:
                continue

        if not line.strip():
            continue

        # Verse vs prose
        is_tabbed = line.startswith(_TAB)
        if is_tabbed:
            line = line.lstrip(_TAB)
            if current_lg is None:
                _open_lg()
            else:
                _ensure_l()
        else:
            if current_p is None:
                _open_paragraph('implicit')
            text_parent = current_p

        # Bar analysis
        close_l = False
        num_match = _RE_BAR_NUM.search(line)
        single_match = _RE_SINGLE_BAR.search(line) if not num_match else None
        if num_match:
            current_lg.set('n', num_match.group(1))
            close_l = True
        elif single_match:
            close_l = True

        # Append text
        escaped = html.escape(line, quote=False)
        if text_parent.text is None:
            text_parent.text = escaped
        else:
            last = text_parent[-1] if len(text_parent) else None
            if last is not None:
                last.tail = (last.tail or '') + escaped
            else:
                text_parent.text += escaped

        # Caesura
        if is_tabbed and not (num_match or single_match):
            etree.SubElement(text_parent, 'caesura')

        # Line break milestone
        assert text_parent is not None
        etree.SubElement(text_parent, 'lb', attrib={'n': str(lb_counter)})
        lb_counter += 1

        if close_l:
            current_l = None
            text_parent = current_lg if current_lg is not None else current_p

    return root

# ─────────────────────────── CLI ───────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert custom plaintext to TEI‑XML.')
    parser.add_argument('src', help='input plaintext file')
    parser.add_argument('out', help='output TEI‑XML file')
    parser.add_argument('-p', '--pretty', action='store_true', help='indent block elements for readability')
    args = parser.parse_args()

    root_tree = build_tei(Path(args.src))
    post_process(root_tree)

    xml_output = _serialize(root_tree, pretty=args.pretty)
    # extra readability tweak: add newline after every <pb/> or <lb/> when pretty-printing
    if args.pretty:
        xml_output = re.sub(r'(<[lp]b[^>]*?>)([^\n])', r"\1\n\2", xml_output)
    Path(args.out).write_text(xml_output, encoding='utf-8')
    print(f'Wrote {args.out}')
