from lxml import etree
import argparse
import json
from pathlib import Path
import markdown
from lxml.html import fromstring

# establish globals
NO_LINE_NUMBERS: bool = None
VERSE_ONLY: bool = None
PLAIN: bool = None
STANDALONE: bool = None
TOC_DATA = []
CORRECTIONS_DATA = []
METADATA_ENTRIES = []


# --- Content Processing Functions ---
def append_text(element, text):
    """Appends text to an lxml element, handling children correctly.

    If the element has children, the text is appended to the tail of the last
    child. Otherwise, it's appended to the element's text attribute.

    Args:
        element: The lxml.etree._Element to append text to.
        text: The string to append.
    """
    if not text: return
    if len(element) > 0:
        last_child = element[-1]
        last_child.tail = (last_child.tail or '') + text
    else:
        element.text = (element.text or '') + text

def get_plain_text_recursive(element):
    """Recursively extracts and returns the plain text content of an XML element.

    This function traverses the XML tree, concatenating text content. It makes
    choices about which content to include based on TEI tags:
    - <corr> inside <choice> is preferred.
    - <del> content is ignored.
    - <supplied> content is included.

    Args:
        element: The lxml.etree._Element to extract text from.

    Returns:
        A string containing the concatenated plain text.
    """
    text = ''
    if element.text: text += element.text
    for child in element:
        if child.tag == 'choice':
            corr = child.find('corr')
            if corr is not None: text += get_plain_text_recursive(corr)
        elif child.tag == 'del': pass
        elif child.tag == 'supplied': text += get_plain_text_recursive(child)
        else: text += get_plain_text_recursive(child)
        if child.tail: text += child.tail
    return text

def process_children(xml_node, html_node, page, line, plain):
    """Recursively processes TEI XML nodes and converts them to HTML elements.

    This function walks through the children of an XML node, creating corresponding
    HTML structures. It handles various TEI tags for line breaks, page breaks,
    corrections, and unclear text, generating rich HTML with spans and data
    attributes, or a plain text representation.

    Args:
        xml_node: The source lxml.etree._Element from the TEI XML.
        html_node: The parent lxml.etree._Element in the target HTML tree.
        page: The current page number string.
        line: The current line number string.
        plain: A boolean flag; if True, generates simplified plain text content.
    """
    if plain:
        text_content = get_plain_text_recursive(xml_node)
        append_text(html_node, text_content)
        return page, line

    if xml_node.text:
        append_text(html_node, xml_node.text)
    for child in xml_node:
        if child.tag == 'lb':
            line_n = child.get("n")
            if line_n: line = line_n
            lb_span = etree.SubElement(html_node, "span", {"class": "lb rich-text", "data-line": line_n})
            lb_span.text = f'(p.{page}, l.{line_n})'
            etree.SubElement(html_node, "br", {"class": "lb-br rich-text"})
        elif child.tag == 'pb':
            page = child.get("n")
            line = "1"
            pb_span = etree.SubElement(html_node, "span", {"class": "pb rich-text", "data-page": page})
            pb_span.text = f'(p.{page}, l.1)' if not NO_LINE_NUMBERS else f'(p.{page})'
            etree.SubElement(html_node, "br", {"class": "pb-br rich-text"})
        elif child.tag == 'choice':
            corr_span = etree.SubElement(html_node, "span", {"class": "correction"})
            sic = child.find('sic')
            corr = child.find('corr')
            sic_text = ''.join(sic.itertext()) if sic is not None else ''
            corr_text = ''.join(corr.itertext()) if corr is not None else ''
            if not PLAIN: CORRECTIONS_DATA.append({'sic': sic_text, 'corr': corr_text, 'page': page, 'line': line})
            ante = etree.SubElement(corr_span, "i", {"class": "ante-correction", "title": f"pre-correction (post-: {corr_text})"})
            if sic is not None: page, line = process_children(sic, ante, page, line, False)
            post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;", "title": f"post-correction (pre-: {sic_text})"})
            if corr is not None: page, line = process_children(corr, post, page, line, False)
        elif child.tag in ['del', 'supplied']:
            corr_span = etree.SubElement(html_node, "span", {"class": "correction"})
            text = ''.join(child.itertext())
            if not PLAIN:
                CORRECTIONS_DATA.append({'sic': text if child.tag == 'del' else '', 'corr': text if child.tag == 'supplied' else '', 'page': page, 'line': line})
            if child.tag == 'del':
                ante = etree.SubElement(corr_span, "i", {"class": "ante-correction", "title": "deletion"})
                page, line = process_children(child, ante, page, line, False)
                etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;"}).text = ''
            else: # supplied
                etree.SubElement(corr_span, "i", {"class": "ante-correction"}).text = ''
                post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;", "title": "supplied"})
                page, line = process_children(child, post, page, line, False)
        elif child.tag == 'unclear':
            unclear_span = etree.SubElement(html_node, "span", {"class": "unclear", "title": "unclear"})
            page, line = process_children(child, unclear_span, page, line, False)
        else:
            page, line = process_children(child, html_node, page, line, False)
        if child.tail: append_text(html_node, child.tail)
    return page, line

