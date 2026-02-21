from lxml import etree
import argparse
import json
from pathlib import Path
import markdown
from lxml.html import fromstring


def _is_condensed_lg(lg_element):
    """Check if an <lg> uses condensed verse format (has <l> children with segment n attributes)."""
    for child in lg_element:
        if child.tag == 'l' and child.get('n'):
            return True
    return False


class HtmlConverter:
    def __init__(self, no_line_numbers=False, only_plain=False, standalone=False):
        self.no_line_numbers = no_line_numbers
        self.only_plain = only_plain
        self.standalone = standalone
        self.toc_data = []
        self.corrections_data = []
        self.metadata_entries = []
        self.current_page = ""
        self.current_line = "1"
        self.pending_label = None
        self.pending_breaks = 0
        self.pdf_page_mapping = None
        self.has_verses = False
        self.has_location_markers = False
        self.current_verse = None
        self.current_verse_part = None
        self.current_location_id = None

    # --- Content Processing Functions ---
    def append_text(self, element, text, strip_leading_whitespace=False, treat_as_plain=True):
        """Appends text to an lxml element, handling children correctly.

        If the element has children, the text is appended to the tail of the last
        child. Otherwise, it's appended to the element's text attribute.

        Args:
            element: The lxml.etree._Element to append text to.
            text: The string to append.
            strip_leading_whitespace: If True, leading whitespace will be stripped from text
                                      if labels/breaks were just flushed.
        """
        if not text:
            return

        # Determine the text to append, stripping leading whitespace if a label was just flushed.
        text_to_append = text

        if not treat_as_plain:
            if (self.pending_breaks or self.pending_label is not None) and text.strip():
                for _ in range(self.pending_breaks):
                    etree.SubElement(element, "br", {"class": "lb-br rich-text"})
                self.pending_breaks = 0

                if self.pending_label is not None:
                    element.append(self.pending_label)
                    self.pending_label = None

                if strip_leading_whitespace:
                    text_to_append = text.lstrip()
        
        if len(element) > 0:
            last_child = element[-1]
            last_child.tail = (last_child.tail or '') + text_to_append
        else:
            element.text = (element.text or '') + text_to_append

    def get_plain_text_recursive(self, element):
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
        if element.text:
            text += element.text
        for child in element:
            if child.tag == 'choice':
                corr = child.find('corr')
                if corr is not None:
                    text += self.get_plain_text_recursive(corr)
            elif child.tag == 'del':
                pass
            elif child.tag == 'supplied':
                text += self.get_plain_text_recursive(child)
            else:
                text += self.get_plain_text_recursive(child)
            if child.tail:
                text += child.tail
        return text

    def process_children(self, xml_node, html_node, treat_as_plain, in_lg=False):
        """Recursively processes TEI XML nodes and converts them to HTML elements.

        This function walks through the children of an XML node, creating corresponding
        HTML structures. It handles various TEI tags for line breaks, page breaks,
        corrections, and unclear text, generating rich HTML with spans and data
        attributes, or a plain text representation.

        Args:
            xml_node: The source lxml.etree._Element from the TEI XML.
            html_node: The parent lxml.etree._Element in the target HTML tree.
            treat_as_plain: A boolean flag; if True, generates simplified plain text content.
        """
        if treat_as_plain:
            text_content = self.get_plain_text_recursive(xml_node)
            self.append_text(html_node, text_content, treat_as_plain=treat_as_plain)
            return

        if xml_node.text:
            self.append_text(html_node, xml_node.text, treat_as_plain=treat_as_plain)
        for child in xml_node:
            if child.tag == 'lb':
                if child.get("break") == "no":
                    etree.SubElement(html_node, "span", {"class": "hyphen"}).text = "-"
                else:
                    # Ensure a space precedes a non-hyphenated break.
                    if len(html_node) > 0:
                        last_elem = html_node[-1]
                        if last_elem.tail:
                            if not last_elem.tail.endswith(' '):
                                last_elem.tail += ' '
                        else:
                            last_elem.tail = ' '
                    elif html_node.text:
                        if not html_node.text.endswith(' '):
                            html_node.text += ' '

                line_n = child.get("n")
                if line_n:
                    self.current_line = line_n

                is_after_caesura = False
                previous_sibling = child.getprevious()
                if previous_sibling is not None and previous_sibling.tag == 'caesura':
                    is_after_caesura = True

                if not in_lg or is_after_caesura:
                    self.pending_breaks += 1
                lb_span = etree.Element("span", {"class": "lb-label rich-text", "data-line": line_n})
                lb_span.text = f'(p.{self.current_page}, l.{line_n})'
                self.pending_label = lb_span
            elif child.tag == 'pb':
                if child.get("break") == "no":
                    etree.SubElement(html_node, "span", {"class": "hyphen"}).text = "-"
                else:
                    # Ensure a space precedes a non-hyphenated break.
                    if len(html_node) > 0:
                        last_elem = html_node[-1]
                        if last_elem.tail:
                            if not last_elem.tail.endswith(' '):
                                last_elem.tail += ' '
                        else:
                            last_elem.tail = ' '
                    elif html_node.text:
                        if not html_node.text.endswith(' '):
                            html_node.text += ' '

                self.current_page = child.get("n")
                self.current_line = "1"
                if not in_lg:
                    self.pending_breaks += 1
                pb_a = etree.Element("a", {"class": "pb-label rich-text", "data-page": self.current_page, "target": "_blank"})
                pb_a.text = f'(p.{self.current_page}, l.1)' if not self.no_line_numbers else f'(p.{self.current_page})'
                self.pending_label = pb_a
            elif child.tag == 'choice':
                corr_span = etree.SubElement(html_node, "span", {"class": "correction"})
                sic = child.find('sic')
                corr = child.find('corr')
                sic_text = ''.join(sic.itertext()) if sic is not None else ''
                corr_text = ''.join(corr.itertext()) if corr is not None else ''
                if not self.only_plain:
                    if self.current_verse is not None:
                        entry = {'sic': sic_text, 'corr': corr_text, 'verse': self.current_verse, 'verse_part': self.current_verse_part, 'location_id': self.current_location_id}
                    else:
                        entry = {'sic': sic_text, 'corr': corr_text, 'page': self.current_page, 'line': self.current_line, 'location_id': self.current_location_id}
                    self.corrections_data.append(entry)
                ante = etree.SubElement(corr_span, "i", {"class": "ante-correction", "title": f"pre-correction (post-: {corr_text})"})
                if sic is not None:
                    self.process_children(sic, ante, treat_as_plain, in_lg=in_lg)
                post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;", "title": f"post-correction (pre-: {sic_text})"})
                if corr is not None:
                    self.process_children(corr, post, treat_as_plain, in_lg=in_lg)
            elif child.tag in ['del', 'supplied']:
                corr_span = etree.SubElement(html_node, "span", {"class": "correction"})
                text = ''.join(child.itertext())
                if not self.only_plain:
                    if self.current_verse is not None:
                        entry = {'sic': text if child.tag == 'del' else '', 'corr': text if child.tag == 'supplied' else '', 'verse': self.current_verse, 'verse_part': self.current_verse_part, 'location_id': self.current_location_id}
                    else:
                        entry = {'sic': text if child.tag == 'del' else '', 'corr': text if child.tag == 'supplied' else '', 'page': self.current_page, 'line': self.current_line, 'location_id': self.current_location_id}
                    self.corrections_data.append(entry)
                if child.tag == 'del':
                    ante = etree.SubElement(corr_span, "i", {"class": "ante-correction", "title": "deletion"})
                    self.process_children(child, ante, treat_as_plain, in_lg=in_lg)
                    etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;"}).text = ''
                else: # supplied
                    etree.SubElement(corr_span, "i", {"class": "ante-correction"}).text = ''
                    post = etree.SubElement(corr_span, "i", {"class": "post-correction", "style": "display:none;", "title": "supplied"})
                    self.process_children(child, post, treat_as_plain, in_lg=in_lg)
            elif child.tag == 'unclear':
                unclear_span = etree.SubElement(html_node, "span", {"class": "unclear", "title": "unclear"})
                self.process_children(child, unclear_span, treat_as_plain, in_lg=in_lg)
            else:
                self.process_children(child, html_node, treat_as_plain, in_lg=in_lg)
            if child.tail:
                should_strip = (child.tag in ['lb', 'pb']) and not treat_as_plain
                self.append_text(html_node, child.tail, strip_leading_whitespace=should_strip, treat_as_plain=treat_as_plain)

    def process_lg_content(self, lg_element, container, treat_as_plain):
        """Processes a TEI <lg> (line group) element into an HTML structure.

        In condensed-verse-format: uses <ul class="verses">/<li class="verse">/<ul class="padas">/<li>
        markup with verse number appended to last pāda as " N ||".
        In standard mode: uses <div class="lg">/<span> markup (indented verse).

        Args:
            lg_element: The <lg> lxml.etree._Element to process.
            container: The parent HTML element for the generated content.
            treat_as_plain: A boolean flag; if True, generates simplified plain text content.
        """
        self.has_verses = True

        def process_lg_children_standard(target_div, treat_as_plain):
            for child in lg_element.iterchildren():
                if child.tag == 'head':
                    if child.text:
                        p_tag = etree.SubElement(target_div, "p", {"class": "lg-head"})
                        self.append_text(p_tag, child.text, treat_as_plain=treat_as_plain)
                elif child.tag == 'l':
                    span_tag = etree.SubElement(target_div, "span")
                    self.process_children(child, span_tag, treat_as_plain, in_lg=(not treat_as_plain))
                elif child.tag == 'back':
                    if len(target_div) > 0:
                        last_element = target_div[-1]
                        self.process_children(child, last_element, treat_as_plain, in_lg=(not treat_as_plain))
                    else:
                        p_tag = etree.SubElement(target_div, "p")
                        self.process_children(child, p_tag, treat_as_plain, in_lg=(not treat_as_plain))
                elif child.tag == 'milestone':
                    if not treat_as_plain:
                        milestone_span = etree.SubElement(target_div, "span", {"class": "milestone"})
                        milestone_span.text = f'{child.get("n")}'

        if not _is_condensed_lg(lg_element):
            if treat_as_plain:
                div_elem = etree.SubElement(container, "div", {"class": "lg plain-text"})
                process_lg_children_standard(div_elem, treat_as_plain=True)
            else:
                # Emit <head> elements before the verse li, directly on the container
                for child in lg_element.iterchildren():
                    if child.tag == 'head' and child.text:
                        head_p = etree.SubElement(container, "li", {"class": "lg-head rich-text"})
                        head_p.text = child.text
                # Wrap verse lines in li.verse so verse-styling CSS can target it
                verse_li = etree.SubElement(container, "li", {"class": "verse rich-text"})
                div_elem = etree.SubElement(verse_li, "div", {"class": "lg"})
                for child in lg_element.iterchildren():
                    if child.tag == 'l':
                        span_tag = etree.SubElement(div_elem, "span")
                        self.process_children(child, span_tag, False, in_lg=True)
                    elif child.tag == 'back':
                        if len(div_elem) > 0:
                            self.process_children(child, div_elem[-1], False, in_lg=True)
                        else:
                            p_tag = etree.SubElement(div_elem, "p")
                            self.process_children(child, p_tag, False, in_lg=True)
                    elif child.tag == 'milestone':
                        milestone_span = etree.SubElement(div_elem, "span", {"class": "milestone"})
                        milestone_span.text = f'{child.get("n")}'
            return

        # Condensed verse format below

        if treat_as_plain:
            cls = "lg plain-text"
            div_elem = etree.SubElement(container, "div", {"class": cls})
            process_lg_children_standard(div_elem, treat_as_plain=True)
            return

        # Rich pass for condensed verse format: emit ul/li verse structure
        verse_n = lg_element.get("n")
        self.current_verse = verse_n
        self.current_location_id = f"v{verse_n.replace('.', '-')}" if verse_n else None

        verse_li = etree.SubElement(container, "li", {"class": "verse rich-text"})
        if self.current_location_id:
            verse_li.set("id", self.current_location_id)
        padas_ul = etree.SubElement(verse_li, "ul", {"class": "padas"})

        children_of_lg = list(lg_element.iterchildren())

        # Find the last 'l' element to append the verse number
        last_l = next((child for child in reversed(children_of_lg) if child.tag == 'l'), None)

        if last_l is not None and verse_n:
            trailing_breaks = []
            while len(last_l) > 0 and last_l[-1].tag in ['pb', 'lb']:
                child_to_move = last_l[-1]
                if child_to_move.tail and child_to_move.tail.strip():
                    break
                trailing_breaks.insert(0, child_to_move)
                last_l.remove(child_to_move)

            if len(last_l) > 0:
                last_l[-1].tail = (last_l[-1].tail or '') + f" {verse_n} ||"
            else:
                last_l.text = (last_l.text or '') + f" {verse_n} ||"

            for br_tag in trailing_breaks:
                last_l.append(br_tag)

        # Track which <l> is last so we can bold its verse number in the HTML output
        last_l_for_bold = last_l if (last_l is not None and verse_n) else None

        for child in children_of_lg:
            if child.tag == 'head':
                if child.text:
                    p_tag = etree.SubElement(padas_ul, "p", {"class": "lg-head"})
                    self.append_text(p_tag, child.text, treat_as_plain=False)
            elif child.tag == 'l':
                self.current_verse_part = child.get('n')
                li_elem = etree.SubElement(padas_ul, "li")
                self.process_children(child, li_elem, False, in_lg=True)
                if child is last_l_for_bold:
                    # Bold the verse number in the HTML output.
                    # The text " {verse_n} ||" was appended to the XML source,
                    # so it's now in the HTML li's last child tail or the li's text.
                    # Trailing <lb>/<pb> elements may add whitespace after "||",
                    # so we match against rstripped text.
                    marker = f" {verse_n} ||"
                    if len(li_elem) > 0:
                        last = li_elem[-1]
                        if last.tail and last.tail.rstrip().endswith(marker):
                            trailing_ws = last.tail[len(last.tail.rstrip()):]
                            last.tail = last.tail.rstrip()[:-len(marker)] + " "
                            b_tag = etree.SubElement(li_elem, "b")
                            b_tag.text = verse_n
                            b_tag.tail = " ||" + trailing_ws
                    elif li_elem.text and li_elem.text.rstrip().endswith(marker):
                        trailing_ws = li_elem.text[len(li_elem.text.rstrip()):]
                        li_elem.text = li_elem.text.rstrip()[:-len(marker)] + " "
                        b_tag = etree.SubElement(li_elem, "b")
                        b_tag.text = verse_n
                        b_tag.tail = " ||" + trailing_ws
            elif child.tag == 'back':
                if len(padas_ul) > 0:
                    self.process_children(child, padas_ul[-1], False, in_lg=True)
            elif child.tag == 'milestone':
                etree.SubElement(padas_ul, "br")
                milestone_li = etree.SubElement(padas_ul, "li", {"class": "milestone-verse"})
                milestone_li.text = f'{child.get("n")}'

    def convert_xml_to_html(self, xml_path, html_path):
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
        if not self.only_plain:
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

                self.toc_data.append({'name': section_name, 'page': start_page, 'id': f'{section_name.replace(" ", "_")}'})

            metadata_md_path = Path(__file__).resolve().parents[3] / 'metadata' / 'markdown' / f'{text_base_name}.md'

            if metadata_md_path.exists():
                md_content = metadata_md_path.read_text(encoding="utf-8")
                html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
                
                # Prefix miscellaneous links to point to /static/data/
                html_content = html_content.replace('href="miscellaneous/', 'href="/static/data/miscellaneous/')

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

                        # If there's only one paragraph and it has no child elements (like links), treat it as inline text.
                        if len(content_nodes) == 1 and content_nodes[0].tag == 'p' and len(content_nodes[0]) == 0:
                            inline_text = content_nodes[0].text_content()
                        else:
                            if content_nodes:
                                rendered_html = "".join(etree.tostring(cn, encoding="unicode") for cn in content_nodes)

                        label_text = (node.text or '').strip()
                        if not (inline_text or rendered_html).strip():
                            continue
                        self.metadata_entries.append({
                            "type": "field",
                            "label": label_text or None,
                            "inline_text": (inline_text or '').strip() or None,
                            "content_html": rendered_html
                        })
                    else:
                        i += 1

                pdf_link_url = None
                pdf_offsets = None
                edition_pdfs_entry = next((entry for entry in self.metadata_entries if entry['label'] == 'Edition PDFs'), None)
                if edition_pdfs_entry and edition_pdfs_entry['content_html']:
                    html_fragment = fromstring(edition_pdfs_entry['content_html'])
                    link = html_fragment.find('.//a')
                    if link is not None and 'href' in link.attrib:
                        pdf_link_url = link.get('href')

                pdf_offset_entry = next((entry for entry in self.metadata_entries if entry['label'] == 'PDF Page Offset'), None)
                if pdf_offset_entry and pdf_offset_entry['content_html']:
                    html_fragment = fromstring(pdf_offset_entry['content_html']) # this will be a <ul>
                    offsets = []
                    for li in html_fragment.findall('.//li'):
                        text = li.text_content().strip()
                        if '→' in text:
                            parts = [p.strip() for p in text.split('→')]
                        else:
                            parts = [p.strip() for p in text.split(',')]
                        if len(parts) == 2:
                            try:
                                offsets.append([int(parts[0]), int(parts[1])])
                            except ValueError:
                                pass
                    if offsets:
                        pdf_offsets = offsets

                if pdf_offsets is None:
                    pdf_offsets = [[1, 1]]

                if pdf_link_url and pdf_offsets:
                    self.pdf_page_mapping = {
                        "url": pdf_link_url,
                        "offsets": pdf_offsets
                    }


        # 3. generate content_div HTML fragment (= main content processing loop)
        content_div = etree.Element("div", id="content")
        if not self.only_plain:
            content_div.set('class', 'hide-location-markers')

        self.current_page, self.current_line = '', '1'  # TODO: investigate whether necessary to reset like this
        for section in root.xpath('//body/div[@n]'):
            section_name = section.get('n')
            h1 = etree.SubElement(content_div, "h1", id=section_name.replace(" ", "_"))
            h1.text = f"§ {section_name}"

            # Collect lg elements for this section to wrap in a <ul class="verses">
            # We use a "current verses_ul" that gets created on first lg and closed on non-lg
            current_verses_ul = None

            for element in section.iterchildren():
                if element.tag == "milestone":
                    current_verses_ul = None
                    # Milestones occupy a physical line
                    self.current_line = str(int(self.current_line) + 1)
                    if self.pending_label is not None:
                        label_text = f'(p.{self.current_page}, l.{self.current_line})' if not self.no_line_numbers else f'(p.{self.current_page})'
                        self.pending_label.text = label_text
                    n_attr = element.get("n")
                    if n_attr:
                        etree.SubElement(content_div, "h2", {"class": "milestone rich-text"}).text = n_attr

                elif element.tag == "pb":
                    self.current_page = element.get("n")
                    self.current_line = "1"
                    pb_a = etree.Element("a", {"class": "pb-label rich-text", "data-page": self.current_page, "target": "_blank"})
                    pb_a.text = f'(p.{self.current_page}, l.1)' if not self.no_line_numbers else f'(p.{self.current_page})'
                    self.pending_label = pb_a

                elif element.tag == "p":
                    current_verses_ul = None
                    self.current_verse = None
                    self.current_verse_part = None
                    n_attr = element.get("n")
                    if n_attr:
                        # Clear pending breaks/labels from the previous element's trailing <lb>/<pb>,
                        # since the location marker <h2> replaces their visual function.
                        self.pending_breaks = 0
                        self.pending_label = None
                        self.has_location_markers = True
                        self.current_location_id = n_attr.replace(',', '_').replace(' ', '')
                        h2 = etree.SubElement(content_div, "h2", {"class": "location-marker rich-text", "id": self.current_location_id})
                        n_parts = n_attr.split(',')
                        page_part = n_parts[0].strip()
                        line_part = n_parts[1].strip() if len(n_parts) > 1 else "1"

                        self.current_page = page_part
                        self.current_line = line_part

                        if len(n_parts) == 2:
                            h2.text = f"p.{page_part}, l.{line_part}"
                        elif len(n_parts) == 1:
                            h2.text = f"p.{page_part}"
                        else:
                            h2.text = n_attr

                    if not self.only_plain:
                        self.process_children(element, etree.SubElement(content_div, "p", {"class": "rich-text"}), treat_as_plain=False, in_lg=False)
                    self.process_children(element, etree.SubElement(content_div, "p", {"class": "plain-text"}), treat_as_plain=True, in_lg=False)

                elif element.tag == "lg":
                    n_attr = element.get("n")

                    # Detect whether this lg (or its children for group type) uses condensed format
                    is_condensed = False
                    if element.get('type') == 'group':
                        is_condensed = any(_is_condensed_lg(lg_child) for lg_child in element.findall("lg"))
                    else:
                        is_condensed = _is_condensed_lg(element)

                    # Standard mode: emit location marker h2 before the verse
                    if not is_condensed and n_attr:
                        if ',' not in n_attr:
                            raise ValueError(f"Standard-format <lg> has non-page,line n attribute: n=\"{n_attr}\". Use condensed verse format for verse-numbered lgs.")

                        # Clear pending breaks/labels from the previous element's trailing <lb>/<pb>,
                        # since the location marker <h2> replaces their visual function.
                        self.pending_breaks = 0
                        self.pending_label = None
                        self.has_location_markers = True
                        self.current_location_id = n_attr.replace(',', '_').replace(' ', '')
                        # Break the current verses_ul so a new one is created after this h2
                        current_verses_ul = None
                        h2 = etree.SubElement(content_div, "h2", {"class": "location-marker rich-text", "id": self.current_location_id})
                        n_parts = n_attr.split(',')
                        page_part = n_parts[0].strip()
                        line_part = n_parts[1].strip() if len(n_parts) > 1 else "1"

                        self.current_page = page_part
                        self.current_line = line_part

                        if len(n_parts) == 2:
                            h2.text = f"p.{page_part}, l.{line_part}"
                        elif len(n_parts) == 1:
                            h2.text = f"p.{page_part}"
                        else:
                            h2.text = n_attr

                    # Rich pass: wrap in <ul class="verses"> for verse-styling CSS
                    if not self.only_plain:
                        if current_verses_ul is None:
                            current_verses_ul = etree.SubElement(content_div, "ul", {"class": "verses rich-text"})
                        if element.get('type') == 'group':
                            for lg_child in element.findall("lg"):
                                self.process_lg_content(lg_child, current_verses_ul, treat_as_plain=False)
                        else:
                            self.process_lg_content(element, current_verses_ul, treat_as_plain=False)

                    # Plain pass
                    if element.get('type') == 'group':
                        for lg_child in element.findall("lg"):
                            self.process_lg_content(lg_child, content_div, treat_as_plain=True)
                    else:
                        self.process_lg_content(element, content_div, treat_as_plain=True)

        # 4. write output depending on mode
        if self.only_plain:
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

        elif self.standalone:
            # inject rich content_div fragment into HTML template with rich CSS
            template_path = Path(__file__).parent / 'templates' / 'standalone.html'
            with open(template_path, 'r', encoding='utf-8') as f:
                template_str = f.read()

            content_str = etree.tostring(content_div, pretty_print=True, encoding="unicode")

            output_html = template_str.replace('{{ title }}', text_base_name)
            output_html = output_html.replace('{{ content_html | safe }}', content_str)

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(output_html)

        else: # rich
            # directly write rich content_div fragment and JSON sidecar
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(etree.tostring(content_div, pretty_print=True, encoding="unicode"))

            if self.corrections_data:
                self.metadata_entries.append({
                    "type": "corrections",
                    "count": len(self.corrections_data),
                    "rows": self.corrections_data
                })

            document_context = {
                "title": text_base_name,
                "toc": self.toc_data,
                "metadata_entries": self.metadata_entries,
                "has_verses": self.has_verses,
                "has_location_markers": self.has_location_markers,
                "no_line_numbers": self.no_line_numbers
            }
            if self.pdf_page_mapping:
                document_context["pdf_page_mapping"] = self.pdf_page_mapping

            json_path = Path(html_path).with_suffix('.json')
            with open(json_path, "w", encoding='utf-8') as f:
                json.dump(document_context, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert TEI XML to HTML and JSON context.")
    parser.add_argument("xml_path", help="Path to the input XML file.")
    parser.add_argument("html_path", help="Path to the output HTML file.")
    parser.add_argument("--no-line-numbers", action="store_true", help="Format page breaks as <PAGE> instead of <PAGE,1> and do not produce <br/>.")
    parser.add_argument("--plain", action="store_true", help="Generate a plain HTML version without rich features.")
    parser.add_argument("--standalone", action="store_true", help="Generate a browser-viewable HTML file for development.")
    args = parser.parse_args()

    converter = HtmlConverter(
        no_line_numbers=args.no_line_numbers,
        only_plain=args.plain,
        standalone=args.standalone
    )
    converter.convert_xml_to_html(args.xml_path, args.html_path)

    if not args.standalone and not args.plain:
        print(f"Wrote {args.html_path} and {Path(args.html_path).with_suffix('.json')}")
    else:
        print(f"Wrote {args.html_path}")
