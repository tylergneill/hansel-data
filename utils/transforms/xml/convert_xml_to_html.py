from lxml import etree
import os
import argparse

def convert_xml_to_html(xml_path, html_path):
    """
    Converts a TEI XML file to an HTML file with a JS toggle for page and line breaks.
    """
    # Parse the XML file
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(xml_path, parser)
    root = tree.getroot()

    # Create the HTML structure
    html = etree.Element("html")
    head = etree.SubElement(html, "head")
    meta = etree.SubElement(head, "meta")
    meta.set("charset", "utf-8")
    title = etree.SubElement(head, "title")
    title.text = os.path.basename(xml_path)

    # Add CSS for the toggle
    style = etree.SubElement(head, "style")
    style.text = """
        .pb, .lb {
            display: none;
        }
        .show-breaks .pb, .show-breaks .lb {
            display: inline;
            cursor: pointer;
            color: blue;
        }
    """

    # Add JavaScript for the toggle
    script = etree.SubElement(head, "script")
    script.text = """
        function toggleBreaks() {
            var content = document.getElementById("content");
            content.classList.toggle("show-breaks");
        }
    """

    body = etree.SubElement(html, "body")

    # Add a button to toggle the breaks
    button = etree.SubElement(body, "button")
    button.set("onclick", "toggleBreaks()")
    button.text = "Toggle Page/Line Breaks"

    content_div = etree.SubElement(body, "div")
    content_div.set("id", "content")

    # Transform the XML content to HTML
    for element in root.iter():
        if element.tag == "p":
            h2 = etree.SubElement(content_div, "h2")
            h2.text = element.get("n")
            p_div = etree.SubElement(content_div, "div")
            p_div.text = element.text
            for child in element:
                if child.tag == "lb":
                    lb = etree.SubElement(p_div, "span")
                    lb.set("class", "lb")
                    lb.set("data-line", child.get("n"))
                    lb.text = "<lb>"
                elif child.tag == "pb":
                    pb = etree.SubElement(p_div, "span")
                    pb.set("class", "pb")
                    pb.set("data-page", child.get("n"))
                    pb.text = "<pb>"
                if child.tail:
                    # Append the text following the tag
                    # This is a bit tricky with lxml. We need to get the last element in p_div and append to its tail
                    if len(p_div):
                        last_elem = p_div[-1]
                        last_elem.tail = (last_elem.tail or '') + child.tail
                    else:
                        p_div.text = (p_div.text or '') + child.tail


        elif element.tag == "lg":
            div = etree.SubElement(content_div, "div")
            div.set("class", "lg")
            for l in element.findall("l"):
                span = etree.SubElement(div, "span")
                span.text = etree.tostring(l, method="text", encoding="unicode")
                etree.SubElement(div, "br")
        elif element.tag == "pb":
            pb = etree.SubElement(content_div, "span")
            pb.set("class", "pb")
            pb.set("data-page", element.get("n"))
            pb.text = f'<pb n="{element.get("n")}">'
        elif element.tag == "milestone":
            span = etree.SubElement(content_div, "span")
            span.set("class", "milestone")
            span.text = f'[{element.get("n")}]'

    # Write the HTML to a file
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(etree.tostring(html, pretty_print=True, encoding="unicode"))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert TEI XML to HTML.")
    parser.add_argument("xml_path", help="Path to the input XML file.")
    parser.add_argument("html_path", help="Path to the output HTML file.")
    args = parser.parse_args()

    convert_xml_to_html(args.xml_path, args.html_path)