import argparse
from lxml import etree
from pathlib import Path

from tei_builder import TeiHeaderBuilder
from conversion_utils import add_shared_argparse_args, get_root, ns, write_xml_file


def build_tei_header(src: Path, template_path: Path, licenses_path: Path) -> etree._Element:
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    builder = TeiHeaderBuilder(template_path, licenses_path)
    return builder.build(lines)


def configure_cli(parser: argparse.ArgumentParser):
    add_shared_argparse_args(parser, input_type="markdown")


def cli():
    parser = argparse.ArgumentParser(
        description="Convert markdown metadata to TEI-XML header"
    )
    configure_cli(parser)
    args = parser.parse_args()

    template_path = Path("utils/transforms/xml/template_components/header_template.xml")
    licenses_path = Path("utils/transforms/xml/template_components/licenses")

    # clean up old header
    root = get_root(args.out)
    old_header_element = root.find('tei:teiHeader', ns)
    if old_header_element is not None:
        root.remove(old_header_element)

    # create and insert new header
    new_header_element = build_tei_header(args.src, template_path, licenses_path)
    if new_header_element is not None:
        root.insert(0, new_header_element)  # first element within TEI

    write_xml_file(root, args.out, pretty_print=not args.uglier, prettier=args.prettier)


if __name__ == "__main__":
    cli()
