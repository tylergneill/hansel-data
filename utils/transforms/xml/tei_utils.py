import argparse
import re
from pathlib import Path
from lxml import etree

from tei_builder import TEIBuilder

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
        help="Legacy verse-only mode"
    )
    parser.add_argument(
        "-u", "--uglier", action="store_true",
        help="Compact output (no indentation)"
    )
    parser.add_argument(
        "-p", "--prettier", action="store_true",
        help="Extra newlines after pb/lb for readability"
    )



def build_tei(src: Path, verse_only: bool = False) -> etree._Element:
    text = src.read_text(encoding="utf-8")
    lines = text.splitlines()
    builder = TEIBuilder(verse_only=verse_only)
    return builder.build(lines)


def serialize(root: etree._Element, pretty_print: bool = True) -> str:
    if pretty_print and hasattr(etree, "indent"):
        etree.indent(root, space="  ")
    return etree.tostring(root, encoding="unicode", pretty_print=pretty_print)


def post_process(root: etree._Element) -> None:
    # TODO: implement post-processing cleanups
    pass


def add_extra_newlines(xml: str) -> str:
    return re.sub(r"(</?[lp][bg]?[^>]*?>|<caesura\s*/?>)(?!\n)", r"\1\n", xml)
