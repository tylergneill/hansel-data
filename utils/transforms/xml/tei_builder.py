
"""
TEI builder

Renders the HANSEL data model (lightly marked plaintext) into a simplified TEI-XML form:
<div>, <p>, <lg>/<l>, <pb>, <cb>, <lb>, <head>, <back>, <note>, <milestone>.

See DATA_MODEL.md for more details.
"""
import copy
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from lxml import etree

_XML_NS = "http://www.w3.org/XML/1998/namespace"

# ----------------------------
# Regexes
# ----------------------------

SECTION_RE = re.compile(r"^{([^}]+)}\s*$")
LOCATION_VERSE_RE = re.compile(r"^\[([^\]]+?)\]\t*(.*)$")  # [label] +/- tabbed verse content
VERSE_NUM_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)*)\s*([a-z]{1,4})?\s*$", re.I)
PAGE_RE = re.compile(r"^<(\d+)>$")  # <page>
PAGE_LINE_RE = re.compile(r"^<(\d+),(\d+)>$")  # <page,line>
ADDITIONAL_STRUCTURE_NOTE_RE = re.compile(r"^<[^\n>]+>$")  # other <...>
VERSE_MARKER_RE = re.compile(r"\|\| ([^|]{1,20}) \|\|(?: |$)")
CHOICE_RE = re.compile(r"≤([^≥]*)≥«([^»]*)»")
DEL_RE = re.compile(r"≤([^≥]*)≥")
SUPPLIED_RE = re.compile(r"«([^»]*)»")
UNCLEAR_RE = re.compile(r"¿([^¿]*)¿")
VERSE_BACK_BOUNDARY_RE = re.compile(r"\|\|(?![^|]{1,20} \|\|)")
CLOSE_L_RE = re.compile(r"\|\|?(?:[ \n]|$)")
HYPHEN_EOL_RE = re.compile(r"-\s*$")  # tweak later if you need fancy hyphens
MID_LINE_PAGE_RE = re.compile(r"<(\d+)(?:,(\d+))?>")
COMBINED_VERSE_END_RE = re.compile(f"{VERSE_MARKER_RE.pattern}|{VERSE_BACK_BOUNDARY_RE.pattern}")
CHAR_FOR_PENDING_HEAD = "_"
PENDING_HEAD_RE = re.compile(f"^(.*\|)\s*{re.escape(CHAR_FOR_PENDING_HEAD)}$")

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
class TextBuildState:
    verse_only: bool = False
    line_by_line: bool = False

    # DOM pointers
    root: etree._Element = field(default_factory=lambda: etree.Element(
        "TEI",
        nsmap={None: "http://www.tei-c.org/ns/1.0", "xml": _XML_NS}
    ))
    text: Optional[etree._Element] = None
    body: Optional[etree._Element] = None
    current_div: Optional[etree._Element] = None
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
    verse_group_buffer: list[etree._Element] = field(default_factory=list)

    # verse head buffer
    pending_head_elem: Optional[etree._Element] = None

