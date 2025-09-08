"""
TEI builder

Renders the HANSEL data model (lightly marked plaintext)
into a simplified TEI-XML form (<div>, <p>, <lg>/<l>, <pb>, <cb>, <lb>, <head>, <back>, <note>).

Primary elements:
1) Section markers {...} (own line only) → <div> (flat, never nested).
2) Location markers [...] ... → either <p> or <lg> (latter can nest x1).
3) Tab → <lg>/<l>
4) Page markers <page[-col][,line]> → <pb>, (<cb>, <lb>) (n attribute)
5) Line-end newline → <lb> (n attribute as counted on book page)
6) Notes (...) → <note> (those that disrupt author's natural-language flow)

<pb>, <cb>, <lb> milestones are placed at line-end, anticipating the next line.

Secondary features:
6) Line-end hyphen → "break=no" attribute (<pb>, <cb>, <lb>)
8) Verse-line-end lack of punctuation → "type=caesura" attribute (<pb>, <cb>, <lb>)
9) Groups of verses → top-level <lg> for "paragraph", second-level <lg> for each verse
10) Same-line material preceding or following verse → <head>, <back>.

Text can appear in:
- element.text: <p>, <l>, <head>, <back>, <note>
- element.tail: <pb>, <cb>, <lb>, <note>

This module focuses on a single linear pass with localized helpers.
Serialization and post-processing are handled one level up, in tei_utils.
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
SECTION_RE = re.compile(r"^{([^}]+)}\s*$")
LOCATION_VERSE_RE = re.compile(r"^\[([^\]]+?)\]\t*(.*)$")  # [label] +/- tabbed verse content
VERSE_NUM_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)*)\s*([a-z]{1,4})?\s*$", re.I)
PAGE_RE = re.compile(r"^<(\d+)>$")  # <page>
PAGE_LINE_RE = re.compile(r"^<(\d+),(\d+)>$")  # <page,line>
ADDITIONAL_STRUCTURE_NOTE_RE = re.compile(r"^<[^\n>]+>$")  # other <...>
VERSE_MARKER_RE = re.compile(r"\|\| ([^|]{1,20}) \|\|(?: |$)")
VERSE_BACK_BOUNDARY_RE = re.compile(r"\|\|? (?![^|]{1,20} \|\|)")
CLOSE_L_RE = re.compile(r"\|\|?(?:[ \n]|$)")
HYPHEN_EOL_RE = re.compile(r"-\s*$")  # tweak later if you need fancy hyphens


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
            page_id = page.replace(".", "_")
            line_id = line_no.replace(".", "_")
            return f"p{page_id}_l{line_id}"
    cleaned = re.sub(r"\W+", "_", s)
    return f"v{cleaned}" if cleaned else "v"

# ----------------------------
# State container
# ----------------------------
@dataclass
class BuildState:
    verse_only: bool = False
    line_by_line: bool = False

    # DOM pointers
    root: etree._Element = field(default_factory=lambda: etree.Element("TEI", nsmap={"xml": _XML_NS}))
    body: etree._Element = field(init=False)
    current_div: etree._Element = field(init=False)
    current_p: Optional[etree._Element] = None
    current_lg: Optional[etree._Element] = None
    current_l: Optional[etree._Element] = None
    current_caesura: Optional[etree._Element] = None
    prev_line_hyphen: bool = False

    # Counters
    lb_count: int = 0  # counts since last <pb>
    explicit_page: Optional[str] = None

    # bookkeeping for multi-line under same location
    current_loc_label: Optional[str] = None  # e.g., "1.1ab"
    current_loc_base: Optional[str] = None  # e.g., "1.1"
    current_loc_xml_id: Optional[str] = None
    extra_p_suffix: int = 1  # for subsequent <p> after a finished <lg>
    last_emitted_lb: Optional[etree._Element] = None

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
    def __init__(self, verse_only: bool = False, line_by_line: bool = False):
        self.state = BuildState(
            verse_only=verse_only,
            line_by_line=line_by_line
        )

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
            s.last_text_sink = None
            return

        # 2a) Page marker <page_num> / <page_num,line_num>
        page_line_match = PAGE_LINE_RE.match(line)
        if page_line_match:
            self._emit_pb(page_line_match.group(1), page_line_match.group(2))
            return
        page_match = PAGE_RE.match(line)
        if page_match:
            self._emit_pb(page_match.group(1), None)
            return

        # 2b) Other structural note <...> to be counted as physical line
        additional_structure_note_match = ADDITIONAL_STRUCTURE_NOTE_RE.match(line)
        if additional_structure_note_match:
            self._emit_milestone(additional_structure_note_match.group(0))
            return

        # 2c) TODO: Other structural note (...) not to be counted as physical line

        # 3) Location marker [label] +/- tabbed verse-only content
        location_match = LOCATION_VERSE_RE.match(line)
        if location_match:
            label, rest = location_match.group(1).strip(), location_match.group(2)

            if s.verse_only:
                self._handle_verse_only_line(label, rest)
                return
            else:
                self._open_location(label)
                return

        # HANDLE LINES WITH CONTENT (AND MAYBE ALSO STRUCTURE)

        # <head>[TAB]verse[bar+space]<back>
        if '\t' in line:
            self._handle_verse_line(line)
            # Verse lines do not currently emit <lb> milestones
            s.prev_line_hyphen = bool(HYPHEN_EOL_RE.search(line))
            return

        # Else, if we are inside a <p>, append text to that <p>
        if s.current_p is not None:
            text_to_append = HYPHEN_EOL_RE.sub("", line)
            if not HYPHEN_EOL_RE.search(line):
                text_to_append += " "
            self._append(s.current_p, text_to_append)
            self._finalize_physical_line(line)
            return

        # shouldn't reach this
        raise Exception(f"end of _handle_line reached: {line}")

    # ---- helpers ----
    def _finalize_physical_line(self, raw_line: str) -> None:
        s = self.state
        # For prose, emit an <lb/> after the line's text has been appended
        if s.current_p is not None:
            s.lb_count += 1
            container = self._get_container()
            attrs = {"n": str(s.lb_count)}
            if HYPHEN_EOL_RE.search(raw_line):
                attrs["break"] = "no"
            lb = etree.SubElement(container, "lb", attrs)
            s.last_emitted_lb = lb
            s.last_text_sink = lb

        s.prev_line_hyphen = bool(HYPHEN_EOL_RE.search(raw_line))

    def _append(self, default_el: etree._Element, text: str, *, tail_ok: bool = True) -> None:
        """Append `text` to the right place, honoring last_text_sink and join-space logic."""
        if not text:
            return
        s = self.state

        sink_el = default_el
        use_tail = False
        if tail_ok and s.last_text_sink is not None:
            sink_el = s.last_text_sink
            use_tail = True

        prefix = ""
        if use_tail and not s.prev_line_hyphen:
            prefix = " "

        if use_tail:
            sink_el.tail = (sink_el.tail or "") + prefix + text
        else:
            sink_el.text = (sink_el.text or "") + text

    def _handle_verse_only_line(self, label, rest):
        s = self.state
        base, seg = self._parse_verse_label(label)
        self._open_or_switch_lg_for_label(base, group_by_base=True)

        if s.current_l is None:
            if seg:
                s.current_l = etree.SubElement(s.current_lg, "l", {"n": seg})
            else:
                s.current_l = etree.SubElement(s.current_lg, "l")
        if rest:
            stripped = rest.rstrip()
            self._append_text(s.current_l, stripped)
            s.last_text_sink = s.current_l
            if CLOSE_L_RE.search(stripped):
                s.current_l = None
        return

    def _handle_verse_line(self, line):
        s = self.state
        pre_tab, after_tab = line.split("\t", 1)
        pre_tab = pre_tab.rstrip()

        verse_payload = after_tab
        back_text = ""

        m_marker = None
        for m in VERSE_MARKER_RE.finditer(after_tab):
            m_marker = m
        if m_marker:
            verse_payload = after_tab[: m_marker.end()].rstrip(" ")
            back_text = after_tab[m_marker.end():]
        else:
            m_back = VERSE_BACK_BOUNDARY_RE.search(after_tab)
            if m_back:
                start = m_back.start()
                bars = "||" if after_tab[start:start + 2] == "||" else "|"
                verse_payload = after_tab[:start] + bars
                back_text = after_tab[m_back.end():]

        self._open_or_switch_lg_for_label(s.current_loc_label or "v", group_by_base=False)
        lg = s.current_lg

        if pre_tab.strip():
            self._append_singleton_child_text(lg, "head", pre_tab)

        if s.current_l is None:
            s.current_l = etree.SubElement(lg, "l")

        payload_stripped = verse_payload.rstrip()
        is_line_close = bool(CLOSE_L_RE.search(payload_stripped))

        if is_line_close:
            if s.current_caesura is not None:
                self._append_text(s.current_caesura, payload_stripped, tail=True)
                s.last_text_sink = s.current_caesura
            else:
                self._append_text(s.current_l, payload_stripped)
                s.last_text_sink = s.current_l
            s.current_l = None
            s.current_caesura = None
        else:
            self._append_text(s.current_l, payload_stripped)
            s.current_caesura = etree.SubElement(s.current_l, "caesura")
            s.last_text_sink = s.current_caesura

        if back_text and back_text.strip():
            self._append_singleton_child_text(lg, "back", back_text)

        return

    def _open_div(self, label: str) -> None:
        s = self.state
        self._close_p()
        self._close_lg()
        div = etree.SubElement(s.body, "div", {"n": label})
        s.current_div = div
        s.current_loc_label = None
        s.current_loc_xml_id = None
        s.extra_p_suffix = 1

    def _get_container(self):
        s = self.state
        if s.current_lg is not None:
            return s.current_lg
        elif s.current_p is not None:
            return s.current_p
        else:
            return s.current_div

    def _emit_pb(self, page: str, line_no: Optional[str]) -> None:
        s = self.state
        container = self._get_container()

        attrs = {"n": page}
        if s.last_emitted_lb is not None and s.last_emitted_lb.getparent() == container:
            if s.last_emitted_lb.get("break") == "no":
                attrs["break"] = "no"
            container.remove(s.last_emitted_lb)

        pb = etree.SubElement(container, "pb", attrs)
        s.last_emitted_lb = None
        s.last_text_sink = pb

        s.explicit_page = page
        if line_no is not None:
            try:
                s.lb_count = int(line_no) - 1
            except ValueError:
                s.lb_count = 0
        else:
            s.lb_count = 0

    def _emit_milestone(self, label: str) -> None:
        s = self.state
        container = self._get_container()
        etree.SubElement(container, "milestone", {"n": label})

    def _open_location(self, label: str) -> None:
        s = self.state
        self._close_p()
        self._close_lg()
        s.current_loc_label = label
        s.current_loc_xml_id = make_xml_id(label)
        if "," in label and not s.verse_only:
            try:
                _page, line_no = map(str.strip, label.split(",", 1))
                s.lb_count = int(line_no)
            except (ValueError, IndexError):
                pass
        s.extra_p_suffix = 1
        s.current_p = etree.SubElement(
            s.current_div, "p", {f"{{{_XML_NS}}}id": s.current_loc_xml_id, "n": label}
        )
        s.last_text_sink = None # Set to None so first append goes to .text
        s.prev_line_hyphen = False # Reset for new paragraph

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
        existing = next((ch for ch in parent if ch.tag == tag), None)
        if existing is None:
            el = etree.SubElement(parent, tag)
            el.text = text.strip()
        else:
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
