from lxml import etree
import os
import argparse
from pathlib import Path
import markdown
from lxml.html import fromstring

def convert_xml_to_html(xml_path, html_path, no_line_numbers=False, verse_only=False, plain=False):
    """
    Converts a TEI XML file to an HTML file with advanced display options.
    Handles all known structural elements from the TEI builder, including nested lg groups,
    heads, backs, and milestones.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, parser)

    # Strip unhelpful namespace info from the tree in-memory
    for elem in tree.iter():
        if '}' in elem.tag:
            elem.tag = elem.tag.split('}', 1)[1]

    root = tree.getroot()

    # --- 1. TOC Data Collection (rich mode only) ---
    toc_data = []
    corrections_data = []
    if not plain:
        for div_section in root.xpath('//body/div[@n]'):
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
    title.text = os.path.basename(Path(xml_path).stem)
    etree.SubElement(head, "meta", name="viewport", content="width=device-width, initial-scale=1.0")

    if not plain:
        components_dir = Path('texts/transforms/html/rich/components')
        html_dir = Path(html_path).parent
        relative_components_path = os.path.relpath(components_dir, start=html_dir)

        link = etree.SubElement(head, "link")
        link.set("rel", "stylesheet")
        link.set("href", (Path(relative_components_path) / 'style.css').as_posix())

        script = etree.SubElement(head, "script")
        script.set("src", (Path(relative_components_path) / 'script.js').as_posix())
        script.text = ""
        sanscript_script = etree.SubElement(head, "script", src="https://cdn.jsdelivr.net/npm/@indic-transliteration/sanscript/sanscript.min.js")
        sanscript_script.text = ""

        if verse_only:
            verse_style_link = etree.SubElement(head, "link")
            verse_style_link.set("rel", "stylesheet")
            verse_style_link.set("href", (Path(relative_components_path) / 'verse_style.css').as_posix())
            
            verse_script = etree.SubElement(head, "script")
            verse_script.set("src", (Path(relative_components_path) / 'verse_script.js').as_posix())
            verse_script.text = ""

    # --- 3. HTML Body ---
    body = etree.SubElement(html, "body")
    if verse_only:
        body.set("class", "simple-verse-style")

    if not plain:
        controls_icon = etree.SubElement(body, "div", id="controls-icon")
        etree.SubElement(controls_icon, "span").text = ""
        etree.SubElement(controls_icon, "span").text = ""
        etree.SubElement(controls_icon, "span").text = ""

        button_container = etree.SubElement(body, "div", **{"class": "button-container"})
        etree.SubElement(button_container, "div", id="close-button-container").text = u"\u00d7"

        if not verse_only:
            loc_container = etree.SubElement(button_container, "div", {"class": "toggle-switch-container"})
            loc_label = etree.SubElement(loc_container, "label", {"class": "toggle-switch"})
            etree.SubElement(loc_label, "input", type="checkbox", onchange="toggleLocationMarkers(this)")
            loc_span_text = etree.SubElement(loc_label, "span", {"class": "toggle-switch-text"})
            loc_span_text.text = "Locations"
            etree.SubElement(loc_label, "span", {"class": "toggle-switch-handle"})

            sw_container1 = etree.SubElement(button_container, "div",
                                            {"class": "toggle-switch-container"})
            sw_label1 = etree.SubElement(sw_container1, "label", {"class": "toggle-switch"})
            etree.SubElement(sw_label1, "input", type="checkbox", onchange="toggleViewMode(this)")
            sw_span_text = etree.SubElement(sw_label1, "span", {"class": "toggle-switch-text"})
            sw_span_text.text = "Search-friendly"
            etree.SubElement(sw_label1, "span", {"class": "toggle-switch-handle"})

            corr_container = etree.SubElement(button_container, "div", {"class": "toggle-switch-container rich-text-toggle"})
            corr_label = etree.SubElement(corr_container, "label", {"class": "toggle-switch"})
            etree.SubElement(corr_label, "input", type="checkbox", onchange="toggleCorrections(this)")
            corr_span_text = etree.SubElement(corr_label, "span", {"class": "toggle-switch-text"})
            corr_span_text.text = "Corrections"
            etree.SubElement(corr_label, "span", {"class": "toggle-switch-handle"})

            info_icon = etree.SubElement(corr_container, "img")
            info_icon.set("id", "corrections-info-icon")
            info_icon.set("src", (Path(relative_components_path) / 'info.png').as_posix())
            info_icon.set("class", "info-icon")
            info_icon.set("title", "Toggles display of corrections, listed at the bottom of the metadata panel.")

            sw_container2 = etree.SubElement(button_container, "div", {"class": "toggle-switch-container rich-text-toggle"})
            sw_label2 = etree.SubElement(sw_container2, "label", {"class": "switch"})
            etree.SubElement(sw_label2, "input", type="checkbox", onchange="toggleLineBreaks(this)")
            etree.SubElement(sw_label2, "span", {"class": "switch-text-off"}).text = "Paragraphs"
            etree.SubElement(sw_label2, "span", {"class": "switch-text-on"}).text = "Lines"

        cb_container = etree.SubElement(button_container, "div", {"class": "toggle-switch-container rich-text-toggle"})
        cb_label = etree.SubElement(cb_container, "label", {"class": "toggle-switch"})
        etree.SubElement(cb_label, "input", type="checkbox", onchange="toggleBreaks(this)")
        cb_span_text = etree.SubElement(cb_label, "span", {"class": "toggle-switch-text"})
        cb_span_text.text = "Line/Page breaks" if not verse_only else "Page breaks"
        etree.SubElement(cb_label, "span", {"class": "toggle-switch-handle"})

        # Transliteration controls
        translit_wrapper = etree.SubElement(button_container, "div", {"class": "toggle-switch-container"})
        inner_container = etree.SubElement(translit_wrapper, "div", id="transliteration-controls-container")
        label_span = etree.SubElement(inner_container, "span", {"class": "toggle-switch-text"})
        label_span.text = "ā→आ"
        controls_div = etree.SubElement(inner_container, "div", id="transliteration-controls")
        select = etree.SubElement(controls_div, "select", id="transliteration-scheme")
        more_label = etree.SubElement(controls_div, "label", id="toggle-switch-text")
        etree.SubElement(more_label, "input", type="checkbox", id="show-all-schemes-checkbox")
        more_text = etree.SubElement(more_label, "span", **{"class": "toggle-switch-text"})
        more_text.text = " more"

        if verse_only:
            v_format_container = etree.SubElement(button_container, "div", {"class": "toggle-switch-container"})
            v_format_label = etree.SubElement(v_format_container, "label", {"class": "toggle-switch"})
            etree.SubElement(v_format_label, "input", type="checkbox", onchange="toggleVerseFormatting(this)")
            v_format_span_text = etree.SubElement(v_format_label, "span", {"class": "toggle-switch-text"})
            v_format_span_text.text = "Verse Styling"
            etree.SubElement(v_format_label, "span", {"class": "toggle-switch-handle"})

            slider_div = etree.SubElement(button_container, "div", {"class": "toggle-switch-container verse-format-toggle"})
            slider_label = etree.SubElement(slider_div, "label", {"class": "simple-checkbox-label"})
            slider_label.text = "Verse Spacing"
            slider_input = etree.SubElement(slider_div, "input", id="width-slider", type="range", min="0", max="1.6", step="0.4", value="0.8")

        top_widgets_div = etree.SubElement(body, "div", id="top-widgets")

        metadata_div = etree.SubElement(top_widgets_div, "div", id="metadata")
        metadata_h2 = etree.SubElement(metadata_div, "h2")
        metadata_h2.text = "Metadata "
        etree.SubElement(metadata_h2, "span", id="metadata-caret").text = "▶"
        metadata_ul = etree.SubElement(metadata_div, "ul", id="metadata-list")
        
        base_name = Path(xml_path).stem
        metadata_md_path = Path('metadata') / f'{base_name}.md'
        if metadata_md_path.exists():
            md_content = metadata_md_path.read_text(encoding="utf-8")
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
            parsed_md_body = fromstring(html_content)

            nodes = list(parsed_md_body.iterchildren())
            i = 0
            while i < len(nodes):
                node = nodes[i]
                if node.tag == 'h1':
                    li = etree.SubElement(metadata_ul, "li")
                    b = etree.SubElement(li, "b")
                    b.text = (node.text or '') + ": "
                    
                    content_nodes = []
                    i += 1
                    while i < len(nodes) and nodes[i].tag != 'h1':
                        content_nodes.append(nodes[i])
                        i += 1
                    
                    if len(content_nodes) == 1 and content_nodes[0].tag == 'p':
                        p_text = content_nodes[0].text_content()
                        b.tail = (b.tail or '') + p_text
                    else:
                        for content_node in content_nodes:
                            li.append(content_node)
                else:
                    i += 1

        toc_div = etree.SubElement(top_widgets_div, "div", id="toc")
        toc_h2 = etree.SubElement(toc_div, "h2")
        toc_h2.text = "Table of Contents "
        etree.SubElement(toc_h2, "span", id="toc-caret").text = "▶"
        toc_ul = etree.SubElement(toc_div, "ul", id="toc-list")
        for item in toc_data:
            li = etree.SubElement(toc_ul, "li")
            a = etree.SubElement(li, "a", href=f"#{item['id']}")
            a.text = f"§ {item['name']} (p.{item['page']})"

    content_div = etree.SubElement(body, "div", id="content")
    if not plain and not verse_only:
        content_div.set('class', 'hide-location-markers')

    # --- 4. Content Processing ---
    def append_text(element, text):
        if not text: return
        if len(element) > 0:
            last_child = element[-1]
            last_child.tail = (last_child.tail or '') + text
        else:
            element.text = (element.text or '') + text

    def get_plain_text_recursive(element):
        text = ''
        if element.text:
            text += element.text
        for child in element:
            if child.tag == 'choice':
                corr = child.find('corr')
                if corr is not None:
                    text += get_plain_text_recursive(corr)
            elif child.tag == 'del':
                pass
            elif child.tag == 'supplied':
                text += get_plain_text_recursive(child)
            else:
                text += get_plain_text_recursive(child)
            if child.tail:
                text += child.tail
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
                if line_n:
                    line_tracker[0] = line_n
                lb_span = etree.SubElement(html_node, "span")
                lb_span.set("class", "lb rich-text")
                lb_span.set("data-line", line_n)
                lb_span.text = f'(p.{page_tracker[0]}, l.{line_n})'
                br = etree.SubElement(html_node, "br")
                br.set("class", "lb-br rich-text")
            elif child.tag == 'pb':
                page_tracker[0] = child.get("n")
                line_tracker[0] = "1"
                pb_span = etree.SubElement(html_node, "span")
                pb_span.set("class", "pb rich-text")
                pb_span.set("data-page", page_tracker[0])
                if no_line_numbers:
                    pb_span.text = f'(p.{page_tracker[0]})'
                else:
                    pb_span.text = f'(p.{page_tracker[0]}, l.1)'
                br = etree.SubElement(html_node, "br")
                br.set("class", "pb-br rich-text")
            elif child.tag == 'choice':
                corr_span = etree.SubElement(html_node, "span", {"class": "correction"})
                sic = child.find('sic')
                corr = child.find('corr')
                sic_text = ''.join(sic.itertext()) if sic is not None else ''
                corr_text = ''.join(corr.itertext()) if corr is not None else ''

                if not plain:
                    corrections_data.append({
                        'sic': sic_text,
                        'corr': corr_text,
                        'page': page_tracker[0],
                        'line': line_tracker[0]
                    })

                ante = etree.SubElement(corr_span, "i", {"class": "ante-correction"})
                ante.set("title", f"pre-correction (post-: {corr_text})")
                if sic is not None:
                    process_children(sic, ante, page_tracker, line_tracker, False)
                post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;"})
                post.set("title", f"post-correction (pre-: {sic_text})")
                if corr is not None:
                    process_children(corr, post, page_tracker, line_tracker, False)
            elif child.tag == 'del':
                corr_span = etree.SubElement(html_node, "span", {"class": "correction"})

                if not plain:
                    del_text = ''.join(child.itertext())
                    corrections_data.append({
                        'sic': del_text,
                        'corr': '',
                        'page': page_tracker[0],
                        'line': line_tracker[0]
                    })

                ante = etree.SubElement(corr_span, "i", {"class": "ante-correction"})
                ante.set("title", "deletion")
                process_children(child, ante, page_tracker, line_tracker, False)
                post_empty = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;"})
                post_empty.text = ''
            elif child.tag == 'supplied':
                corr_span = etree.SubElement(html_node, "span", {"class": "correction"})

                if not plain:
                    supplied_text = ''.join(child.itertext())
                    corrections_data.append({
                        'sic': '',
                        'corr': supplied_text,
                        'page': page_tracker[0],
                        'line': line_tracker[0]
                    })

                ante_empty = etree.SubElement(corr_span, "i", {"class": "ante-correction"})
                ante_empty.text = ''
                post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;"})
                post.set("title", "supplied")
                process_children(child, post, page_tracker, line_tracker, False)
            elif child.tag == 'unclear':
                unclear_span = etree.SubElement(html_node, "span", {"class": "unclear"})
                unclear_span.set("title", "unclear")
                process_children(child, unclear_span, page_tracker, line_tracker, False)
            else:
                process_children(child, html_node, page_tracker, line_tracker, False)

            if child.tail:
                append_text(html_node, child.tail)

    def process_lg_content(lg_element, container, page_tracker, line_tracker, is_plain):
        style = "padding-left: 2em; margin-bottom: 1.3em;" if not verse_only else ""
        if not is_plain:
            # Rich version
            div_rich = etree.SubElement(container, "div", {"class": "lg rich-text", "style": style})
            head_el = lg_element.find('head')
            if head_el is not None and head_el.text:
                p = etree.SubElement(div_rich, "p")
                p.text = head_el.text
            for l in lg_element.findall("l"):
                l_span = etree.SubElement(div_rich, "span")
                process_children(l, l_span, page_tracker, line_tracker, is_plain_version=False)
            back_el = lg_element.find('back')
            if back_el is not None and back_el.text:
                p_back = etree.SubElement(div_rich, "p")
                p_back.text = back_el.text

            # Plain version
            div_plain = etree.SubElement(container, "div", {"class": "lg plain-text", "style": style})
            head_el = lg_element.find('head')
            if head_el is not None and head_el.text:
                p = etree.SubElement(div_plain, "p")
                p.text = head_el.text
            for l in lg_element.findall("l"):
                l_span = etree.SubElement(div_plain, "span")
                process_children(l, l_span, page_tracker, line_tracker, is_plain_version=True)
            back_el = lg_element.find('back')
            if back_el is not None and back_el.text:
                p_back = etree.SubElement(div_plain, "p")
                p_back.text = back_el.text
        else:
            div = etree.SubElement(container, "div", {"class": "lg", "style": style})
            head_el = lg_element.find('head')
            if head_el is not None and head_el.text:
                p = etree.SubElement(div, "p")
                p.text = head_el.text
            for l in lg_element.findall("l"):
                l_span = etree.SubElement(div, "span")
                process_children(l, l_span, page_tracker, line_tracker, is_plain_version=True)
            back_el = lg_element.find('back')
            if back_el is not None and back_el.text:
                p_back = etree.SubElement(div, "p")
                p_back.text = back_el.text

    if verse_only:
        for section in root.xpath('//body/div[@n]'):
            chapter_n_full = section.get('n')
            section_id = f'{chapter_n_full.replace(" ", "_")}'
            h1 = etree.SubElement(content_div, "h1")
            h1.set("id", section_id)
            h1.text = f"§ {chapter_n_full}"
            all_verses_in_section = section.findall('.//lg[@n]')
            if not all_verses_in_section: continue
            verses_ul = etree.SubElement(content_div, "ul")
            verses_ul.set("class", "verses")
            for lg_element in all_verses_in_section:
                verse_id = lg_element.get('n')
                verse_li = etree.SubElement(verses_ul, "li")
                verse_li.set("class", "verse")
                verse_li.set("id", f"v{verse_id.replace('.', '-')}")
                padas_ul = etree.SubElement(verse_li, "ul")
                padas_ul.set("class", "padas")
                l_children = lg_element.findall('l')

                if l_children:
                    last_l = l_children[-1]
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

                for l_child in l_children:
                    pada_li = etree.SubElement(padas_ul, "li")
                    process_children(l_child, pada_li, [''], ['1'], plain)
    else:
        current_page = [""]
        current_line = ["1"]
        for section in root.xpath('//body/div[@n]'):
            section_name = section.get('n')
            section_id = f'{section_name.replace(" ", "_")}'
            h1 = etree.SubElement(content_div, "h1")
            h1.set("id", section_id)
            h1.text = f"§ {section_name}"
            for element in section.iterchildren():
                if element.tag == "pb":
                    current_page[0] = element.get("n")
                    if not plain:
                        pb_span = etree.SubElement(content_div, "span")
                        pb_span.set("class", "pb rich-text")
                        pb_span.set("data-page", current_page[0])
                        if no_line_numbers:
                            pb_span.text = f'(p.{current_page[0]})'
                        else:
                            pb_span.text = f'(p.{current_page[0]}, l.1)'
                        br = etree.SubElement(content_div, "br")
                        br.set("class", "pb-br rich-text")
                    elif element.tag == "milestone":
                        p_milestone = etree.SubElement(content_div, "p")
                        p_milestone.text = f'({element.get("n")}>'
                elif element.tag == "p":
                    n_attr = element.get("n")
                    if n_attr:
                        h2 = etree.SubElement(content_div, "h2")
                        h2.set("class", "location-marker")
                        h2.set("id", n_attr)

                        n_parts = n_attr.split(',')
                        if len(n_parts) == 2:
                            h2.text = f"p.{n_parts[0].strip()}, l.{n_parts[1].strip()}"
                        elif len(n_parts) == 1:
                            h2.text = f"p.{n_parts[0].strip()}"
                        else:
                            h2.text = n_attr

                        page_from_n = n_attr.split(',')[0]
                        if page_from_n:
                            current_page[0] = page_from_n
                            current_line[0] = "1"
                    
                    if not plain:
                        p_rich = etree.SubElement(content_div, "p", {"class": "rich-text"})
                        process_children(element, p_rich, current_page, current_line, is_plain_version=False)
                        p_plain = etree.SubElement(content_div, "p", {"class": "plain-text"})
                        process_children(element, p_plain, current_page, current_line, is_plain_version=True)
                    else:
                        p_element = etree.SubElement(content_div, "p")
                        process_children(element, p_element, current_page, current_line, is_plain_version=True)

                elif element.tag == "lg":
                    n_attr = element.get("n")
                    if n_attr:
                        h2 = etree.SubElement(content_div, "h2")
                        h2.set("class", "location-marker")
                        h2.set("id", n_attr)

                        n_parts = n_attr.split(',')
                        if len(n_parts) == 2:
                            h2.text = f"p.{n_parts[0].strip()}, l.{n_parts[1].strip()}"
                        elif len(n_parts) == 1:
                            h2.text = f"p.{n_parts[0].strip()}"
                        else:
                            h2.text = n_attr

                        page_from_n = n_attr.split(',')[0]
                        if page_from_n:
                            current_page[0] = page_from_n
                            current_line[0] = "1"

                    if element.get('type') == 'group':
                        for lg_child in element.findall("lg"):
                            process_lg_content(lg_child, content_div, current_page, current_line, plain)
                    else:
                        process_lg_content(element, content_div, current_page, current_line, plain)

    if corrections_data and not plain:
        # Create a collapsible list of corrections within the metadata panel
        corrections_li = etree.SubElement(metadata_ul, "li", id="corrections-list-container")
        
        # Title with caret
        corrections_title = etree.SubElement(corrections_li, "b")
        corrections_title.text = f"Corrections ({len(corrections_data)}) "
        
        # The caret for collapsing
        caret = etree.SubElement(corrections_title, "span", {"class": "caret"})
        caret.text = "▶"

        # The nested table of corrections
        corrections_table = etree.SubElement(corrections_li, "table", style="display: none; padding-left: 2em;")
        tbody = etree.SubElement(corrections_table, "tbody")

        for item in corrections_data:
            tr = etree.SubElement(tbody, "tr")
            
            # Location column
            td1 = etree.SubElement(tr, "td", style="padding-right: 1em;")
            td1.text = f"p.{item['page']}, l.{item['line']}:"
            
            sic = item['sic']
            corr = item['corr']
            
            # Change description column
            td2 = etree.SubElement(tr, "td")

            if sic == '' and corr == ' ':
                td2.text = 'space added'
            elif sic == ' ' and corr == '':
                td2.text = 'space removed'
            elif corr == '' and sic != '':
                td2.text = f"{sic} deleted"
            elif sic == '' and corr != '':
                td2.text = f"{corr} added"
            else:
                td2.text = f"{sic} → {corr}"

    # Write the HTML to a file
    with open(html_path, "w", encoding="utf-8") as f:
        html_string = etree.tostring(html, pretty_print=True, encoding="unicode")
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
    print(f"Wrote {args.html_path}")
