import re
from lxml import etree

# XML namespace constant for TEI
_XML_NS = "http://www.w3.org/XML/1998/namespace"


def make_xml_id(label: str) -> str:
    """
    Create an XML-safe @xml:id from a human label.
    Special case: "page,line" → p{page}_{line}
    Otherwise, prefix "v" and replace non-word chars with underscores.
    """
    label = label.strip()
    # Page and line number case
    if "," in label:
        page, line_no = map(str.strip, label.split(",", 1))
        if page and line_no:
            page_id = page.replace('.', '_')
            line_id = line_no.replace('.', '_')
            return f"p{page_id}_{line_id}"
    # Fallback for general labels
    cleaned = re.sub(r"\W+", "_", label)
    return f"v{cleaned}"

class TEIBuilder:
    def __init__(self, verse_only: bool = False):
        self.verse_only = verse_only
        # Initialize root and body
        self.root = etree.Element("TEI", nsmap={"xml": _XML_NS})
        self.body = etree.SubElement(self.root, "body")
        # State variables
        self.current_div = self.body
        self.current_p = None
        self.current_lg = None
        self.current_l = None
        # index for verse segment labels (ab, cd, ...)
        self.verse_index = 0
        # fallback line break counter
        self.lb_counter = 1

    def build(self, lines: list[str]) -> etree._Element:
        for line in lines:
            self._handle_line(line)
        return self.root

    def _handle_line(self, line: str) -> None:
        # 1) div markers only when the whole line is {n}
        if div_m := re.match(r'^\{([^}]+)\}$', line):
            self._open_div(div_m.group(1))
            return

        # 2) paragraph markers [label] with inline content
        if para_match := re.match(r'^\[([^\]]+?)\]\s*(.*)$', line):
            label = para_match.group(1).strip()
            content = para_match.group(2) or ""
            pid = make_xml_id(label)

            # open the <p>
            new_p = etree.SubElement(
                self.current_div, 'p',
                {f"{{{_XML_NS}}}id": pid, 'n': label}
            )
            self.current_p = new_p
            self.current_lg = None
            self.current_l = None
            self.verse_index = 0  # reset verse‐segment counter

            if self.verse_only and content.startswith("\t"):
                # INLINE verse‐only: open a fresh <lg> and use label suffix for n
                self.current_lg = etree.SubElement(self.current_p, 'lg')
                # extract "ab" or "cd" from the end of the label
                if (m := re.search(r'([a-z]{2})$', label)):
                    seg = m.group(1)
                else:
                    seg = 'ab'
                l_elem = etree.SubElement(self.current_lg, 'l', {'n': seg})
                verse_text = content.lstrip("\t")
                l_elem.text = verse_text
                # add <caesura/> only if there’s no trailing danda
                if not re.search(r'(\|+)$', verse_text):
                    etree.SubElement(l_elem, 'caesura')
            else:
                # normal prose paragraph
                if content:
                    new_p.text = content

            return

        # Now scan the remainder of the line for tokens in order:
        for token_type, text in self._scan_line(line):
            if token_type == 'pb':
                etree.SubElement(self.current_p or self._open_implicit_p(),
                                 'pb', {'n': text})
                # reset verse grouping
                self.verse_index = 0

            elif token_type == 'verse':
                self._emit_verse_segment(text)

            elif token_type == 'prose':
                # append prose to the current element's tail (or text)
                parent = self.current_l or self.current_p or self._open_implicit_p()
                if parent.tail is None:
                    parent.tail = text
                else:
                    parent.tail += text

        # end of line → if the last thing was prose, emit an <lb/>
        if self._last_was_prose:
            etree.SubElement(self.current_p or self._open_implicit_p(),
                             'lb', {'n': str(self.lb_counter)})
            self.lb_counter += 1

    def _scan_line(self, line: str):
        """
        Yields a sequence of (token_type, text) for this line, where token_type
        is one of 'pb' (page break), 'verse', or 'prose'.
        """
        parts = re.split(r'(<\d+>|\t)', line)
        i = 0
        while i < len(parts):
            part = parts[i]
            if not part:
                i += 1
                continue

            # page break
            if m := re.match(r'<(\d+)>', part):
                yield ('pb', m.group(1))
                self._last_was_prose = False
                i += 1

            # verse marker
            elif part == '\t':
                i += 1
                verse_text = parts[i] if i < len(parts) else ''
                yield ('verse', verse_text)
                self._last_was_prose = False
                i += 1

            # prose segment
            else:
                yield ('prose', part)
                self._last_was_prose = True
                i += 1

    def _open_div(self, num: str):
        """Helper for step 1."""
        new_div = etree.SubElement(
            self.body, 'div',
            {f"{{{_XML_NS}}}id": f"f{num}", 'n': num}
        )
        self.current_div = new_div
        self.current_p = None
        self.current_lg = None
        self.current_l = None

    def _open_implicit_p(self):
        """Create a <p> when needed, for stray verse or prose."""
        pid = make_xml_id("implicit")
        self.current_p = etree.SubElement(
            self.current_div, 'p',
            {f"{{{_XML_NS}}}id": pid, 'n': pid}
        )
        return self.current_p

    def _emit_verse_segment(self, verse_text: str):
        """
        DRY’d out verse logic: open/continue <lg>, emit <l n="ab">…</l>,
        and add <caesura/> when no trailing danda.
        """
        # ensure <p>
        if self.current_p is None:
            self._open_implicit_p()

        # open or reuse <lg>
        if self.current_lg is None:
            self.current_lg = etree.SubElement(self.current_p, 'lg')
            self.verse_index = 0

        # label "ab", "cd", …
        start = 2 * self.verse_index
        seg = chr(ord('a') + start) + chr(ord('a') + start + 1)
        self.verse_index += 1

        # emit <l>
        l_elem = etree.SubElement(self.current_lg, 'l', {'n': seg})
        l_elem.text = verse_text

        # caesura only if no trailing danda
        if not re.search(r'(\|+)$', verse_text):
            etree.SubElement(l_elem, 'caesura')

        # clear prose flag
        self._last_was_prose = False