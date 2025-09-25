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
        .button-container div { margin-bottom: 10px; background: #f0f0f0; padding: 5px; border-radius: 4px; text-align: center; }
        .button-container label { font-size: 0.8em; display: block; }
        .pb, .lb { display: none; }
        .show-breaks .pb, .show-breaks .lb { display: inline; cursor: pointer; color: blue; }
    """
    if verse_only:
        style_text += """
        .verses { list-style: none; margin: 0; padding: 0; }
        .verse { position: relative; padding: .5rem .75rem; }

        /* alternate backgrounds per verse group */
        .verse:nth-child(odd)  { background: hsl(220 20% 97%); }
        .verse:nth-child(even) { background: hsl(220 20% 93%); }

        /* 2-column pāda layout */
        .padas {
          list-style: none; margin: 0; padding: 0;
          display: grid;
          grid-template-columns: var(--left-col-width, 40%) 1fr;
          column-gap: 1rem;
          row-gap: .25rem;
        }
        .padas > li:first-child {
          grid-column: 1;
          grid-row: 1 / -1; /* This makes the first item span all rows */
        }
        .padas > li:not(:first-child) {
          grid-column: 2;
        }

        /* clean line spacing */
        .padas > li { line-height: 1.4; }

        /* optional: collapse to single column on very narrow screens */
         @media (max-width: 520px) {
          .padas { grid-template-columns: 1fr; }
          .padas > li { grid-column: 1 !important; grid-row: auto !important; }
        }
        """
    else:  # Default, non-verse-only styles
        style_text += """
        .hyphen, .lb-br, .pb-br { display: none; }
        .show-line-breaks .hyphen { display: inline; }
        .show-line-breaks .lb-br, .show-line-breaks .pb-br { display: block; }
        """
    style.text = "STYLE_PLACEHOLDER"

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
    else:  # verse_only
        script_text += """
        document.addEventListener('DOMContentLoaded', (event) => {
            const slider = document.getElementById('width-slider');
            if (slider) {
                slider.addEventListener('input', (e) => {
                    document.documentElement.style.setProperty('--left-col-width', e.target.value + '%');
                });
            }
        });
        """

    script = etree.SubElement(head, "script")
    script.text = "SCRIPT_PLACEHOLDER"

    # --- 3. HTML Body ---
    body = etree.SubElement(html, "body")

    button_container = etree.SubElement(body, "div")
    button_container.set("class", "button-container")

    if verse_only:
        slider_div = etree.SubElement(button_container, "div")
        slider_label = etree.SubElement(slider_div, "label")
        slider_label.set("for", "width-slider")
        slider_label.text = "Column Width"
        slider_input = etree.SubElement(slider_div, "input")
        slider_input.set("type", "range")
        slider_input.set("id", "width-slider")
        slider_input.set("min", "20")
        slider_input.set("max", "80")
        slider_input.set("value", "40")

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
            h1.text = f"{{{chapter_n_full}}}"

            all_verses_in_section = section.findall('.//lg[@n]')
            if not all_verses_in_section:
                continue

            verses_ol = etree.SubElement(content_div, "ol")
            verses_ol.set("class", "verses")

            for lg_element in all_verses_in_section:
                verse_id = lg_element.get('n')
                verse_li = etree.SubElement(verses_ol, "li")
                verse_li.set("class", "verse")
                verse_li.set("id", f"v{verse_id.replace('.', '-')}")

                padas_ol = etree.SubElement(verse_li, "ol")
                padas_ol.set("class", "padas")

                l_children = lg_element.findall('l')
                num_l_children = len(l_children)
                for i, l_child in enumerate(l_children):
                    pada_li = etree.SubElement(padas_ol, "li")
                    if l_child.text:
                        pada_li.text = l_child.text

                    for elem in l_child:
                        if elem.tag == 'pb':
                            pb_span = etree.SubElement(pada_li, "span")
                            pb_span.set("class", "pb")
                            pb_span.set("data-page", elem.get("n"))
                            pb_span.text = f"<{elem.get('n')}>"
                            if elem.tail:
                                pb_span.tail = (pb_span.tail or '') + elem.tail
                        else:
                            pada_li.append(elem)

                    if i == num_l_children - 1:
                        # Defer trailing pb markers until after the verse number is added
                        trailing_pbs = []
                        for child in reversed(pada_li):
                            # We only care about pb spans that are literally at the end.
                            # If a pb span has tail text, it's not at the end.
                            if child.tag == 'span' and child.get('class') == 'pb' and not child.tail:
                                trailing_pbs.insert(0, child)
                            else:
                                break

                        for pb_span in trailing_pbs:
                            pada_li.remove(pb_span)

                        # Add the verse number, enclosed in ||
                        verse_id = lg_element.get('n')
                        text_to_append = f" {verse_id} ||"
                        if len(pada_li) > 0:
                            pada_li[-1].tail = (pada_li[-1].tail or '') + text_to_append
                        else:
                            pada_li.text = (pada_li.text or '') + text_to_append

                        # Add the deferred pb markers back
                        for pb_span in trailing_pbs:
                            pada_li.append(pb_span)

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
        html_string = etree.tostring(html, pretty_print=True, encoding="unicode")
        html_string = html_string.replace("STYLE_PLACEHOLDER", style_text, 1)
        html_string = html_string.replace("SCRIPT_PLACEHOLDER", script_text, 1)
        f.write(html_string)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert TEI XML to HTML.")
    parser.add_argument("xml_path", help="Path to the input XML file.")
    parser.add_argument("html_path", help="Path to the output HTML file.")
    parser.add_argument("--no-line-numbers", action="store_true", help="Format page breaks as <PAGE> instead of <PAGE,1>.")
    parser.add_argument("--verse-only", action="store_true", help="Render chapters as ordered lists of verses.")
    args = parser.parse_args()

    convert_xml_to_html(args.xml_path, args.html_path, no_line_numbers=args.no_line_numbers, verse_only=args.verse_only)