def process_lg_content(lg_element, container, page, line, plain):
    """Processes a TEI <lg> (line group) element into an HTML structure.

    Creates a styled <div> for the line group and processes its children,
    which can include <head>, <l>, <back>, and <milestone> tags. It can
    generate both rich and plain text versions of the content.

    Args:
        lg_element: The <lg> lxml.etree._Element to process.
        container: The parent HTML element for the generated content.
        page: The current page number string.
        line: The current line number string.
        plain: A boolean flag; if True, generates simplified plain text content.
    """
    style = "padding-left: 2em; margin-bottom: 1.3em;" if not VERSE_ONLY else ""

    def process_lg_children(target_div, plain, page, line):
        """Processes the children of a TEI <lg> element, converting them to HTML.

        This nested function iterates through the direct children of an <lg> element,
        handling specific TEI tags like <head>, <l>, <back>, and <milestone>
        to create corresponding HTML elements within the target div.

        Args:
            target_div: The HTML div element where the processed children will be appended.
            plain: A boolean flag; if True, generates simplified plain text content.
        """
        for child in lg_element.iterchildren():
            if child.tag == 'head':
                if child.text:
                    etree.SubElement(target_div, "p").text = child.text
            elif child.tag == 'l':
                span_tag = etree.SubElement(target_div, "span")
                page, line = process_children(child, span_tag, page, line, plain)
            elif child.tag == 'back':
                if child.text:
                    etree.SubElement(target_div, "p").text = child.text
            elif child.tag == 'milestone':
                if not plain:
                    milestone_span = etree.SubElement(target_div, "span", {"class": "milestone"})
                    milestone_span.text = f'{child.get("n")}'
        return page, line

    if not plain:
        div_rich = etree.SubElement(container, "div", {"class": "lg rich-text", "style": style})
        page, line = process_lg_children(div_rich, plain=False, page=page, line=line)

        div_plain = etree.SubElement(container, "div", {"class": "lg plain-text", "style": style})
        process_lg_children(div_plain, plain=True, page=page, line=line)
    else:
        div = etree.SubElement(container, "div", {"class": "lg", "style": style})
        page, line = process_lg_children(div, plain=True, page=page, line=line)
    return page, line

