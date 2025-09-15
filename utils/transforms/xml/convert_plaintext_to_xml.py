import argparse
import re
from lxml import etree
from pathlib import Path

from tei_builder import TEIBuilder


def build_tei(src: Path, verse_only: bool = False, line_by_line: bool = False) -> etree._Element:
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    builder = TEIBuilder(verse_only=verse_only, line_by_line=line_by_line)
    return builder.build(lines)


def post_process(root: etree._Element) -> None:
    # TODO: implement post-processing cleanups
    pass


def serialize(root: etree._Element, pretty_print: bool = True) -> str:
    if pretty_print and hasattr(etree, "indent"):
        etree.indent(root, space="  ")
        # Clean up extra whitespace that indent() adds after inline elements like <caesura>
        for el in root.xpath("//caesura | //lb | //pb"):
            if el.tail and el.tail.isspace():
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



def cli():
    parser = argparse.ArgumentParser(
        description="Convert plaintext into TEI-XML"
    )
    configure_cli(parser)
    args = parser.parse_args()

    root = build_tei(args.src, verse_only=args.verse_only, line_by_line=args.line_by_line)
    post_process(root)

    xml = serialize(root, pretty_print=not args.uglier)
    if args.prettier:
        xml = prettify(xml)

    args.out.write_text(xml, encoding="utf-8")
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    cli()

