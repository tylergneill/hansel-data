"""
TEI builder (proposed rewrite)

Implements the clarified rules discussed on 2025‑08‑09 for transforming a
lightly marked plaintext into TEI with <div>, <p>, <lg>/<l>, <pb>, and <lb>.

Key points implemented here:

1) Section markers {…} → <div> (own line only; flat unless you extend it).
2) Location markers […] usually open a new block (prose <p>), BUT may also
   open verse (<lg>) if the first substantial content line (ignoring purely
   blank lines) after the marker contains a TAB anywhere. Text BEFORE the first
   TAB on that line becomes <head> within that <lg>.
   (NOTE: […] itself never resets lb counting.)
3) Page markers <page> and <page,line> are recognized start-of-line or mid-line.
   They emit <pb n="page"/>, and ONLY <pb> affects line break numbering.
   <page,line> sets lb_count to the explicit line number BEFORE next <lb>.
4) In --line-by-line mode, each physical input line emits <lb n="…"/> BEFORE
   any verse/prose payload for that line (i.e., <lb> precedes <l> or text).
   If the raw line ends with a hyphen, set break="no" on that lb.
   Prose text for the same physical line is appended to the *tail* of that lb.
5) Verse segmentation:
   • End of <l> is signaled by a trailing '|' or '||' (no trailing space).
   • If a segment does NOT end with '|' or '||', append <caesura/>
     inside the <l>.
   • A trailing "| " (bar + space) ends the verse *for that line* and the
     remainder of the physical line becomes <back> within the same <lg>, but
     ONLY if there is non-empty content after the space.
   • Verse under a […] block ends either at "| " OR at the next section/location
     marker on a later line. If subsequent lines continue and they are prose,
     we close the <lg> and open a new <p> (xml:id for that new <p> reuses the
     same n=label but adds a suffix "_p2", "_p3", ...).

This module focuses on a single linear pass with localized helpers and a short
post-process to fix easy edge cases. You can extend/replace the post-processing
according to downstream constraints.

NOTE: This file is designed to minimize dependencies on the outer driver.
It does not perform serialization. Use lxml.etree.tostring elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from lxml import etree

_XML_NS = "http://www.w3.org/XML/1998/namespace"

# ----------------------------
# Regexes (compiled once)
# ----------------------------
SECTION_RE = re.compile(r"^\{([^}]+)\}\s*$")
LOCATION_VERSE_RE = re.compile(r"^\[([^\]]+?)\]\t*(.*)$")  # [label] then tabbed verse content
VERSE_NUM_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)*)\s*([a-z]{1,4})?\s*$", re.I)
LOCATION_RE = re.compile(r"^\[([^\]]+?)\]\$")  # [label] by itself on line
PAGE_RE = re.compile(r"^<(\d+)>$")  # <page>
PAGE_LINE_RE = re.compile(r"^<(\d+),(\d+)>$")  # <page,line>
VERSE_MARKER_RE = re.compile(r"\|\| ([^|]{1,20}) \|\|(?: |$)")
VERSE_BACK_BOUNDARY_RE = re.compile(r"\|\|? (?![^|]{1,20} \|\|)")
CLOSE_L_RE = re.compile(r"\|\|?(?:[ \n]|$)")


# ----------------------------
# Utility helpers
# ----------------------------

def make_xml_id(label: str) -> str:
    """Create an XML-safe @xml:id from a label.
    Special case: "page,line" → p{page}_{line}
    Otherwise, prefix with 'v' and replace non-word chars with '_'.
    """
    s = label.strip()
    if "," in s:
        page, line_no = map(str.strip, s.split(",", 1))
        if page and line_no:
            page_id = page.replace('.', '_')
            line_id = line_no.replace('.', '_')
            return f"p{page_id}_l{line_id}"
    cleaned = re.sub(r"\W+", "_", s)
    return f"v{cleaned}" if cleaned else "v"

# ----------------------------
# State container
# ----------------------------
@dataclass
class BuildState:
    verse_only: bool = False
    line_by_line: bool = True

    # DOM pointers
    root: etree._Element = field(default_factory=lambda: etree.Element("TEI", nsmap={"xml": _XML_NS}))
    body: etree._Element = field(init=False)
    current_div: etree._Element = field(init=False)
    current_p: Optional[etree._Element] = None
    current_lg: Optional[etree._Element] = None
    current_l: Optional[etree._Element] = None
    current_caesura: Optional[etree._Element] = None

    # Counters
    lb_count: int = 0  # counts since last <pb>
    explicit_page: Optional[str] = None

    # bookkeeping for multi-line under same location
    current_loc_label: Optional[str] = None  # e.g., "1.1ab"
    current_loc_base: Optional[str] = None  # e.g., "1.1"
    current_loc_xml_id: Optional[str] = None
    extra_p_suffix: int = 1  # for subsequent <p> after a finished <lg>

    # text sink: most recent inline element (e.g., <lb/>) whose tail should
    # receive following prose text on the same physical line
    last_text_sink: Optional[etree._Element] = None

    def __post_init__(self):
        self.body = etree.SubElement(self.root, "body")
        self.current_div = self.body

# ----------------------------
# Builder class
# ----------------------------
class TEIBuilder:
    def __init__(self, verse_only: bool = False, line_by_line: bool = True):
        self.state = BuildState(verse_only=verse_only, line_by_line=line_by_line)

    def build(self, lines: List[str]) -> etree._Element:
        for raw in lines:
            self._handle_line(raw.rstrip("\n"))
        return self.state.root

    # ---- per-line handler ----
    def _handle_line(self, line: str) -> None:
        if not line.strip():
            return
        s = self.state

        # HANDLE STRUCTURE-ONLY LINES

        # 1) Section marker {label}
        section_match = SECTION_RE.match(line)
        if section_match:
            self._open_div(section_match.group(1))
            # new physical line ends: clear tail sink
            s.last_text_sink = None
            return

        # 2) Page marker <page_num> / <page_num,line_num>
        page_line_match = PAGE_LINE_RE.match(line)
        if page_line_match:
            self._emit_pb(page_line_match.group(1), page_line_match.group(2))
            return
        page_match = PAGE_RE.match(line)
        if page_match:
            self._emit_pb(page_match.group(1), None)
            return

        # 3) Location marker [label]
        location_match = LOCATION_VERSE_RE.match(line)
        if location_match:
            label, rest = location_match.group(1).strip(), location_match.group(2)

            # --verse-only mode: use <lg> and expect content on same line like [label]\tCONTENT
            if s.verse_only:
                self._handle_verse_only_line(label, rest)
                return

            # default mode: use <p>, content will not be on same line
            else:
                self._open_location(label)
                return

        # HANDLE LINES WITH CONTENT (AND MAYBE ALSO STRUCTURE)

        # <head>[TAB]verse[bar+space]<back>
        if '\t' in line:
            self._handle_verse_line(line)
            return

        # Else, if we are inside a <p>, append text to that <p>
        if s.current_p is not None:
            self._append_text(s.current_p, line)
            s.last_text_sink = s.current_p
            return

        # shouldn't reach this
        raise(f"end of _handle_line reached: {line}")

    # ---- helpers ----
    def _handle_verse_only_line(self, label, rest):
        s = self.state
        base, seg = self._parse_verse_label(label)
        self._open_or_switch_lg_for_label(base, group_by_base=True)

        # If no open <l>, start one; attach segment to @n if present
        if s.current_l is None:
            if seg:
                s.current_l = etree.SubElement(s.current_lg, "l", {"n": seg})
            else:
                s.current_l = etree.SubElement(s.current_lg, "l")
        # Append same-line content (if any)
        if rest:
            stripped = rest.rstrip()
            self._append_text(s.current_l, rest)
            s.last_text_sink = s.current_l
            # If this segment ends with '|' or '||', the <l> is complete.
            if CLOSE_L_RE.search(stripped):
                s.current_l = None
        return

    def _handle_verse_line(self, line):
        s = self.state
        pre_tab, after_tab = line.split("\t", 1)
        pre_tab = pre_tab.rstrip()

        verse_payload = after_tab
        back_text = ""

        # 1) Prefer numeric verse marker (VERSE_MARKER_RE)
        m_marker = None
        for m in VERSE_MARKER_RE.finditer(after_tab):
            m_marker = m
        if m_marker:
            verse_payload = after_tab[: m_marker.end()].rstrip(" ")
            back_text = after_tab[m_marker.end():]
        else:
            # 2) Else simple back boundary (VERSE_BACK_BOUNDARY_RE)
            m_back = VERSE_BACK_BOUNDARY_RE.search(after_tab)
            if m_back:
                start = m_back.start()
                bars = "||" if after_tab[start:start + 2] == "||" else "|"
                verse_payload = after_tab[:start] + bars
                back_text = after_tab[m_back.end():]

        # Ensure we have an <lg> for the current location (default mode = full label grouping)
        self._open_or_switch_lg_for_label(s.current_loc_label or "v", group_by_base=False)
        lg = s.current_lg

        # <head> (only if non-empty)
        if pre_tab.strip():
            self._append_singleton_child_text(lg, "head", pre_tab)

        # Start a new <l> only if there isn't one already open
        if s.current_l is None:
            s.current_l = etree.SubElement(lg, "l")

        # Append verse payload with caesura handling
        payload_stripped = verse_payload.rstrip()
        is_line_close = bool(CLOSE_L_RE.search(payload_stripped))  # ends with '|' or '||'

        if is_line_close:
            # If mid-line after caesura, append to caesura tail; else to <l>.text
            if s.current_caesura is not None:
                self._append_text(s.current_caesura, payload_stripped, tail=True)
                s.last_text_sink = s.current_caesura
            else:
                self._append_text(s.current_l, payload_stripped)
                s.last_text_sink = s.current_l

            # Close the <l> for the next verse line
            s.current_l = None
            s.current_caesura = None
        else:
            # Continuing same <l>: append payload and insert a <caesura/> for continuation
            self._append_text(s.current_l, payload_stripped)
            s.current_caesura = etree.SubElement(s.current_l, "caesura")
            s.last_text_sink = s.current_caesura

        # <back> (only if there's content after the boundary)
        if back_text and back_text.strip():
            self._append_singleton_child_text(lg, "back", back_text)

        return

    def _open_div(self, label: str) -> None:
        s = self.state
        # Close any open p/lg implicitly
        self._close_p()
        self._close_lg()
        # FLAT: append to <body>, not to the previous <div>
        div = etree.SubElement(s.body, "div", {"n": label})
        s.current_div = div
        # Reset location bookkeeping when a new div starts
        s.current_loc_label = None
        s.current_loc_xml_id = None
        s.extra_p_suffix = 1

    def _emit_pb(self, page: str, line_no: Optional[str]) -> None:
        s = self.state
        # Ensure we are inside a container
        container = s.current_lg or s.current_p or s.current_div
        etree.SubElement(container, "pb", {"n": page})
        s.explicit_page = page
        # Reset lb_count only on page; set to line_no-1 so that next lb becomes that number
        if line_no is not None:
            try:
                s.lb_count = int(line_no) - 1
            except ValueError:
                s.lb_count = 0
        else:
            s.lb_count = 0

    def _open_location(self, label: str) -> None:
        s = self.state
        # Close any open p/lg for previous location
        self._close_p()
        self._close_lg()
        s.current_loc_label = label
        s.current_loc_xml_id = make_xml_id(label)
        s.extra_p_suffix = 1
        # Default: open a fresh <p>; may be upgraded to <lg> if TAB appears
        s.current_p = etree.SubElement(
            s.current_div, "p", {f"{{{_XML_NS}}}id": s.current_loc_xml_id, "n": label}
        )

    def _parse_verse_label(self, raw: str) -> tuple[str, Optional[str]]:
        """
        Returns (base, segment). If no match, treat whole label as base.
        Examples:
          "1.1ab" -> ("1.1", "ab")
          "1.1 cd" -> ("1.1", "cd")
          "2.3" -> ("2.3", None)
        """
        verse_label_match = VERSE_NUM_RE.match(raw)
        if not verse_label_match:
            return raw.strip(), None
        base, seg = verse_label_match.group(1), verse_label_match.group(2)
        return base.strip(), (seg.lower() if seg else None)

    def _open_or_switch_lg_for_label(self, label: str, *, group_by_base: bool = True) -> None:
        s = self.state
        if group_by_base:
            base, _seg = self._parse_verse_label(label)
            need_base = base
        else:
            need_base = label.strip()

        # already in correct lg?
        if s.current_lg is not None and s.current_loc_base == need_base:
            s.current_loc_label = label
            return

        self._close_lg()
        s.current_loc_base = need_base
        s.current_loc_label = label
        lg_id = "v" + re.sub(r"\W+", "_", need_base)
        s.current_lg = etree.SubElement(s.current_div, "lg", {
            "n": need_base,
            f"{{{_XML_NS}}}id": lg_id
        })
        s.current_l = None

    def _append_text(self, el, text: str, tail: bool=False) -> None:
        if not text:
            return
        if tail:
            if el.tail:
                el.tail += text
            else:
                el.tail = text
        else:
            if el.text:
                el.text += text
            else:
                el.text = text

    def _append_singleton_child_text(self, parent, tag: str, text: str) -> None:
        if not text or not text.strip():
            return
        # find first existing child with this tag
        existing = next((ch for ch in parent if ch.tag == tag), None)
        if existing is None:
            el = etree.SubElement(parent, tag)
            el.text = text.strip()
        else:
            # append with a separating space
            if existing.text:
                existing.text += " " + text.strip()
            else:
                existing.text = text.strip()

    def _close_p(self) -> None:
        s = self.state
        if s.current_p is not None:
            s.current_p = None

    def _close_lg(self) -> None:
        s = self.state
        if s.current_lg is not None:
            s.current_lg = None
