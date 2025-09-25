from lxml import etree
import os
import argparse
from pathlib import Path

def convert_xml_to_html(xml_path, html_path, no_line_numbers=False, verse_only=False, plain=False):
    """
    Converts a TEI XML file to an HTML file with advanced display options.
    Can generate a 'plain' version for searchability or a 'rich' version with all features.
    """
    # Parse the XML file
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()

    id_prefix = "plain_" if plain else ""

    # --- Plain Content Embedding Logic (for rich mode) ---
    plain_body_content = ""
    if not plain:
        try:
            plain_path = Path(html_path).parent.parent / 'plain' / Path(html_path).name
            if plain_path.exists():
                with open(plain_path, "r", encoding="utf-8") as f:
                    plain_html_content = f.read()
                plain_tree = etree.HTML(plain_html_content)
                plain_body = plain_tree.find('body')
                if plain_body is not None:
                    plain_body_content = (plain_body.text or '') + ''.join(etree.tostring(child, encoding='unicode') for child in plain_body)
        except Exception as e:
            print(f"Warning: Could not read or parse plain HTML file '{plain_path}': {e}")

    # --- 1. TOC Data Collection (rich mode only) ---
    toc_data = []
    if not plain:
        for div_section in root.xpath('//body/div[@n]') :
            section_name = div_section.get('n')
            first_pb = div_section.find('.//pb')
            start_page = first_pb.get('n') if first_pb is not None else 'N/A'
            toc_data.append({'name': section_name, 'page': start_page, 'id': f'{section_name.replace(" ", "_")}'})

    # --- 2. HTML Head ---
    html = etree.Element("html")
    head = etree.SubElement(html, "head")
    meta = etree.SubElement(head, "meta")
    meta.set("charset", "utf-8")
    title = etree.SubElement(head, "title")
    title.text = os.path.basename(xml_path)

    style = etree.SubElement(head, "style")
    style_text = "body { font-family: sans-serif; margin: 2em; }\n"
    script_text = ""

    if not plain:
        style_text += """
        #toc { border: 1px solid #ccc; padding: 10px; margin-bottom: 20px; width: 30%; }
        #toc h2 { margin-top: 0; cursor: pointer; user-select: none; }
        #toc-caret { display: inline-block; transition: transform 0.2s; margin-left: 8px; }
        #toc.expanded #toc-caret { transform: rotate(90deg); }
        #toc ul { list-style: none; padding-left: 0; }
        #toc-list { margin-bottom: 0; max-height: 4.5em; /* Approx 3 lines */ overflow: hidden; transition: max-height 0.3s ease-out; }
        #toc.expanded #toc-list { max-height: 500px; /* Large enough for content */ overflow-y: auto; transition: max-height 0.5s ease-in; }
        #toc li { margin-bottom: 5px; }
        .button-container { position: fixed; top: 10px; right: 10px; z-index: 1000; }
        .button-container button { display: block; margin-bottom: 5px; }
        .button-container div { margin-bottom: 10px; background: #f0f0f0; padding: 5px; border-radius: 4px; text-align: center; }
        .button-container label { font-size: 0.8em; display: block; }
        .pb, .lb { display: none; }
        .show-breaks .pb, .show-breaks .lb { display: inline; cursor: pointer; color: blue; }
        #simple-view { display: none; }
        """
        if verse_only:
            style_text += """
            .verses { list-style: none; margin: 0; padding: 0; }
            .verse { position: relative; padding: .5rem .75rem; }
            .verse:nth-child(odd)  { background: hsl(220 20% 97%); }
            .verse:nth-child(even) { background: hsl(220 20% 93%); }
            .padas {
              list-style: none; margin: 0; padding: 0;
              display: grid;
              grid-template-columns: var(--left-col-width, 40%) 1fr;
              column-gap: 1rem;
              row-gap: .25rem;
            }
            .padas > li:first-child { grid-column: 1; grid-row: 1 / -1; }
            .padas > li:not(:first-child) { grid-column: 2; }
            .padas > li { line-height: 1.4; }
            @media (max-width: 520px) {
              .padas { grid-template-columns: 1fr; }
              .padas > li { grid-column: 1 !important; grid-row: auto !important; }
            }
            """
        else:
            style_text += """
            .hyphen, .lb-br, .pb-br { display: none; }
            .show-line-breaks .hyphen { display: inline; }
            .show-line-breaks .lb-br, .show-line-breaks .pb-br { display: block; }
            """

        script_text += """
            function toggleBreaks() { document.getElementById("content").classList.toggle("show-breaks"); }
            function toggleToc() { document.getElementById('toc').classList.toggle('expanded'); }
            function getTopmostVisibleElement(containerSelector) {
                const container = document.querySelector(containerSelector);
                if (!container) return null;
                const elements = container.querySelectorAll('[id]');
                for (const elem of elements) {
                    const rect = elem.getBoundingClientRect();
                    if (rect.top >= 0 && rect.bottom <= window.innerHeight) { return elem; }
                }
                return null;
            }
            function toggleViewMode() {
                const richView = document.getElementById('content');
                const simpleView = document.getElementById('simple-view');
                const toc = document.getElementById('toc');
                let sourceViewSelector, targetViewSelector;
                if (richView.style.display === 'none') {
                    sourceViewSelector = '#simple-view';
                    targetViewSelector = '#content';
                    richView.style.display = 'block';
                    simpleView.style.display = 'none';
                    if(toc) toc.style.display = 'block';
                } else {
                    sourceViewSelector = '#content';
                    targetViewSelector = '#simple-view';
                    richView.style.display = 'none';
                    simpleView.style.display = 'block';
                    if(toc) toc.style.display = 'none';
                }
                const topElem = getTopmostVisibleElement(sourceViewSelector);
                if (topElem && topElem.id) {
                    let targetId;
                    if (sourceViewSelector === '#content') { // from rich to simple
                        targetId = 'plain_' + topElem.id;
                    } else { // from simple to rich
                        targetId = topElem.id.replace('plain_', '');
                    }
                    const targetElem = document.querySelector(`${targetViewSelector} #${targetId}`);
                    if (targetElem) { targetElem.scrollIntoView({ behavior: 'auto', block: 'start' }); }
                }
            }
        """
        if not verse_only:
            script_text += "function toggleLineBreaks() { document.getElementById(\"content\").classList.toggle(\"show-line-breaks\"); }\n"

        script_text += """
            document.addEventListener('DOMContentLoaded', (event) => {
                const tocHeader = document.querySelector('#toc h2');
                if (tocHeader) { tocHeader.addEventListener('click', toggleToc); }
        """
        if verse_only:
            script_text += """
                const slider = document.getElementById('width-slider');
                if (slider) {
                    slider.addEventListener('input', (e) => {
                        document.documentElement.style.setProperty('--left-col-width', e.target.value + '%');
                    });
                }
            """
        script_text += "});"

    style.text = "STYLE_PLACEHOLDER"
    script = etree.SubElement(head, "script")
    script.text = "SCRIPT_PLACEHOLDER"

    # --- 3. HTML Body ---
    body = etree.SubElement(html, "body")

    if not plain:
        button_container = etree.SubElement(body, "div")
        button_container.set("class", "button-container")
        
        button_view = etree.SubElement(button_container, "button")
        button_view.set("onclick", "toggleViewMode()")
        button_view.text = "Toggle Search View"

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
        button1.text = "Show page/line break info"

        if not verse_only:
            button2 = etree.SubElement(button_container, "button")
            button2.set("onclick", "toggleLineBreaks()")
            button2.text = "Toggle line breaks"

        toc_div = etree.SubElement(body, "div")
        toc_div.set("id", "toc")
        toc_h2 = etree.SubElement(toc_div, "h2")
        toc_h2.text = "Table of Contents "
        caret = etree.SubElement(toc_h2, "span")
        caret.set("id", "toc-caret")
        caret.text = "▶"
        toc_ul = etree.SubElement(toc_div, "ul")
        toc_ul.set("id", "toc-list")
        for item in toc_data:
            li = etree.SubElement(toc_ul, "li")
            a = etree.SubElement(li, "a")
            a.set("href", f"#{item['id']}")
            a.text = f"{item['name']} (starts on page {item['page']})"

    content_div = etree.SubElement(body, "div")
    content_div.set("id", "content")

    # --- 4. Content Processing ---
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
            if not plain:
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
            if child.tail:
                append_text(html_node, child.tail)

    if verse_only:
        for section in root.xpath('//body/div[@n]') :
            chapter_n_full = section.get('n')
            section_id = f'{id_prefix}{chapter_n_full.replace(" ", "_")}'
            h1 = etree.SubElement(content_div, "h1")
            h1.set("id", section_id)
            h1.text = f"{{{chapter_n_full}}}"
            all_verses_in_section = section.findall('.//lg[@n]')
            if not all_verses_in_section: continue
            verses_ol = etree.SubElement(content_div, "ol")
            verses_ol.set("class", "verses")
            for lg_element in all_verses_in_section:
                verse_id = lg_element.get('n')
                verse_li = etree.SubElement(verses_ol, "li")
                verse_li.set("class", "verse")
                verse_li.set("id", f"{id_prefix}v{verse_id.replace('.', '-')}")
                padas_ol = etree.SubElement(verse_li, "ol")
                padas_ol.set("class", "padas")
                l_children = lg_element.findall('l')
                for i, l_child in enumerate(l_children):
                    pada_li = etree.SubElement(padas_ol, "li")
                    process_children(l_child, pada_li, [''])
    else:  # Original processing logic
        current_page = [""]
        for section in root.xpath('//body/div[@n]') :
            section_name = section.get('n')
            section_id = f'{id_prefix}{section_name.replace(" ", "_")}'
            h1 = etree.SubElement(content_div, "h1")
            h1.set("id", section_id)
            h1.text = f"{{{section_name}}}"
            for element in section.iterchildren():
                if element.tag == "pb":
                    current_page[0] = element.get("n")
                    if not plain:
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
                    if not plain:
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

    if not plain:
        simple_view_div = etree.SubElement(body, "div")
        simple_view_div.set("id", "simple-view")
        simple_view_div.text = "SIMPLE_VIEW_PLACEHOLDER"

    # Write the HTML to a file
    with open(html_path, "w", encoding="utf-8") as f:
        html_string = etree.tostring(html, pretty_print=True, encoding="unicode")
        html_string = html_string.replace("STYLE_PLACEHOLDER", style_text, 1)
        html_string = html_string.replace("SCRIPT_PLACEHOLDER", script_text, 1)
        if not plain:
            html_string = html_string.replace("SIMPLE_VIEW_PLACEHOLDER", plain_body_content, 1)
        f.write(html_string)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert TEI XML to HTML.")
    parser.add_argument("xml_path", help="Path to the input XML file.")
    parser.add_argument("html_path", help="Path to the output HTML file.")
    parser.add_argument("--no-line-numbers", action="store_true", help="Format page breaks as <PAGE> instead of <PAGE,1>.")
    parser.add_argument("--verse-only", action="store_true", help="Render chapters as ordered lists of verses.")
    parser.add_argument("--plain", action="store_true", help="Generate a plain HTML version without rich features.")
    args = parser.parse_args()

    convert_xml_to_html(args.xml_path, args.html_path, no_line_numbers=args.no_line_numbers, verse_only=args.verse_only, plain=args.plain)
