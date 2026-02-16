import argparse
from lxml import etree
from pathlib import Path

from tei_builder import TeiTextBuilder
from conversion_utils import add_shared_argparse_args, get_root, ns, write_xml_file


def build_tei_text(src: Path, condensed_verse_format: bool = False, line_by_line: bool = False) -> etree._Element:
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    builder = TeiTextBuilder(condensed_verse_format=condensed_verse_format, line_by_line=line_by_line)
    return builder.build(lines)


def configure_cli(parser: argparse.ArgumentParser):
    add_shared_argparse_args(parser, input_type="plaintext")
    parser.add_argument(
        "--condensed-verse-format", action="store_true",
        help="Condensed verse format: [label]<TAB>verse on same line"
    )
    parser.add_argument(
        "--line-by-line", action="store_true",
        help="Every newline gets <lb>"
    )
    parser.add_argument(
        "--extra-space-after-location", action="store_true",
        help="Add extra blank line after location markers (only used in xml-plaintext script)."
    )


def cli():
    parser = argparse.ArgumentParser(
        description="Convert plaintext into TEI-XML text"
    )
    configure_cli(parser)
    args = parser.parse_args()

    # clean up old text
    root = get_root(args.out)
    old_text_element = root.find('tei:text', ns)
    if old_text_element is not None:
        root.remove(old_text_element)

    # create and insert new text
    new_text_element = build_tei_text(args.src, condensed_verse_format=args.condensed_verse_format, line_by_line=args.line_by_line)
    if new_text_element is not None:
        root.append(new_text_element)  # whether teiHeader exists or not, ensures text comes after

    write_xml_file(root, args.out, pretty_print=not args.uglier, prettier=args.prettier)


if __name__ == "__main__":
    cli()