# ----------------------------
# Builder class
# ----------------------------
class TeiTextBuilder:
    def __init__(self, verse_only: bool = False, line_by_line: bool = False):
        self.state = TextBuildState(
            verse_only=verse_only,
            line_by_line=line_by_line
        )
        self.state.text = etree.SubElement(self.state.root, "text")
        self.state.body = etree.SubElement(self.state.text, "body")
        self.state.current_div = self.state.body

    def build(self, lines: list[str]) -> etree._Element:
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

        # verse starter on its own line (e.g. "uktaṃ ca |_")
        pending_head_match = PENDING_HEAD_RE.search(line)
        if pending_head_match:
            self._close_p()
            head_text = pending_head_match.group(1).strip()
            head_elem = etree.Element("head")
            head_elem.text = head_text
            if s.line_by_line:
                self._emit_lb(head_elem, "")

            s.pending_head_elem = head_elem
            return

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
            if sink_el.tag in ('lb', 'pb'):
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

        if pre_tab.strip() and s.current_lg is not None:
            if not s.verse_only:
                s.verse_group_buffer.append(s.current_lg)
            s.current_lg = None
            s.current_l = None

        if s.verse_only:
            lg = self._open_or_switch_lg_for_label(s.current_loc_label or "v", group_by_base=True)
            if s.pending_head_elem is not None:
                lg.append(s.pending_head_elem)
                s.pending_head_elem = None
            if pre_tab.strip():
                self._append_child_text(lg, "head", pre_tab)
            if s.current_l is None:
                s.current_l = etree.SubElement(lg, "l")
                s.last_tail_text_sink = None
            self._process_content_with_midline_elements(after_tab, "verse", line)
            return

        if s.current_lg is None:
            lg = etree.Element("lg")
            if s.pending_head_elem is not None:
                lg.append(s.pending_head_elem)
                s.pending_head_elem = None
            if pre_tab.strip():
                self._append_child_text(lg, "head", pre_tab)
                pre_tab = ""
            s.current_lg = lg

        if s.current_l is None:
            if pre_tab.strip():
                self._append_child_text(s.current_lg, "head", pre_tab)
            s.current_l = etree.SubElement(s.current_lg, "l")
            s.last_tail_text_sink = None

        verse_payload = after_tab
        back_text = ""

        # find the last verse marker on the line
        last_match = None
        for m in COMBINED_VERSE_END_RE.finditer(after_tab):
            last_match = m

        if last_match:
            verse_payload = after_tab[:last_match.end()]
            back_text = after_tab[last_match.end():]

        is_verse_close = self._process_content_with_midline_elements(verse_payload, "verse", line)

        if back_text and back_text.strip():
            milestone_to_move = s.last_tail_text_sink
            back_el = self._append_child_text(s.current_lg, "back", back_text)
            if (
                    milestone_to_move is not None
                    and milestone_to_move.tag in ('lb', 'pb')
                    and back_el is not None
            ):
                parent = milestone_to_move.getparent()
                if parent is not None and parent.tag == 'l':
                    back_el.append(milestone_to_move)

        if is_verse_close:
            if s.current_lg is not None and not s.verse_only:
                s.verse_group_buffer.append(s.current_lg)
            s.current_lg = None
            s.current_l = None

    def _emit_pb_from_match(self, match: re.Match):
        page, line_num = match.groups()
        self._emit_pb(page, line_num)

    def _emit_choice(self, match: re.Match):
        choice = etree.Element("choice")
        sic = etree.SubElement(choice, "sic")
        sic.text = match.group(1)
        corr = etree.SubElement(choice, "corr")
        corr.text = match.group(2)
        self._add_inline_element(choice)

    def _emit_del(self, match: re.Match):
        del_el = etree.Element("del")
        del_el.text = match.group(1)
        self._add_inline_element(del_el)

    def _emit_supplied(self, match: re.Match):
        supplied = etree.Element("supplied")
        supplied.text = match.group(1)
        self._add_inline_element(supplied)

    def _emit_unclear(self, match: re.Match):
        unclear = etree.Element("unclear")
        unclear.text = match.group(1)
        self._add_inline_element(unclear)

    def _add_inline_element(self, el: etree._Element):
        s = self.state
        sink = s.last_tail_text_sink

        if sink is None:
            container = s.current_l if s.current_l is not None else s.current_p
            if container is not None:
                container.append(el)
        else:
            sink.addnext(el)

        s.last_tail_text_sink = el

    def _process_content_with_midline_elements(self, content: str, mode: str, raw_line_for_hyphen_check: str):
        s = self.state
        
        markers = [
            (MID_LINE_PAGE_RE, self._emit_pb_from_match),
            (CHOICE_RE, self._emit_choice),
            (DEL_RE, self._emit_del),
            (SUPPLIED_RE, self._emit_supplied),
            (UNCLEAR_RE, self._emit_unclear),
        ]
        
        all_matches = []
        for marker_re, handler in markers:
            for match in marker_re.finditer(content):
                all_matches.append({"match": match, "handler": handler})
                
        all_matches.sort(key=lambda x: (x["match"].start(), -x["match"].end()))

        filtered_matches = []
        last_end = -1
        for item in all_matches:
            if item['match'].start() >= last_end:
                filtered_matches.append(item)
                last_end = item['match'].end()

        last_match_end = 0
        for item in filtered_matches:
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
                # Check if the parent of the lb's container is the current div
                if lb_parent.getparent().tag == 'div' and lb_parent.getparent() is not s.current_div:
                    # if not, pb becomes sibling of the p/lg, not a child
                    pass
                else:
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

    def _append_child_text(self, parent, tag: str, text: str) -> Optional[etree._Element]:
        if not text or not text.strip():
            return None
        el = etree.SubElement(parent, tag)
        el.text = text.strip()
        return el

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
        if s.current_lg is not None and not s.verse_only:
            s.verse_group_buffer.append(s.current_lg)
            s.current_lg = None
            s.current_l = None

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

