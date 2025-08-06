import re
from lxml import etree

_XML_NS = "http://www.w3.org/XML/1998/namespace"

def make_xml_id(label: str) -> str:
    label = label.strip()
    # Page and line number case
    if "," in label:
        page, line = map(str.strip, label.split(",", 1))
        if page and line:
            page_id = page.replace('.', '_')
            line_id = line.replace('.', '_')
            return f"p{page_id}_l{line_id}"
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
        self.letter_index = 0
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
        div_match = re.match(r'^\{(\d+)\}$', line)
        if div_match:
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
        p_match = re.match(r'^\[([^\]]+?)\]\s*(.*)$', line)
        if p_match:
            label = p_match.group(1).strip()
            content = p_match.group(2)
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

        # 3) page breaks <number>
        # TODO: implement <pb> parsing

        # 4) verse lines (leading tab)
        # TODO: implement <lg>, <l>, <caesura/> logic

        # 5) prose + <lb/> fallback
        # TODO: implement prose line <lb/> logic
        pass
