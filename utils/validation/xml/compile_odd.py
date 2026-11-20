"""Compile a TEI ODD customization into RELAX NG and ISO Schematron.

HANSEL's schema is written as an ODD (``schemas/hansel.odd``), a customization of
SARIT's ``sarit.odd``. Validators can't read an ODD directly, so this script runs the
TEI Stylesheets over it, with SaxonC-HE (pip ``saxonche``) as the XSLT engine:

1. ``odds/odd2odd.xsl``       expands the ODD against the TEI P5 source (p5subset.xml)
                              into a self-contained "compiled ODD";
2. ``odds/odd2relax.xsl``     turns the compiled ODD into RELAX NG (XML syntax);
3. ``odds/extract-isosch.xsl`` pulls out its embedded ISO Schematron rules.

The outputs (``<stem>.rng`` and ``<stem>.isosch``) are committed, so day-to-day
validation never needs this script. Rerun it only when the ODD changes, normally via
``make schemas`` in this directory, which also downloads the pinned inputs.

Fed ``sarit.odd``, this reproduces the behaviour of the repo's ``sarit.rng`` exactly
(identical error counts on all HANSEL files), which is how the pipeline was checked.

Usage:
    python compile_odd.py ODD --stylesheets DIR --p5subset FILE [--out-dir DIR]
"""
import argparse
import sys
from pathlib import Path

from saxonche import PySaxonProcessor

# Versions the committed schemas were compiled with. The Makefile downloads these;
# change them together, then recompile and recommit hansel.rng / hansel.isosch.
TEI_STYLESHEETS_VERSION = "7.58.0"
TEI_P5_VERSION = "4.10.2"


def compile_odd(odd: Path, stylesheets: Path, p5subset: Path, out_dir: Path) -> tuple[Path, Path]:
    """Compile ``odd`` to ``out_dir/<stem>.rng`` and ``out_dir/<stem>.isosch``.

    The intermediate compiled ODD goes to a ``build/`` folder beside the outputs
    (git-ignored). Returns the paths of the RNG and Schematron files.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    build_dir = out_dir / "build"
    build_dir.mkdir(exist_ok=True)
    stem = odd.stem
    compiled = build_dir / f"{stem}.compiled.odd"
    rng = out_dir / f"{stem}.rng"
    isosch = out_dir / f"{stem}.isosch"

    with PySaxonProcessor(license=False) as proc:
        xslt = proc.new_xslt30_processor()

        # 1. ODD -> compiled ODD. defaultSource tells odd2odd where the TEI P5
        #    definitions live, instead of fetching them from tei-c.org.
        step1 = xslt.compile_stylesheet(stylesheet_file=str(stylesheets / "odds/odd2odd.xsl"))
        step1.set_parameter("defaultSource", proc.make_string_value(p5subset.resolve().as_uri()))
        step1.transform_to_file(source_file=str(odd), output_file=str(compiled))

        # 2. compiled ODD -> RELAX NG
        step2 = xslt.compile_stylesheet(stylesheet_file=str(stylesheets / "odds/odd2relax.xsl"))
        step2.transform_to_file(source_file=str(compiled), output_file=str(rng))

        # 3. compiled ODD -> ISO Schematron
        step3 = xslt.compile_stylesheet(stylesheet_file=str(stylesheets / "odds/extract-isosch.xsl"))
        step3.transform_to_file(source_file=str(compiled), output_file=str(isosch))

    return rng, isosch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("odd", type=Path, help="ODD file to compile, e.g. schemas/hansel.odd")
    parser.add_argument("--stylesheets", type=Path, required=True,
                        help=f"Unpacked TEI Stylesheets {TEI_STYLESHEETS_VERSION} (the folder containing odds/)")
    parser.add_argument("--p5subset", type=Path, required=True,
                        help=f"TEI P5 {TEI_P5_VERSION} p5subset.xml")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Where to write <stem>.rng and <stem>.isosch (default: beside the ODD)")
    args = parser.parse_args()

    for path in (args.odd, args.stylesheets / "odds/odd2odd.xsl", args.p5subset):
        if not path.exists():
            print(f"compile_odd: missing {path}", file=sys.stderr)
            return 1

    rng, isosch = compile_odd(args.odd, args.stylesheets, args.p5subset, args.out_dir or args.odd.parent)
    print(f"Wrote {rng}\nWrote {isosch}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