class TeiHeaderBuilder:
    def __init__(self, template_path: Path, licenses_path: Path):
        self.template_path = template_path
        self.licenses_path = licenses_path
        self.metadata = {}
        self.ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        etree.register_namespace("tei", self.ns['tei'])
        parser = etree.XMLParser(remove_comments=True)
        self.template_tree = etree.parse(str(template_path), parser)

    def build(self, lines: list[str]) -> etree._Element:
        self.parse_metadata(lines)
        tree = copy.deepcopy(self.template_tree)
        self.populate_template_lxml(tree)
        header_element = tree.getroot().find('tei:teiHeader', self.ns)
        return header_element

    def parse_metadata(self, lines: list[str]):
        current_key = None
        current_value = []
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                if current_key:
                    self.metadata[current_key] = self._process_value(current_value)
                current_key = line[2:].strip()
                current_value = []
            elif current_key:
                if line:
                    current_value.append(line)
        if current_key:
            self.metadata[current_key] = self._process_value(current_value)

    def _process_value(self, value_lines: list[str]) -> str | list | dict:
        stripped_lines = [line for line in value_lines if line.strip()]
        if not stripped_lines:
            return ""
        if all(line.startswith('- ') and ':' not in line for line in stripped_lines):
            return [line[2:].strip() for line in stripped_lines]

        def parse_lines(lines, indent_level=0):
            data = {}
            i = 0
            while i < len(lines):
                line = lines[i]
                indent = len(line) - len(line.lstrip(' '))
                if indent < indent_level:
                    break
                line = line.strip()
                if line.startswith('- '):
                    line = line[2:]
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    j = i + 1
                    nested_lines = []
                    while j < len(lines) and (len(lines[j]) - len(lines[j].lstrip(' '))) > indent:
                        nested_lines.append(lines[j])
                        j += 1
                    if nested_lines:
                        data[key] = parse_lines(nested_lines, indent + 2)
                    else:
                        data[key] = value
                    i = j - 1
                elif line:
                    key = line
                    j = i + 1
                    nested_lines = []
                    while j < len(lines) and (len(lines[j]) - len(lines[j].lstrip(' '))) > indent:
                        nested_lines.append(lines[j])
                        j += 1
                    if nested_lines:
                        data[key] = parse_lines(nested_lines, indent + 2)
                    i = j
                i += 1
            return data

        if any(':' in line for line in stripped_lines):
            return parse_lines(stripped_lines)
        return "\n".join(stripped_lines)

    def populate_template_lxml(self, tree: etree._ElementTree):
        root = tree.getroot()

        def replace_placeholder(placeholder, value):
            ph = f'{{{{{placeholder}}}}}'
            for elem in root.xpath(f".//*[contains(text(),'{ph}')] | .//tei:*[@*[contains(., '{ph}')]]", namespaces=self.ns):
                if elem.text and ph in elem.text:
                    elem.text = elem.text.replace(ph, value)
                if elem.tail and ph in elem.tail:
                    elem.tail = elem.tail.replace(ph, value)
                for attr_name, attr_value in elem.attrib.items():
                    if ph in attr_value:
                        elem.set(attr_name, attr_value.replace(ph, value))

        for key, value in self.metadata.items():
            if isinstance(value, str):
                replace_placeholder(key.upper().replace(' ', '_'), value)

        authors = self.metadata.get('Authors', self.metadata.get('Author'))
        if isinstance(authors, str): authors = [authors]
        author_template = root.find('.//tei:author', self.ns)
        if author_template is not None:
            parent = author_template.getparent()
            if authors:
                idx = parent.index(author_template)
                parent.remove(author_template)
                for i, name in enumerate(authors):
                    new_author = etree.Element("author", nsmap=self.ns)
                    new_author.text = name
                    parent.insert(idx + i, new_author)
            else:
                parent.remove(author_template)

        contributors = self.metadata.get('Contributors', [])
        if isinstance(contributors, str): contributors = [contributors]
        resp_stmt_template = root.find('.//tei:respStmt', self.ns)
        if resp_stmt_template is not None:
            parent = resp_stmt_template.getparent()
            if contributors:
                idx = parent.index(resp_stmt_template)
                parent.remove(resp_stmt_template)
                for i, name in enumerate(contributors):
                    new_stmt = etree.Element("respStmt", nsmap=self.ns)
                    pers_name = etree.SubElement(new_stmt, "persName", nsmap=self.ns)
                    pers_name.text = name
                    resp = etree.SubElement(new_stmt, "resp", nsmap=self.ns)
                    resp.text = "Contribution to the digital edition."
                    parent.insert(idx + i, new_stmt)
            else:
                parent.remove(resp_stmt_template)

        def get_safe_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return None

        text_date = get_safe_date(self.metadata.get('Text Last Updated'))
        meta_date = get_safe_date(self.metadata.get('Metadata Last Updated'))

        latest_date = text_date
        if meta_date:
            if not latest_date or meta_date > latest_date:
                latest_date = meta_date

        year = ""
        if latest_date:
            year = str(latest_date.year)
            pub_date_iso = latest_date.date().isoformat()
            pub_date_human = latest_date.strftime('%B %d, %Y')
            replace_placeholder('COPYRIGHT_YEAR', year)
            replace_placeholder('PUB_DATE_ISO', pub_date_iso)
            replace_placeholder('PUB_DATE_HUMAN', pub_date_human)

        license_name = self.metadata.get('HANSEL License')
        if not license_name:
            raise ValueError("HANSEL License is missing from metadata.")

        license_map = {
            'CC BY-SA 4.0': 'cc_by_sa_4.xml',
            'CC BY-NC-SA 4.0': 'cc_by_nc_sa_4.xml',
            'CC BY 4.0': 'cc_by_4.xml',
            'CC0 1.0': 'cc0_1.xml'
        }
        license_filename = license_map.get(license_name.strip())
        if not license_filename:
            raise ValueError(f"Unknown HANSEL License: '{license_name}'")

        license_file = self.licenses_path / license_filename
        if not license_file.exists():
            raise FileNotFoundError(f"License file not found: {license_file}")

        availability_template = root.find('.//tei:availability', self.ns)
        if availability_template is not None:
            license_str = license_file.read_text(encoding='utf-8')

            if not year:
                if text_date:
                    year = str(text_date.year)
                elif meta_date:
                    year = str(meta_date.year)
                else:
                    year = str(datetime.now().year)

            license_str = license_str.replace('{{COPYRIGHT_YEAR}}', year)
            license_str = license_str.replace('{{RIGHTS_HOLDER}}', 'Tyler Neill')

            try:
                license_element = etree.fromstring(license_str)
                availability_template.text = ''
                for child in list(availability_template):
                    availability_template.remove(child)
                availability_template.append(license_element)
            except etree.XMLSyntaxError as e:
                raise ValueError(f"Error parsing license file {license_file}: {e}")

        breakpoint()
        if 'Edition' in self.metadata and isinstance(self.metadata['Edition'], dict):
            edition_dict = self.metadata['Edition']
            for key, value in edition_dict.items():
                replace_placeholder(f"EDITION_{key.upper()}", value)
            if 'Series' in edition_dict:
                replace_placeholder('SERIES_TITLE', edition_dict['Series'])
            if 'Series Part' in edition_dict:
                replace_placeholder('SERIES_PART', edition_dict['Series Part'])
            if 'Note' in edition_dict:
                replace_placeholder('IMPRINT_NOTE', edition_dict['Note'])

        notes = self.metadata.get('Digitization Notes', [])
        change_template = root.find('.//tei:change', self.ns)
        if change_template is not None:
            parent = change_template.getparent()
            idx = parent.index(change_template)
            parent.remove(change_template)

            if isinstance(notes, dict):
                for key, desc in notes.items():
                    when, who = '', ''
                    # Parse the key which has the format '(date) who'
                    match = re.match(r'\((?P<when>.*?)\)\s*(?P<who>.*)', key.strip())
                    if match:
                        when = match.group('when').strip()
                        who = match.group('who').strip()
                    else:
                        # Fallback if the key is not in the expected format
                        who = key.strip()

                    new_change = etree.Element("change", nsmap=self.ns)
                    if when: new_change.set('when', when)
                    if who: new_change.set('who', who)
                    if desc and 'HANSEL' in desc:
                        new_change.set('ana', '#hansel-contributor')
                    new_change.text = desc.strip() if isinstance(desc, str) else ''
                    parent.insert(idx, new_change)
                    idx += 1
            elif isinstance(notes, list):
                # Fallback for list of strings or dicts
                for note in notes:
                    when, who, desc = '', '', ''
                    if isinstance(note, dict):
                        when = note.get('Date', '')
                        who = note.get('Who', '')
                        desc = note.get('Description', '')
                    elif isinstance(note, str):
                        full_match = re.match(r'\((?P<when>.*?)\)\s*(?P<who>.*?):\s*(?P<desc>.*)', note.strip())
                        if full_match:
                            when = full_match.group('when').strip()
                            who = full_match.group('who').strip()
                            desc = full_match.group('desc').strip()
                        else:
                            when_match = re.match(r'\((?P<when>.*?)\)', note.strip())
                            if when_match:
                                when = when_match.group('when').strip()
                            else:
                                desc = note.strip()

                    new_change = etree.Element("change", nsmap=self.ns)
                    if when: new_change.set('when', when)
                    if who: new_change.set('who', who)
                    if desc and 'HANSEL' in desc:
                        new_change.set('ana', '#hansel-contributor')
                    new_change.text = desc
                    parent.insert(idx, new_change)
                    idx += 1

        # Set from/to dates on publicationStmt/date based on contributor changes
        revision_desc = root.find('.//tei:revisionDesc', self.ns)
        if revision_desc is not None:
            years = []
            for change in revision_desc.findall('change', self.ns):
                if change.get('ana') == '#hansel-contributor':
                    when = change.get('when')
                    if when:
                        found_years = re.findall(r'\b(\d{4})\b', when)
                        for year_str in found_years:
                            years.append(int(year_str))

            if years:
                min_year = min(years)
                max_year = max(years)

                pub_stmt_date = root.find('.//tei:publicationStmt/tei:date', self.ns)
                if pub_stmt_date is not None:
                    pub_stmt_date.set('from', str(min_year))
                    pub_stmt_date.set('to', str(max_year))

        if 'Text Type' in self.metadata and 'Prose with verse' in self.metadata['Text Type']:
            boilerplate_file = Path("utils/transforms/xml/template_components/textual_units/prose_with_verse.xml")
            if boilerplate_file.exists():
                p_template = root.find(".//tei:p[@id='intermediate-textual-units']", namespaces=self.ns)
                if p_template is not None:
                    boilerplate_content = etree.fromstring(boilerplate_file.read_text(encoding='utf-8'))
                    boilerplate_content.set('id', 'intermediate-textual-units')
                    p_template.getparent().replace(p_template, boilerplate_content)

        # Clean up any remaining placeholders
        for elem in root.xpath(".//*[contains(text(),'{{')] | .//tei:*[@*[contains(., '{{')]]", namespaces=self.ns):
            if elem.text and '{{' in elem.text:
                elem.text = re.sub(r'{{[A-Z_0-9]+}}', '', elem.text)
            if elem.tail and '{{' in elem.tail:
                elem.tail = re.sub(r'{{[A-Z_0-9]+}}', '', elem.tail)
            for attr_name, attr_value in elem.attrib.items():
                if '{{' in attr_value:
                    elem.set(attr_name, re.sub(r'{{[A-Z_0-9]+}}', '', attr_value))