def convert_xml_to_html(xml_path, html_path):
    """
    In default rich mode, converts a TEI XML file into an HTML fragment and corresponding JSON sidecar file.
    - The HTML file contains only the core text content inside a <div id="content">.
    - The JSON file contains all metadata, TOC, corrections, and display flags.
    Plain and standalone modes omit the JSON sidecar.
    Plain mode omits rich formatting anticipating JavaScript controls.
    Standalone mode outputs a complete rich HTML document, not a fragment.
    """

    # 1. prep XML data, remove namespace prefixes, get text name
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, parser)
    for elem in tree.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]
    root = tree.getroot()
    text_base_name = Path(xml_path).stem

    # 2. generate JSON sidecar (TOC + Metadata for rich HTML)
    if not PLAIN:
        for div_section in root.xpath('//body/div[@n]'):
            section_name = div_section.get('n')
            first_pb = div_section.find('.//pb')
            start_page = 'N/A'
            if first_pb is not None:
                start_page = first_pb.get('n')
            else:
                # Find the first child element with an 'n' attribute
                first_elem_with_n = div_section.find('.//*[@n]')
                if first_elem_with_n is not None:
                    n_attr = first_elem_with_n.get('n')
                    if ',' in n_attr:
                        start_page = n_attr.split(',')[0]
                    else:
                        start_page = n_attr

            TOC_DATA.append({'name': section_name, 'page': start_page, 'id': f'{section_name.replace(" ", "_")}'})

        metadata_md_path = Path(__file__).resolve().parents[3] / 'metadata' / 'markdown' / f'{text_base_name}.md'

        if metadata_md_path.exists():
            md_content = metadata_md_path.read_text(encoding="utf-8")
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
            parsed_md_body = fromstring(html_content)

            nodes = list(parsed_md_body.iterchildren())
            i = 0
            while i < len(nodes):
                node = nodes[i]
                if node.tag == 'h1':
                    content_nodes = []
                    i += 1
                    while i < len(nodes) and nodes[i].tag != 'h1':
                        content_nodes.append(nodes[i])
                        i += 1

                    inline_text = None
                    rendered_html = ""

                    if len(content_nodes) == 1 and content_nodes[0].tag == 'p':
                        inline_text = content_nodes[0].text_content()
                    else:
                        if content_nodes:
                            rendered_html = "".join(etree.tostring(cn, encoding="unicode") for cn in content_nodes)

                    label_text = (node.text or '').strip()
                    if not (inline_text or rendered_html).strip():
                        continue
                    METADATA_ENTRIES.append({
                        "type": "field",
                        "label": label_text or None,
                        "inline_text": (inline_text or '').strip() or None,
                        "content_html": rendered_html
                    })
                else:
                    i += 1

    # 3. generate content_div HTML fragment (= main content processing loop)
    content_div = etree.Element("div", id="content")
    if not PLAIN and not VERSE_ONLY:
        content_div.set('class', 'hide-location-markers')

    if VERSE_ONLY:
        # format text as list of verses with numbering appended at line-end
        for section in root.xpath('//body/div[@n]'):
            chapter_n_full = section.get('n')
            h1 = etree.SubElement(content_div, "h1", id=f'{chapter_n_full.replace(" ", "_")}')
            h1.text = f"§ {chapter_n_full}"
            all_verses_in_section = section.findall('.//lg[@n]')
            if not all_verses_in_section: continue
            verses_ul = etree.SubElement(content_div, "ul", {"class": "verses"})
            for lg_element in all_verses_in_section:
                verse_id = lg_element.get('n')
                verse_li = etree.SubElement(verses_ul, "li", {"class": "verse", "id": f"v{verse_id.replace('.', '-')}"})
                padas_ul = etree.SubElement(verse_li, "ul", {"class": "padas"})
                children_of_lg = list(lg_element.iterchildren())

                # Find the last 'l' element to append the verse number.
                last_l = next((child for child in reversed(children_of_lg) if child.tag == 'l'), None)

                if last_l is not None:
                    trailing_breaks = []
                    while len(last_l) > 0 and last_l[-1].tag in ['pb', 'lb']:
                        child_to_move = last_l[-1]
                        trailing_breaks.insert(0, child_to_move)
                        last_l.remove(child_to_move)
                    
                    if len(last_l) > 0:
                        last_l[-1].tail = (last_l[-1].tail or '') + f" {verse_id} ||"
                    else:
                        last_l.text = (last_l.text or '') + f" {verse_id} ||"
                    
                    for br_tag in trailing_breaks:
                        last_l.append(br_tag)

                # Process all children, creating list items for each.
                for child in children_of_lg:
                    if child.tag == 'l':
                        process_children(child, etree.SubElement(padas_ul, "li"), '', '1', PLAIN)
                    elif child.tag == 'milestone':
                        etree.SubElement(padas_ul, "br")
                        milestone_li = etree.SubElement(padas_ul, "li", {"class": "milestone-verse"})
                        milestone_li.text = f'{child.get("n")}'
    else:
        # format standard text (prose/mixed) with indented verse
        current_page = ""
        current_line = "1"
        for section in root.xpath('//body/div[@n]'):
            section_name = section.get('n')
            h1 = etree.SubElement(content_div, "h1", id=f'{section_name.replace(" ", "_")}')
            h1.text = f"§ {section_name}"
            for element in section.iterchildren():
                if element.tag == "pb":
                    current_page = element.get("n")
                    if not PLAIN:
                        pb_span = etree.SubElement(content_div, "span", {"class": "pb rich-text", "data-page": current_page})
                        pb_span.text = f'(p.{current_page}, l.1)' if not NO_LINE_NUMBERS else f'(p.{current_page})'
                        etree.SubElement(content_div, "br", {"class": "pb-br rich-text"})
                elif element.tag == "milestone":
                    etree.SubElement(content_div, "p").text = f'{element.get("n")}'
                elif element.tag in ["p", "lg"]:
                    n_attr = element.get("n")
                    if n_attr:
                        h2 = etree.SubElement(content_div, "h2", {"class": "location-marker", "id": n_attr})
                        n_parts = n_attr.split(',')
                        h2.text = f"p.{n_parts[0].strip()}, l.{n_parts[1].strip()}" if len(n_parts) == 2 else f"p.{n_parts[0].strip()}" if len(n_parts) == 1 else n_attr
                        page_from_n = n_attr.split(',')[0]
                        if page_from_n: current_page, current_line = page_from_n, "1"
                    if element.tag == "p":
                        if not PLAIN:
                            current_page, current_line = process_children(element, etree.SubElement(content_div, "p", {"class": "rich-text"}), current_page, current_line, plain=False)
                            process_children(element, etree.SubElement(content_div, "p", {"class": "plain-text"}), current_page, current_line, plain=True)
                        else:
                            current_page, current_line = process_children(element, etree.SubElement(content_div, "p"), current_page, current_line, plain=True)
                    else: # lg
                        if element.get('type') == 'group':
                            for lg_child in element.findall("lg"): current_page, current_line = process_lg_content(lg_child, content_div, current_page, current_line, PLAIN)
                        else:
                            current_page, current_line = process_lg_content(element, content_div, current_page, current_line, PLAIN)

    # 4. write output depending on mode
    if PLAIN:
        # inject rich content_div fragment into simple HTML template
        html_doc = etree.Element("html")
        head = etree.SubElement(html_doc, "head")
        etree.SubElement(head, "meta", charset="utf-8")
        title = etree.SubElement(head, "title")
        title.text = text_base_name
        etree.SubElement(head, "meta", name="viewport", content="width=device-width, initial-scale=1.0")
        body_full = etree.SubElement(html_doc, "body")
        body_full.append(content_div)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(etree.tostring(html_doc, pretty_print=True, encoding="unicode"))
    elif STANDALONE:
        # inject rich content_div fragment into HTML template with rich CSS
        template_path = Path(__file__).parent / 'templates' / 'standalone.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template_str = f.read()

        content_str = etree.tostring(content_div, pretty_print=True, encoding="unicode")

        output_html = template_str.replace('{{ title }}', text_base_name)
        output_html = output_html.replace('{{ content_html | safe }}', content_str)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(output_html)
    else:
        # bare rich content_div fragment and JSON sidecar
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(etree.tostring(content_div, pretty_print=True, encoding="unicode"))

        if CORRECTIONS_DATA:
            METADATA_ENTRIES.append({
                "type": "corrections",
                "count": len(CORRECTIONS_DATA),
                "rows": CORRECTIONS_DATA
            })

        document_context = {
            "title": text_base_name,
            "toc": TOC_DATA,
            "metadata_entries": METADATA_ENTRIES,
            "verse_only": VERSE_ONLY,
            "includes_plain_variant": not VERSE_ONLY,  # TODO: figure out whether this is a bug
            "no_line_numbers": NO_LINE_NUMBERS
        }

        json_path = Path(html_path).with_suffix('.json')
        with open(json_path, "w", encoding='utf-8') as f:
            json.dump(document_context, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert TEI XML to HTML and JSON context.")
    parser.add_argument("xml_path", help="Path to the input XML file.")
    parser.add_argument("html_path", help="Path to the output HTML file.")
    parser.add_argument("--no-line-numbers", action="store_true", help="Format page breaks as <PAGE> instead of <PAGE,1> and do not produce <br/>.")
    parser.add_argument("--verse-only", action="store_true", help="Produce special formatting for texts consisting only of numbered verse.")
    parser.add_argument("--plain", action="store_true", help="Generate a plain HTML version without rich features.")
    parser.add_argument("--standalone", action="store_true", help="Generate a browser-viewable HTML file for development.")
    args = parser.parse_args()

    # set globals
    NO_LINE_NUMBERS = args.no_line_numbers
    VERSE_ONLY = args.verse_only
    PLAIN = args.plain
    STANDALONE = args.standalone

    convert_xml_to_html(args.xml_path, args.html_path)
    if not STANDALONE and not PLAIN:
        print(f"Wrote {args.html_path} and {Path(args.html_path).with_suffix('.json')}")
    else:
        print(f"Wrote {args.html_path}")
