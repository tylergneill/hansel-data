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
        """
        1) {n}          → <div xml:id="f{n}" n="{n}">
        2) [label] text → <p xml:id="..." n="label">text</p>
        3) <number>     → <pb n="number"/>
        4) Leading '\t' → verse logic
        5) Otherwise     → prose + <lb/>
        """
        # 1) div markers {n}
        if div_match := re.match(r'^\{(\d+)\}$', line):
            num = div_match.group(1)
            new_div = etree.SubElement(
                self.body,
                'div',
                {
                    f"{{{_XML_NS}}}id": f"f{num}",
                    'n': num
                }
            )
            self.current_div = new_div
            self.current_p = None
            self.current_lg = None
            self.current_l = None
            return

        # 2) paragraph markers [label] with inline content
        if para_match := re.match(r'^\[([^\]]+?)\]\s*(.*)$', line):
            label = para_match.group(1).strip()
            content = para_match.group(2)
            pid = make_xml_id(label)
            new_p = etree.SubElement(
                self.current_div,
                'p',
                {
                    f"{{{_XML_NS}}}id": pid,
                    'n': label
                }
            )
            if content:
                new_p.text = content
            self.current_p = new_p
            self.current_lg = None
            self.current_l = None
            return

        # 3) page breaks at start of line
        if pb_match := re.match(r'^<([^>]+)>', line):
            # implicit paragraph if needed
            if self.current_p is None:
                pid = make_xml_id("implicit")
                new_p = etree.SubElement(
                    self.current_div,
                    'p',
                    {f"{{{_XML_NS}}}id": pid, 'n': pid}
                )
                self.current_p = new_p
            # emit page break
            etree.SubElement(self.current_p, 'pb', attrib={'n': pb_match.group(1).strip()})
            # reset verse counter after a page break
            self.verse_index = 0
            # trim line for further processing
            line = line[pb_match.end():].lstrip()
            if not line:
                return

        # 4) verse lines (leading tab)
        if line.startswith("	"):
            verse_text = line.lstrip("	")
            # ensure paragraph context
            if self.current_p is None:
                pid = make_xml_id("implicit")
                new_p = etree.SubElement(
                    self.current_div,
                    'p',
                    {f"{{{_XML_NS}}}id": pid, 'n': 'implicit'}
                )
                self.current_p = new_p
            parent = self.current_p
            # open <lg> if needed
            if self.current_lg is None:
                self.current_lg = etree.SubElement(parent, 'lg')
                self.verse_index = 0
            # compute segment label (ab, cd, ...)
            start = 2 * self.verse_index
            seg = chr(ord('a') + start) + chr(ord('a') + start + 1)
            self.verse_index += 1
            # create <l n="seg">
            self.current_l = etree.SubElement(self.current_lg, 'l', {'n': seg})
            # set text and add caesura only if no trailing bars
            self.current_l.text = verse_text
            # detect trailing bars
            if not re.search(r"(\|+)$", verse_text):
                etree.SubElement(self.current_l, 'caesura')
            return

        # 5) prose + <lb/> fallback
        # TODO: implement prose line <lb/> logic
        pass
