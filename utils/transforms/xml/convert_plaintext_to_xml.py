import argparse
import re
from lxml import etree
from pathlib import Path

from tei_builder import TeiTextBuilder


def build_tei(src: Path, verse_only: bool = False, line_by_line: bool = False) -> etree._Element:
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    builder = TeiTextBuilder(verse_only=verse_only, line_by_line=line_by_line)
    return builder.build(lines)


def serialize(root: etree._Element, pretty_print: bool = True) -> str:
    if pretty_print and hasattr(etree, "indent"):
        etree.indent(root, space="  ")
        # Clean up extra whitespace that indent() adds after inline elements like <caesura>
        ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
        for el in root.xpath("//tei:caesura | //tei:lb | //tei:pb", namespaces=ns):
            if el.tail is not None and el.tail.isspace():
                el.tail = None
    return etree.tostring(root, encoding="unicode", pretty_print=pretty_print)


def prettify(xml: str) -> str:
    # add extra newlines
    xml = re.sub(r"(</?[lp][bg]?[^>]*?>)(?!\n)", r"\1\n", xml)
    # rm line-initial space
    xml = re.sub(r"^ +?([^<])", r"\1", xml, flags=re.MULTILINE)
    return xml


def configure_cli(parser: argparse.ArgumentParser):
    parser.add_argument(
        "src", type=Path,
        help="Source plaintext file"
    )
    parser.add_argument(
        "out", type=Path,
        help="Destination XML file"
    )
    parser.add_argument(
        "--verse-only", action="store_true",
        help="Verse-only mode"
    )
    parser.add_argument(
        "--line-by-line", action="store_true",
        help="Every newline gets <lb>"
    )
    parser.add_argument(
        "-u", "--uglier", action="store_true",
        help="Compact output (no indentation)"
    )
    parser.add_argument(
        "-p", "--prettier", action="store_true",
        help="Extra newlines after pb/lb for readability"
    )
    parser.add_argument(
        "--extra-space-after-location", action="store_true",
        help="Add extra blank line after location markers (only used in xml-plaintext script)."
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Update an existing TEI file instead of creating a new one"
    )


def cli():
    parser = argparse.ArgumentParser(
        description="Convert plaintext into TEI-XML"
    )
    configure_cli(parser)
    args = parser.parse_args()

    # This returns the <TEI> element with the <text> inside
    tei = build_tei(args.src, verse_only=args.verse_only, line_by_line=args.line_by_line)
    ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

    is_update = args.update and args.out.exists() and args.out.stat().st_size > 0

    if is_update:
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.parse(str(args.out), parser).getroot()

        # Define the tag name with the full namespace URI
        text_tag = f"{{{ns['tei']}}}text"

        # Find and remove old <text> element
        old_text = root.find(text_tag)
        if old_text is not None:
            root.remove(old_text)

        # Find new <text> element from builder output
        new_text = tei.find(text_tag)
        if new_text is not None:
            root.append(new_text)

        final_root = root
    else:
        final_root = tei

    # Clean up namespaces to move declaration to the root
    etree.cleanup_namespaces(final_root, top_nsmap={None: ns['tei']})

    # Serialize using the function that calls etree.indent()
    xml = serialize(final_root, pretty_print=not args.uglier)

    if args.prettier:
        xml = prettify(xml)

    # Add the XML declaration
    xml_declaration = "<?xml version='1.0' encoding='UTF-8'?>\n"

    args.out.write_text(xml_declaration + xml, encoding='utf-8')

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    cli()
