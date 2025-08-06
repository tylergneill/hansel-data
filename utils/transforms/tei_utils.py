"""
tei_utils.py – shared helpers for the plaintext → TEI converter.
Keeps munging utilities and post-processing in one place so the main
script stays focused on parsing logic.
"""

import re
from lxml import etree

# Public constant ------------------------------------------------------------

_XML_NS = "http://www.w3.org/XML/1998/namespace"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def make_xml_id(label: str) -> str:
    """
    Create an XML-safe @xml:id from a human label.

    Examples
    --------
    >>> make_xml_id("1.1,17")
    'p1.1_17'
    >>> make_xml_id("intro")
    'pintro'
    """
    label = label.strip().replace(".", "_")
    if "," in label:
        page, line = map(str.strip, label.split(",", 1))
        if page and line:
            return f"p{page}_l{line.replace('.', '_')}"
    return "v" + re.sub(r"\W+", "_", label)


def serialize(root: etree._Element, pretty_print: bool = True) -> str:
    """Return the XML tree as a Unicode string; indent when *pretty* is True."""
    if pretty_print and hasattr(etree, "indent"):          # lxml ≥ 4.5
        etree.indent(root, space="  ")
    return etree.tostring(root, encoding="unicode", pretty_print=pretty_print)

# ---------------------------------------------------------------------------
# Post-processing helpers
# ---------------------------------------------------------------------------

def _remove_lb_before_pb(root: etree._Element) -> None:
    for lb in root.xpath(".//lb"):
        nxt = lb.getnext()
        if nxt is not None and nxt.tag == "pb":
            lb.getparent().remove(lb)


def _move_trailing_pb(root: etree._Element) -> None:
    for pb in list(root.xpath(".//pb")):
        parent = pb.getparent()
        if parent is not None and parent.tag == "p" and parent[-1] is pb:
            parent.remove(pb)
            parent.getparent().insert(parent.getparent().index(parent) + 1, pb)


def _fix_hyphen_join(root: etree._Element) -> None:
    """
    If a line ends with a hyphen that’s merely a break marker,
    remove the hyphen and add break="no" to the milestone.
    """
    for tag in ("lb", "pb"):
        for el in root.xpath(f".//{tag}"):
            prev = el.getprevious()
            candidate = prev
            if prev is not None and prev.tag == "caesura":
                candidate = prev.getprevious()

            # Tail on sibling
            if candidate is not None and candidate.tail and candidate.tail.endswith("-"):
                candidate.tail = candidate.tail[:-1]
                el.set("break", "no")
                continue

            # Text on sibling
            if candidate is not None and candidate.text and candidate.text.endswith("-"):
                candidate.text = candidate.text[:-1]
                el.set("break", "no")
                continue

            # Text on parent (milestone is first child)
            parent = el.getparent()
            if parent is not None and parent.text and parent.text.endswith("-"):
                parent.text = parent.text[:-1]
                el.set("break", "no")


def post_process(root: etree._Element) -> None:
    """Run all formatting clean-ups in place."""
    _remove_lb_before_pb(root)
    _move_trailing_pb(root)
    _fix_hyphen_join(root)


__all__ = [
    "_XML_NS",
    "make_xml_id",
    "serialize",
    "post_process",
]
