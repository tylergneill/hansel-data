from lxml import etree
import os
import argparse
import json
from pathlib import Path
import markdown
from lxml.html import fromstring

def convert_xml_to_html(xml_path, html_path, no_line_numbers=False, verse_only=False, plain=False):
    """
    Converts a TEI XML file to an HTML fragment and a corresponding JSON sidecar file.
    - The HTML file contains only the core text content inside a <div id="content">.
    - The JSON file contains all metadata, TOC, corrections, and display flags.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, parser)

    for elem in tree.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]

    root = tree.getroot()
    base_name = Path(xml_path).stem

    # --- Data Collection ---
    toc_data = []
    corrections_data = []
    metadata_entries = []

    if not plain:
        for div_section in root.xpath('//body/div[@n]'):
            section_name = div_section.get('n')
            first_pb = div_section.find('.//pb')
            start_page = first_pb.get('n') if first_pb is not None else 'N/A'
            toc_data.append({'name': section_name, 'page': start_page, 'id': f'{section_name.replace(" ", "_")}'})

        # This path needs to be relative to the script location or an absolute path
        # Assuming the script is run from the project root for now.
        metadata_md_path = Path('hansel-data/metadata/markdown/') / f'{base_name}.md'
        if not metadata_md_path.exists():
             # Fallback for different execution contexts
             metadata_md_path = Path(__file__).resolve().parents[2] / 'metadata' / 'markdown' / f'{base_name}.md'

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
                    metadata_entries.append({
                        "type": "field",
                        "label": label_text or None,
                        "inline_text": (inline_text or '').strip() or None,
                        "content_html": rendered_html
                    })
                else:
                    i += 1

    # --- HTML Body Generation ---
    body = etree.Element("body")
    content_div = etree.SubElement(body, "div", id="content")
    if not plain and not verse_only:
        content_div.set('class', 'hide-location-markers')

    # --- Content Processing Functions ---
    def append_text(element, text):
        if not text: return
        if len(element) > 0:
            last_child = element[-1]
            last_child.tail = (last_child.tail or '') + text
        else:
            element.text = (element.text or '') + text

    def get_plain_text_recursive(element):
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

    def process_children(xml_node, html_node, page_tracker, line_tracker, is_plain_version):
        if is_plain_version:
            text_content = get_plain_text_recursive(xml_node)
            append_text(html_node, text_content)
            return

        if xml_node.text:
            append_text(html_node, xml_node.text)
        for child in xml_node:
            if child.tag == 'lb':
                line_n = child.get("n")
                if line_n: line_tracker[0] = line_n
                lb_span = etree.SubElement(html_node, "span", {"class": "lb rich-text", "data-line": line_n})
                lb_span.text = f'(p.{page_tracker[0]}, l.{line_n})'
                etree.SubElement(html_node, "br", {"class": "lb-br rich-text"})
            elif child.tag == 'pb':
                page_tracker[0] = child.get("n")
                line_tracker[0] = "1"
                pb_span = etree.SubElement(html_node, "span", {"class": "pb rich-text", "data-page": page_tracker[0]})
                pb_span.text = f'(p.{page_tracker[0]}, l.1)' if not no_line_numbers else f'(p.{page_tracker[0]})'
                etree.SubElement(html_node, "br", {"class": "pb-br rich-text"})
            elif child.tag == 'choice':
                corr_span = etree.SubElement(html_node, "span", {"class": "correction"})
                sic = child.find('sic')
                corr = child.find('corr')
                sic_text = ''.join(sic.itertext()) if sic is not None else ''
                corr_text = ''.join(corr.itertext()) if corr is not None else ''
                if not plain: corrections_data.append({'sic': sic_text, 'corr': corr_text, 'page': page_tracker[0], 'line': line_tracker[0]})
                ante = etree.SubElement(corr_span, "i", {"class": "ante-correction", "title": f"pre-correction (post-: {corr_text})"})
                if sic is not None: process_children(sic, ante, page_tracker, line_tracker, False)
                post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;", "title": f"post-correction (pre-: {sic_text})"})
                if corr is not None: process_children(corr, post, page_tracker, line_tracker, False)
            elif child.tag in ['del', 'supplied']:
                corr_span = etree.SubElement(html_node, "span", {"class": "correction"})
                text = ''.join(child.itertext())
                if not plain:
                    corrections_data.append({'sic': text if child.tag == 'del' else '', 'corr': text if child.tag == 'supplied' else '', 'page': page_tracker[0], 'line': line_tracker[0]})
                if child.tag == 'del':
                    ante = etree.SubElement(corr_span, "i", {"class": "ante-correction", "title": "deletion"})
                    process_children(child, ante, page_tracker, line_tracker, False)
                    etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;"}).text = ''
                else: # supplied
                    etree.SubElement(corr_span, "i", {"class": "ante-correction"}).text = ''
                    post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;", "title": "supplied"})
                    process_children(child, post, page_tracker, line_tracker, False)
            elif child.tag == 'unclear':
                unclear_span = etree.SubElement(html_node, "span", {"class": "unclear", "title": "unclear"})
                process_children(child, unclear_span, page_tracker, line_tracker, False)
            else:
                process_children(child, html_node, page_tracker, line_tracker, False)
            if child.tail: append_text(html_node, child.tail)

    def process_lg_content(lg_element, container, page_tracker, line_tracker, is_plain):
        style = "padding-left: 2em; margin-bottom: 1.3em;" if not verse_only else ""
        if not is_plain:
            div_rich = etree.SubElement(container, "div", {"class": "lg rich-text", "style": style})
            head_el = lg_element.find('head')
            if head_el is not None and head_el.text: etree.SubElement(div_rich, "p").text = head_el.text
            for l in lg_element.findall("l"): process_children(l, etree.SubElement(div_rich, "span"), page_tracker, line_tracker, is_plain_version=False)
            back_el = lg_element.find('back')
            if back_el is not None and back_el.text: etree.SubElement(div_rich, "p").text = back_el.text

            div_plain = etree.SubElement(container, "div", {"class": "lg plain-text", "style": style})
            head_el = lg_element.find('head')
            if head_el is not None and head_el.text: etree.SubElement(div_plain, "p").text = head_el.text
            for l in lg_element.findall("l"): process_children(l, etree.SubElement(div_plain, "span"), page_tracker, line_tracker, is_plain_version=True)
            back_el = lg_element.find('back')
            if back_el is not None and back_el.text: etree.SubElement(div_plain, "p").text = back_el.text
        else:
            div = etree.SubElement(container, "div", {"class": "lg", "style": style})
            head_el = lg_element.find('head')
            if head_el is not None and head_el.text: etree.SubElement(div, "p").text = head_el.text
            for l in lg_element.findall("l"): process_children(l, etree.SubElement(div, "span"), page_tracker, line_tracker, is_plain_version=True)
            back_el = lg_element.find('back')
            if back_el is not None and back_el.text: etree.SubElement(div, "p").text = back_el.text

    # --- Main Content Processing Loop ---
    current_page = [""]
    current_line = ["1"]
    for section in root.xpath('//body/div[@n]'):
        section_name = section.get('n')
        h1 = etree.SubElement(content_div, "h1", id=f'{section_name.replace(" ", "_")}')
        h1.text = f"§ {section_name}"
        for element in section.iterchildren():
            if element.tag == "p":
                if not plain:
                    p_rich = etree.SubElement(content_div, "p", {"class": "rich-text"})
                    process_children(element, p_rich, current_page, current_line, is_plain_version=False)
                    p_plain = etree.SubElement(content_div, "p", {"class": "plain-text"})
                    process_children(element, p_plain, current_page, current_line, is_plain_version=True)
                else:
                    p_element = etree.SubElement(content_div, "p")
                    process_children(element, p_element, current_page, current_line, is_plain_version=True)
            elif element.tag == "lg":
                process_lg_content(element, content_div, current_page, current_line, plain)

    # --- Final Output Generation ---
    if plain:
        html_doc = etree.Element("html")
        head = etree.SubElement(html_doc, "head")
        etree.SubElement(head, "meta", charset="utf-8")
        title = etree.SubElement(head, "title")
        title.text = base_name
        etree.SubElement(head, "meta", name="viewport", content="width=device-width, initial-scale=1.0")
        body_full = etree.SubElement(html_doc, "body")
        body_full.append(content_div)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(etree.tostring(html_doc, pretty_print=True, encoding="unicode"))
    else:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(etree.tostring(content_div, pretty_print=True, encoding="unicode"))

        if corrections_data:
            metadata_entries.append({
                "type": "corrections",
                "count": len(corrections_data),
                "rows": corrections_data
            })

        document_context = {
            "title": base_name,
            "toc": toc_data,
            "toc_available": bool(toc_data),
            "metadata_entries": metadata_entries,
            "metadata_available": bool(metadata_entries),
            "verse_only": bool(verse_only),
            "includes_plain_variant": not verse_only,
            "no_line_numbers": bool(no_line_numbers)
        }

        json_path = Path(html_path).with_suffix('.json')
        with open(json_path, "w", encoding='utf-8') as f:
            json.dump(document_context, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert TEI XML to HTML and JSON context.")
    parser.add_argument("xml_path", help="Path to the input XML file.")
    parser.add_argument("html_path", help="Path to the output HTML file.")
    parser.add_argument("--no-line-numbers", action="store_true", help="Format page breaks as <PAGE> instead of <PAGE,1>.")
    parser.add_argument("--verse-only", action="store_true", help="Render chapters as ordered lists of verses.")
    parser.add_argument("--plain", action="store_true", help="Generate a plain HTML version without rich features.")
    args = parser.parse_args()

    convert_xml_to_html(args.xml_path, args.html_path, no_line_numbers=args.no_line_numbers, verse_only=args.verse_only, plain=args.plain)
    print(f"Wrote {args.html_path} and {Path(args.html_path).with_suffix('.json')}")