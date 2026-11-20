"""Minimal stand-in for the ``saxon`` command line, built on pip ``saxonche``.

The Makefile runs Schematron as a series of XSLT transforms with the Saxon CLI
(``saxon -xsl:STYLESHEET -s:SOURCE -o:OUTPUT``): three to compile the .isosch into a
validator stylesheet, then one per XML file to produce its SVRL report. This script
accepts exactly that argument form, so the Makefile can use it in place of a
Homebrew/Java Saxon install:

    make validate SAXON="python saxon_cli.py" JING=pyjing

Only the three options the Makefile uses are supported. Exits non-zero if the
transform fails, like the real CLI.
"""
import sys
from pathlib import Path

from saxonche import PySaxonApiError, PySaxonProcessor


def parse_args(argv: list[str]) -> dict[str, str]:
    """Parse Saxon-style ``-name:value`` options into a dict (xsl, s, o)."""
    opts = {}
    for arg in argv:
        if not arg.startswith("-") or ":" not in arg:
            raise SystemExit(f"saxon_cli: unsupported argument {arg!r}")
        name, value = arg[1:].split(":", 1)
        if name not in ("xsl", "s", "o"):
            raise SystemExit(f"saxon_cli: unsupported option -{name}")
        opts[name] = value
    missing = {"xsl", "s", "o"} - opts.keys()
    if missing:
        raise SystemExit(f"saxon_cli: missing {', '.join('-' + m for m in sorted(missing))}")
    return opts


def main() -> int:
    opts = parse_args(sys.argv[1:])
    Path(opts["o"]).parent.mkdir(parents=True, exist_ok=True)
    with PySaxonProcessor(license=False) as proc:
        try:
            xslt = proc.new_xslt30_processor()
            executable = xslt.compile_stylesheet(stylesheet_file=opts["xsl"])
            executable.transform_to_file(source_file=opts["s"], output_file=opts["o"])
        except PySaxonApiError as e:
            print(f"saxon_cli: {e}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
