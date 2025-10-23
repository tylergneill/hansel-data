import argparse
import re
from lxml import etree
from pathlib import Path

ns = {'tei': 'http://www.tei-c.org/ns/1.0'}


def add_shared_argparse_args(parser: argparse.ArgumentParser, input_type: str):
    parser.add_argument(
        "src", type=Path,
        help=f"Source {input_type} file"
    )
    parser.add_argument(
        "out", type=Path,
        help="Destination XML file"
    )
    parser.add_argument(
        "-p", "--prettier", action="store_true",
        help="Extra newlines after pb/lb for readability"
    )
    parser.add_argument(
        "-u", "--uglier", action="store_true",
        help="Compact output (no indentation)"
    )


def get_root(outpath: Path):
    root = None
    if outpath.exists() and outpath.stat().st_size > 0:
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            root = etree.parse(str(outpath), parser).getroot()
        except etree.XMLSyntaxError:
            root = None  # Treat as a new file

    if root is None:
        root = etree.Element("TEI")

    return root


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


def write_xml_file(root: etree._Element, out_path: Path, pretty_print: bool, prettier: bool):
    etree.cleanup_namespaces(root, top_nsmap={None: ns['tei']})

    xml = serialize(root, pretty_print=pretty_print)

    if prettier:
        xml = prettify(xml)

    xml_declaration = "<?xml version='1.0' encoding='UTF-8'?>\n"
    out_path.write_text(xml_declaration + xml, encoding='utf-8')
    print(f"Wrote {out_path}")
