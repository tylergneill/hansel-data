from lxml import etree
import os
import argparse

def convert_xml_to_html(xml_path, html_path, no_line_numbers=False, verse_only=False):
    """
    Converts a TEI XML file to an HTML file with advanced display options.
    """
    # Parse the XML file
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()

    # --- 1. TOC Data Collection ---
    toc_data = []
    for div_section in root.xpath('//body/div[@n]'):
        section_name = div_section.get('n')
        first_pb = div_section.find('.//pb')
        start_page = first_pb.get('n') if first_pb is not None else 'N/A'
        toc_data.append({'name': section_name, 'page': start_page, 'id': f'section_{section_name.replace(" ", "_")}'})

    # --- 2. HTML Head ---
    html = etree.Element("html")
    head = etree.SubElement(html, "head")
    meta = etree.SubElement(head, "meta")
    meta.set("charset", "utf-8")
    title = etree.SubElement(head, "title")
    title.text = os.path.basename(xml_path)

    style = etree.SubElement(head, "style")
    style_text = """
        body { font-family: sans-serif; margin: 2em; }
        #toc { border: 1px solid #ccc; padding: 10px; margin-bottom: 20px; }
        #toc h2 { margin-top: 0; }
        #toc ul { list-style: none; padding-left: 0; }
        #toc li { margin-bottom: 5px; }
        .button-container { position: fixed; top: 10px; right: 10px; z-index: 1000; }
        .button-container button { display: block; margin-bottom: 5px; }
        .pb, .lb { display: none; }
        .show-breaks .pb, .show-breaks .lb { display: inline; cursor: pointer; color: blue; }
    """
    if verse_only:
        style_text += """
        .verses { list-style: none; padding-left: 0; }
        .verses > li { position: relative; margin-bottom: 1rem; }
        .verse-number { display: inline-block; width: 4em; text-align: right; padding-right: 1em; }
        .verse-line { display: inline-block; }
        """
    else:  # Default, non-verse-only styles
        style_text += """
        .hyphen, .lb-br, .pb-br { display: none; }
        .show-line-breaks .hyphen { display: inline; }
        .show-line-breaks .lb-br, .show-line-breaks .pb-br { display: block; }
        """
    style.text = style_text

    script_text = """
        function toggleBreaks() {
            document.getElementById("content").classList.toggle("show-breaks");
        }
    """
    if not verse_only:
        script_text += """
        function toggleLineBreaks() {
            document.getElementById("content").classList.toggle("show-line-breaks");
        }
        """

    script = etree.SubElement(head, "script")
    script.text = script_text

    # --- 3. HTML Body ---
    body = etree.SubElement(html, "body")

    button_container = etree.SubElement(body, "div")
    button_container.set("class", "button-container")

    button1 = etree.SubElement(button_container, "button")
    button1.set("onclick", "toggleBreaks()")
    if no_line_numbers:
        button1.text = "Show page break info"
    else:
        button1.text = "Show page/line break info"

    if not verse_only:
        button2 = etree.SubElement(button_container, "button")
        button2.set("onclick", "toggleLineBreaks()")
        button2.text = "Toggle line breaks"

    # --- TOC ---
    toc_div = etree.SubElement(body, "div")
    toc_div.set("id", "toc")
    toc_h2 = etree.SubElement(toc_div, "h2")
    toc_h2.text = "Table of Contents"
    toc_ul = etree.SubElement(toc_div, "ul")
    for item in toc_data:
        li = etree.SubElement(toc_ul, "li")
        a = etree.SubElement(li, "a")
        a.set("href", f"#{item['id']}")
        a.text = f"{item['name']} (starts on page {item['page']})"

    content_div = etree.SubElement(body, "div")
    content_div.set("id", "content")

    # --- 4. Content Processing ---
    if verse_only:
        for section in root.xpath('//body/div[@n]'):
            chapter_n_full = section.get('n')
            section_id = f'section_{chapter_n_full.replace(" ", "_")}'

            h1 = etree.SubElement(content_div, "h1")
            h1.set("id", section_id)
            h1.text = f"Chapter {chapter_n_full}"

            all_verses_in_section = section.findall('.//lg[@n]')
            if not all_verses_in_section:
                continue

            first_verse_n = all_verses_in_section[0].get('n').split('.')[-1]

            ol = etree.SubElement(content_div, "ol")
            ol.set("class", "verses")
            if first_verse_n.isdigit():
                ol.set("start", first_verse_n)

            for lg_element in all_verses_in_section:
                verse_id = lg_element.get('n')
                li = etree.SubElement(ol, "li")
                li.set("id", f"v{verse_id.replace('.', ',')}")

                verse_span = etree.SubElement(li, "span")
                verse_span.set("class", "verse-number")
                verse_span.text = verse_id

                l_children = lg_element.findall('l')
                for i, l_child in enumerate(l_children):
                    if i > 0 and len(li) > 0:
                        li[-1].tail = '\u00A0' * 20

                    line_span = etree.SubElement(li, "span")
                    line_span.set("class", "verse-line")

                    if l_child.text:
                        line_span.text = l_child.text
                    
                    for elem in l_child:
                        if elem.tag == 'pb':
                            pb_span = etree.SubElement(line_span, "span")
                            pb_span.set("class", "pb")
                            pb_span.set("data-page", elem.get("n"))
                            pb_span.text = f"<{elem.get('n')}>"
                            if elem.tail:
                                pb_span.tail = (pb_span.tail or '') + elem.tail
                        else:
                            line_span.append(elem)

    else:  # Original processing logic
        current_page = [""]

        def append_text(element, text):
            if not text: return
            if len(element) > 0:
                last_child = element[-1]
                last_child.tail = (last_child.tail or '') + text
            else:
                element.text = (element.text or '') + text

        def process_children(xml_node, html_node, page_tracker):
            if xml_node.text:
                append_text(html_node, xml_node.text)

            for child in xml_node:
                break_no = child.get("break") == "no"

                if break_no:
                    hyphen_span = etree.SubElement(html_node, "span")
                    hyphen_span.set("class", "hyphen")
                    hyphen_span.text = "-"

                if child.tag == 'lb':
                    span = etree.SubElement(html_node, "span")
                    span.set("class", "lb")
                    line_n = child.get("n")
                    span.set("data-line", line_n)
                    span.text = f'<{page_tracker[0]},{line_n}>'
                    br = etree.SubElement(html_node, "br")
                    br.set("class", "lb-br")
                elif child.tag == 'pb':
                    page_tracker[0] = child.get("n")
                    span = etree.SubElement(html_node, "span")
                    span.set("class", "pb")
                    span.set("data-page", page_tracker[0])
                    if no_line_numbers:
                        span.text = f'<{page_tracker[0]}>'
                    else:
                        span.text = f'<{page_tracker[0]},1>'
                    br = etree.SubElement(html_node, "br")
                    br.set("class", "pb-br")
                elif child.tag == 'caesura':
                    pass

                if child.tail:
                    append_text(html_node, child.tail)

        for section in root.xpath('//body/div[@n]'):
            section_name = section.get('n')
            section_id = f'section_{section_name.replace(" ", "_")}'
            h1 = etree.SubElement(content_div, "h1")
            h1.set("id", section_id)
            h1.text = f"{{{section_name}}}"

            for element in section.iterchildren():
                if element.tag == "pb":
                    current_page[0] = element.get("n")
                    break_no = element.get("break") == "no"
                    if break_no:
                        hyphen_span = etree.SubElement(content_div, "span")
                        hyphen_span.set("class", "hyphen")
                        hyphen_span.text = "-"

                    pb = etree.SubElement(content_div, "span")
                    pb.set("class", "pb")
                    pb.set("data-page", element.get("n"))
                    if no_line_numbers:
                        pb.text = f'<{element.get("n")}>'
                    else:
                        pb.text = f'<{element.get("n")},1>'
                    br = etree.SubElement(content_div, "br")
                    br.set("class", "pb-br")

                elif element.tag == "milestone":
                    span = etree.SubElement(content_div, "span")
                    span.set("class", "milestone")
                    span.text = f'[{element.get("n")}]'
                elif element.tag == "p":
                    n_attr = element.get("n")
                    if n_attr:
                        h2 = etree.SubElement(content_div, "h2")
                        h2.text = n_attr
                        page_from_n = n_attr.split(',')[0]
                        if page_from_n:
                            current_page[0] = page_from_n

                    p_element = etree.SubElement(content_div, "p")
                    process_children(element, p_element, current_page)

                elif element.tag == "lg":
                    n_attr = element.get("n")
                    if n_attr:
                        h2 = etree.SubElement(content_div, "h2")
                        h2.text = n_attr
                        page_from_n = n_attr.split(',')[0]
                        if page_from_n:
                            current_page[0] = page_from_n

                    div = etree.SubElement(content_div, "div")
                    div.set("class", "lg")
                    for l in element.findall("l"):
                        l_span = etree.SubElement(div, "span")
                        process_children(l, l_span, current_page)

    # Write the HTML to a file
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(etree.tostring(html, pretty_print=True, encoding="unicode"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert TEI XML to HTML.")
    parser.add_argument("xml_path", help="Path to the input XML file.")
    parser.add_argument("html_path", help="Path to the output HTML file.")
    parser.add_argument("--no-line-numbers", action="store_true", help="Format page breaks as <PAGE> instead of <PAGE,1>.")
    parser.add_argument("--verse-only", action="store_true", help="Render chapters as ordered lists of verses.")
    args = parser.parse_args()

    convert_xml_to_html(args.xml_path, args.html_path, no_line_numbers=args.no_line_numbers, verse_only=args.verse_only)
