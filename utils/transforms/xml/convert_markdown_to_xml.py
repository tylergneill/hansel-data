import argparse
import re
from pathlib import Path
from lxml import etree

from tei_builder import TeiHeaderBuilder


def build_tei_header(src: Path, template_path: Path, licenses_path: Path) -> etree._Element:
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    builder = TeiHeaderBuilder(template_path, licenses_path)
    return builder.build(lines)


def serialize(root: etree._Element, pretty_print: bool = True) -> str:
    if pretty_print and hasattr(etree, "indent"):
        etree.indent(root, space="  ")
    return etree.tostring(root, encoding="unicode", pretty_print=pretty_print)


def configure_cli(parser: argparse.ArgumentParser):
    parser.add_argument(
        "src", type=Path,
        help="Source markdown file"
    )
    parser.add_argument(
        "out", type=Path,
        help="Destination XML file"
    )
    parser.add_argument(
        "-p", "--prettier", action="store_true",
        help="Extra newlines for readability"
    )
    parser.add_argument(
        "-u", "--uglier", action="store_true",
        help="Compact output (no indentation)"
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Update an existing TEI file instead of creating a new one"
    )


def prettify(xml: str) -> str:
    # add extra newlines
    xml = re.sub(r"(</?[lp][bg]?[^>]*?>)(?!\n)", r"\1\n", xml)
    # rm line-initial space
    xml = re.sub(r"^ +?([^<])", r"\1", xml, flags=re.MULTILINE)
    return xml


def cli():
    parser = argparse.ArgumentParser(
        description="Convert markdown metadata to TEI-XML header"
    )
    configure_cli(parser)
    args = parser.parse_args()

    template_path = Path("utils/transforms/xml/template_components/header_template.xml")
    licenses_path = Path("utils/transforms/xml/template_components/licenses")

    # This returns the <teiHeader> element
    header_element = build_tei_header(args.src, template_path, licenses_path)

    ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
    root = None

    is_update = args.update and args.out.exists() and args.out.stat().st_size > 0

    if is_update:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(str(args.out), parser)
        root = tree.getroot()

        old_header = root.find('tei:teiHeader', ns)
        if old_header is not None:
            root.remove(old_header)

        root.insert(0, header_element)
    else:
        # Create a new TEI document
        root = etree.Element("TEI")
        root.append(header_element)

    # Clean up namespaces to move declaration to the root
    etree.cleanup_namespaces(root, top_nsmap={None: ns['tei']})

    # Serialize using the function that calls etree.indent()
    final_xml = serialize(root, pretty_print=not args.uglier)

    # Add the XML declaration
    xml_declaration = "<?xml version='1.0' encoding='UTF-8'?>\n"

    args.out.write_text(xml_declaration + final_xml, encoding='utf-8')

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    cli()
