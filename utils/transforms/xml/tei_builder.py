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
Serialization and post-processing are handled one level up.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from lxml import etree

_XML_NS = "http://www.w3.org/XML/1998/namespace"

# ----------------------------
# Regexes (compiled once)
# ----------------------------

from tei_builder_regexes import *

# ----------------------------
# Utility helpers
# ----------------------------

def make_xml_id(label: str) -> str:
    """Create an XML-safe @xml:id from a label.
    Special case: \"page,line\" → p{page}_{line}
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
    last_tail_text_sink: Optional[etree._Element] = None

    # verse group buffer
    verse_group_buffer: List[etree._Element] = field(default_factory=list)

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
        self._flush_verse_group_buffer()
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
            s.last_tail_text_sink = None
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
            self._finalize_physical_line(line)
            return

        # 2c) TODO: Other structural note (...) not to be counted as physical line

        # 3) Location marker [label] +/- tabbed verse-only content
        location_match = LOCATION_VERSE_RE.match(line)
        if location_match:
            label, rest = location_match.group(1).strip(), location_match.group(2)

            if s.verse_only:
                self._handle_verse_only_line(label, rest)
                self._finalize_physical_line(line)
                return
            else:
                self._open_location(label)
                return

        # HANDLE LINES WITH CONTENT (AND MAYBE ALSO STRUCTURE)

        # verse (<head>[TAB]verse[bar+space]<back>)
        if '\t' in line:
            self._handle_verse_line(line)
            self._finalize_physical_line(line)
            return

        # prose
        if s.current_p is not None:
            self._process_content_with_midline_elements(line, "prose", raw_line_for_hyphen_check=line)
            self._finalize_physical_line(line)
            return

        # shouldn't reach this
        raise Exception(f"end of _handle_line reached: {line}")

    # ---- helpers ----
    def _emit_lb(self, container: etree._Element, raw_line: str = "") -> etree._Element:
        s = self.state
        s.lb_count += 1
        attrs = {"n": str(s.lb_count)}
        if raw_line and HYPHEN_EOL_RE.search(raw_line):
            attrs["break"] = "no"
        lb = etree.SubElement(container, "lb", attrs)
        s.last_emitted_lb = lb
        return lb

    def _finalize_physical_line(self, raw_line: str) -> None:
        s = self.state
        s.prev_line_hyphen = bool(HYPHEN_EOL_RE.search(raw_line))

    def _append(self, text: str) -> None:
        """Append `text` to the right place, honoring last_tail_text_sink and join-space logic."""
        if not text:
            return
        s = self.state

        sink_el = s.last_tail_text_sink
        use_tail = True

        if sink_el is None:
            if s.current_l is not None:
                sink_el = s.current_l
                use_tail = False
            elif s.current_p is not None:
                sink_el = s.current_p
                use_tail = False
            else:
                return

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
            attrs = {}
            if seg:
                attrs["n"] = seg
            s.current_l = etree.SubElement(s.current_lg, "l", attrs)
            s.last_tail_text_sink = None

        self._process_content_with_midline_elements(rest, "verse", rest)

    def _handle_verse_line(self, line: str) -> None:
        s = self.state
        self._close_p()

        pre_tab, after_tab = line.split("\t", 1)
        pre_tab = pre_tab.rstrip()

        if s.verse_only:
            lg = self._open_or_switch_lg_for_label(s.current_loc_label or "v", group_by_base=True)
            if pre_tab.strip():
                self._append_singleton_child_text(lg, "head", pre_tab)
            if s.current_l is None:
                s.current_l = etree.SubElement(lg, "l")
                s.last_tail_text_sink = None
            self._process_content_with_midline_elements(after_tab, "verse", line)
            return

        if s.current_lg is None:
            lg = etree.Element("lg")
            if pre_tab.strip():
                self._append_singleton_child_text(lg, "head", pre_tab)
            s.current_lg = lg

        if s.current_l is None:
            s.current_l = etree.SubElement(s.current_lg, "l")
            s.last_tail_text_sink = None

        verse_payload = after_tab
        back_text = ""

        # Use COMBINED_VERSE_END_RE to find the last verse marker on the line
        last_match = None
        for m in COMBINED_VERSE_END_RE.finditer(after_tab):
            last_match = m

        if last_match:
            verse_payload = after_tab[:last_match.end()]
            back_text = after_tab[last_match.end():]

        is_verse_close = self._process_content_with_midline_elements(verse_payload, "verse", line)

        if back_text and back_text.strip():
            self._append_singleton_child_text(s.current_lg, "back", back_text)

        if is_verse_close:
            if s.current_lg is not None and not s.verse_only:
                s.verse_group_buffer.append(s.current_lg)
            s.current_lg = None
            s.current_l = None

    def _emit_pb_from_match(self, match: re.Match):
        page, line_num = match.groups()
        self._emit_pb(page, line_num)

    def _process_content_with_midline_elements(self, content: str, mode: str, raw_line_for_hyphen_check: str):
        s = self.state
        
        markers = [
            (MID_LINE_PAGE_RE, self._emit_pb_from_match)
        ]
        
        all_matches = []
        for marker_re, handler in markers:
            for match in marker_re.finditer(content):
                all_matches.append({"match": match, "handler": handler})
                
        all_matches.sort(key=lambda x: x["match"].start())
        
        last_match_end = 0
        for item in all_matches:
            match = item["match"]
            handler = item["handler"]
            
            pre_text = content[last_match_end:match.start()]
            self._append(pre_text)
            
            handler(match)
            
            last_match_end = match.end()

        post_text = content[last_match_end:]
        post_text = HYPHEN_EOL_RE.sub("", post_text)
        self._append(post_text)

        if mode == "prose":
            if not HYPHEN_EOL_RE.search(content):
                self._append(" ")

            if s.line_by_line:
                lb = self._emit_lb(s.current_p, raw_line_for_hyphen_check)
                s.last_tail_text_sink = lb
            else:
                if not len(s.current_p):
                    s.last_tail_text_sink = None
    
        elif mode == "verse":
            is_line_close = (bool(CLOSE_L_RE.search(post_text.rstrip())))
            is_verse_close = (bool(COMBINED_VERSE_END_RE.search(post_text.rstrip())))

            if not is_line_close and content:
                s.current_caesura = etree.SubElement(s.current_l, "caesura")
                s.last_tail_text_sink = s.current_caesura
            else:
                s.current_caesura = None

            if s.line_by_line:
                lb = self._emit_lb(s.current_l, raw_line_for_hyphen_check)
                s.last_tail_text_sink = lb
            elif s.current_caesura is None:
                s.last_tail_text_sink = None

            if is_line_close:
                s.current_l = None

            return is_verse_close

    def _open_div(self, label: str) -> None:
        s = self.state
        self._flush_verse_group_buffer()
        self._close_p()
        self._close_lg()
        div = etree.SubElement(s.body, "div", {"n": label})
        s.current_div = div
        s.current_loc_label = None
        s.current_loc_xml_id = None
        s.extra_p_suffix = 1

    def _get_container(self):
        s = self.state
        if s.current_l is not None:
            return s.current_l
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

        # If last thing emitted was <lb>, replace it with this <pb>
        if s.last_emitted_lb is not None:
            lb_parent = s.last_emitted_lb.getparent()
            if lb_parent is not None:
                container = lb_parent
                if s.last_emitted_lb.get("break") == "no":
                    attrs["break"] = "no"
                lb_parent.remove(s.last_emitted_lb)
        elif not s.line_by_line:
            # Fallback for when no <lb> are emitted.
            # Try to find the last <l> or <p> in the current div and append there.
            last_elem_list = s.current_div.xpath('(.//l | .//p)[last()]')
            if last_elem_list:
                container = last_elem_list[0]

        pb = etree.SubElement(container, "pb", attrs)
        s.last_emitted_lb = None
        s.last_tail_text_sink = pb

        s.explicit_page = page
        if line_no is not None:
            try:
                s.lb_count = int(line_no) - 1
            except ValueError:
                s.lb_count = 0
        else:
            s.lb_count = 1

    def _emit_milestone(self, label: str) -> None:
        s = self.state
        container = self._get_container()
        etree.SubElement(container, "milestone", {"n": label})

    def _open_location(self, label: str) -> None:
        s = self.state
        self._flush_verse_group_buffer()
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
        s.last_tail_text_sink = None # Set to None so first append goes to .text
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

    def _open_or_switch_lg_for_label(self, label: str, *, group_by_base: bool = True) -> etree._Element:
        s = self.state
        if group_by_base:
            base, _seg = self._parse_verse_label(label)
            need_base = base
        else:
            need_base = label.strip()

        if s.current_lg is not None and s.current_loc_base == need_base:
            s.current_loc_label = label
            return s.current_lg

        if s.current_p is not None and not s.current_p.text and not len(s.current_p):
            s.current_p.getparent().remove(s.current_p)
            s.current_p = None

        self._close_lg()
        s.current_loc_base = need_base
        s.current_loc_label = label
        lg_id = "v" + re.sub(r"\W+", "_", need_base)
        
        if s.verse_only:
            container = s.current_div
            lg = etree.SubElement(container, "lg", {
                "n": need_base,
                f"{{{_XML_NS}}}id": lg_id
            })
        else:
            lg = etree.Element("lg", {
                "n": need_base,
                f"{{{_XML_NS}}}id": lg_id
            })

        s.current_lg = lg
        s.current_l = None
        return lg

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
            if not s.current_p.text and not len(s.current_p):
                parent = s.current_p.getparent()
                if parent is not None:
                    parent.remove(s.current_p)
            s.current_p = None

    def _close_lg(self) -> None:
        s = self.state
        self._flush_verse_group_buffer()
        if s.current_lg is not None:
            s.current_lg = None
            s.current_l = None

    def _flush_verse_group_buffer(self):
        s = self.state
        if not s.verse_group_buffer:
            return

        if len(s.verse_group_buffer) > 1:
            # Create a parent lg and move the children
            parent_lg = etree.SubElement(s.current_div, "lg", {
                "type": "group",
                "n": s.current_loc_label,
                f"{{{_XML_NS}}}id": s.current_loc_xml_id
            })
            for child_lg in s.verse_group_buffer:
                parent_lg.append(child_lg)
        else:
            # Just add the single lg
            single_lg = s.verse_group_buffer[0]
            single_lg.set(f"{{{_XML_NS}}}id", s.current_loc_xml_id)
            single_lg.set("n", s.current_loc_label)
            s.current_div.append(single_lg)

        s.verse_group_buffer.clear()
