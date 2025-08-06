import argparse

from tei_utils import (
    configure_cli,
    build_tei,
    serialize,
    post_process,
    add_extra_newlines,
)

def cli():
    parser = argparse.ArgumentParser(
        description="Convert Śukasaptati-style plaintext into TEI-XML"
    )
    configure_cli(parser)
    args = parser.parse_args()

    root = build_tei(args.src, verse_only=args.verse_only)
    post_process(root)

    xml = serialize(root, pretty_print=not args.uglier)
    if args.prettier:
        xml = add_extra_newlines(xml)

    args.out.write_text(xml, encoding="utf-8")
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    cli()

