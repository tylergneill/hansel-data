from lxml import etree
import os
import argparse
import json
from pathlib import Path
import markdown
from lxml.html import fromstring

def convert_xml_to_html(xml_path, html_path, no_line_numbers=False, verse_only=False, plain=False, standalone=False):
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

            toc_data.append({'name': section_name, 'page': start_page, 'id': f'{section_name.replace(" ", "_")}'})

        metadata_md_path = Path(__file__).resolve().parents[3] / 'metadata' / 'markdown' / f'{base_name}.md'

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

        def process_lg_children(target_div, is_plain_version):
            for child in lg_element.iterchildren():
                if child.tag == 'head':
                    if child.text:
                        etree.SubElement(target_div, "p").text = child.text
                elif child.tag == 'l':
                    span_tag = etree.SubElement(target_div, "span")
                    process_children(child, span_tag, page_tracker, line_tracker, is_plain_version)
                elif child.tag == 'back':
                    if child.text:
                        etree.SubElement(target_div, "p").text = child.text
                elif child.tag == 'milestone':
                    if not is_plain_version:
                        milestone_span = etree.SubElement(target_div, "span", {"class": "milestone"})
                        milestone_span.text = f'{child.get("n")}'

        if not is_plain:
            div_rich = etree.SubElement(container, "div", {"class": "lg rich-text", "style": style})
            process_lg_children(div_rich, is_plain_version=False)

            div_plain = etree.SubElement(container, "div", {"class": "lg plain-text", "style": style})
            process_lg_children(div_plain, is_plain_version=True)
        else:
            div = etree.SubElement(container, "div", {"class": "lg", "style": style})
            process_lg_children(div, is_plain_version=True)

    # --- Main Content Processing Loop ---
    if verse_only:
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
                        process_children(child, etree.SubElement(padas_ul, "li"), [''], ['1'], plain)
                    elif child.tag == 'milestone':
                        etree.SubElement(padas_ul, "br")
                        milestone_li = etree.SubElement(padas_ul, "li", {"class": "milestone-verse"})
                        milestone_li.text = f'{child.get("n")}'
    else:
        current_page = [""]
        current_line = ["1"]
        for section in root.xpath('//body/div[@n]'):
            section_name = section.get('n')
            h1 = etree.SubElement(content_div, "h1", id=f'{section_name.replace(" ", "_")}')
            h1.text = f"§ {section_name}"
            for element in section.iterchildren():
                if element.tag == "pb":
                    current_page[0] = element.get("n")
                    if not plain: 
                        pb_span = etree.SubElement(content_div, "span", {"class": "pb rich-text", "data-page": current_page[0]})
                        pb_span.text = f'(p.{current_page[0]}, l.1)' if not no_line_numbers else f'(p.{current_page[0]})'
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
                        if page_from_n: current_page[0], current_line[0] = page_from_n, "1"
                    if element.tag == "p":
                        if not plain:
                            process_children(element, etree.SubElement(content_div, "p", {"class": "rich-text"}), current_page, current_line, is_plain_version=False)
                            process_children(element, etree.SubElement(content_div, "p", {"class": "plain-text"}), current_page, current_line, is_plain_version=True)
                        else:
                            process_children(element, etree.SubElement(content_div, "p"), current_page, current_line, is_plain_version=True)
                    else: # lg
                        if element.get('type') == 'group':
                            for lg_child in element.findall("lg"): process_lg_content(lg_child, content_div, current_page, current_line, plain)
                        else:
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
    elif standalone:
        template_path = Path(__file__).parent / 'templates' / 'standalone.html'
        with open(template_path, 'r', encoding='utf-8') as f:
            template_str = f.read()

        content_str = etree.tostring(content_div, pretty_print=True, encoding="unicode")

        output_html = template_str.replace('{{ title }}', base_name)
        output_html = output_html.replace('{{ content_html | safe }}', content_str)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(output_html)
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
            "metadata_entries": metadata_entries,
            "verse_only": bool(verse_only),
            "includes_plain_variant": not verse_only,  # TODO: figure out whether this is a bug
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
    parser.add_argument("--standalone", action="store_true", help="Generate a standalone HTML file for development.")
    args = parser.parse_args()

    convert_xml_to_html(args.xml_path, args.html_path, no_line_numbers=args.no_line_numbers, verse_only=args.verse_only, plain=args.plain, standalone=args.standalone)
    if not args.standalone and not args.plain:
        print(f"Wrote {args.html_path} and {Path(args.html_path).with_suffix('.json')}")
    else:
        print(f"Wrote {args.html_path}")
