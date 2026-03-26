"""Post-process HTML files to produce unspaced variants.

Walks all text nodes in a generated HTML file and applies Skrutable's
avoid_virama_non_indic_scripts transform (IAST→IAST with inter-word spaces
removed). Elements with the following classes are skipped, mirroring the
exclusions in hansel-app's rich_script.js:

    pb-label, lb-label, editorial-coord, hyphen

Usage:
    python unspace_html.py <input.html> <output.html>
"""

import argparse
import re
from pathlib import Path
from lxml import etree
from skrutable.transliteration import Transliterator

SKIP_CLASSES = {"pb-label", "lb-label", "editorial-coord", "hyphen"}

T = Transliterator(from_scheme='IAST', to_scheme='IAST')


def _should_skip(element):
    classes = set(element.get("class", "").split())
    return bool(classes & SKIP_CLASSES)


def _unspace(text):
    if not text:
        return text
    return T.transliterate(text, avoid_virama_non_indic_scripts=True)


def _process_node(element):
    """Recursively unspace text nodes, skipping excluded elements.

    Note on tails: in lxml, child.tail is text that follows the child's closing
    tag but belongs to the parent's flow. We always unspace tails regardless of
    whether the child element itself is skipped, because the tail is Sanskrit
    content in the parent context, not part of the skipped element.
    """
    if _should_skip(element):
        return

    if element.text:
        element.text = _unspace(element.text)

    for child in element:
        _process_node(child)
        if child.tail:
            child.tail = _unspace(child.tail)


def unspace_html_file(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw = input_path.read_text(encoding="utf-8")

    # The generated HTML files are fragments (no <html>/<body>), so parse as a
    # fragment. lxml wraps fragments in <div> when using fragment_fromstring.
    root = etree.fromstring(f"<root>{raw}</root>")

    _process_node(root)

    # Serialize back, stripping the <root> wrapper we added.
    inner = (root.text or "")
    for child in root:
        inner += etree.tostring(child, encoding="unicode", method="html")
        if child.tail:
            inner += child.tail

    output_path.write_text(inner, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate unspaced HTML from a spaced HTML file.")
    parser.add_argument("input", help="Input HTML file path")
    parser.add_argument("output", help="Output HTML file path")
    args = parser.parse_args()

    unspace_html_file(args.input, args.output)
    print(f"Written: {args.output}")
