"""
Round-trip check for the txt <-> XML pipeline.

For every project edition (or the stems given on the command line) this runs

    txt --builder--> XML --writer--> txt' --builder--> XML'

entirely in memory (nothing under texts/ is written) and reports two things:

* txt fidelity: how many lines of txt' differ from the original txt, both
  strictly and ignoring blank lines and trailing whitespace (the layout the XML
  does not record; see "Round trip" in texts/DATA_MODEL.md). The chāyā companion
  file is compared the same way.
* XML stability: whether XML' is identical to XML. This is the stronger promise:
  whatever the writer produces must rebuild into exactly the same edition.

Usage:
    python utils/transforms/xml/roundtrip.py              # summary table
    python utils/transforms/xml/roundtrip.py --diff STEM  # also show diffs for one text
    python utils/transforms/xml/roundtrip.py --strict     # exit 1 unless every text is exact

Exit status is 1 if any XML' differs from XML (or, with --strict, if any txt
differs in more than layout).
"""
import argparse
import difflib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(PROJECT_ROOT)]

from conversion_utils import serialize  # noqa: E402
from convert_plaintext_to_xml import load_chaya_list  # noqa: E402
from convert_xml_to_plaintext import convert_element  # noqa: E402
from tei_builder import TeiTextBuilder  # noqa: E402
from utils.transforms.flag_map import flag_map  # noqa: E402

TXT_DIR = PROJECT_ROOT / "texts" / "project_editions" / "txt"


def build(txt: str, flags: str, chaya: list[str]):
    """Build the TEI <text> element from txt, as the regen pipeline does."""
    builder = TeiTextBuilder(
        line_by_line="--line-by-line" in flags,
        drama="--drama" in flags,
        chaya_list=chaya,
    )
    return builder.build(txt.splitlines())


CUE_RE = re.compile(r"^\S+ —")  # a speaker cue starts a new speech
STRUCTURAL_RE = re.compile(r"^(\t|\[[^\]]+\]\t|[\[{<].*[\]}>]$)")


def layout_insensitive(lines: list[str], line_by_line: bool = True) -> list[str]:
    """Normalize what the XML does not record: blank lines, trailing whitespace
    and, in a text without <lb> (no --line-by-line), where prose lines break.
    There each prose run (up to the next marker, verse line or speaker cue) is
    rejoined into one line; verse lines and marker lines stay as they are."""
    out, prose = [], []
    for line in lines:
        line = line.rstrip()
        if line_by_line:
            if line.strip():
                out.append(line)
            continue
        if not line.strip():
            continue  # blank lines do not end a paragraph (only markers and cues do)
        if STRUCTURAL_RE.match(line) or CUE_RE.match(line):
            if prose:
                out.append(" ".join(prose))
                prose = []
        if STRUCTURAL_RE.match(line):
            out.append(line)
        else:
            prose.append(line.strip())
    if prose:
        out.append(" ".join(prose))
    return out


def chaya_layout_insensitive(lines: list[str]) -> list[str]:
    """Chāyā entries: also treat any leading indentation as one tab."""
    return [re.sub(r"^[ \t]+", "\t", l) for l in layout_insensitive(lines)]


def diff_count(a: list[str], b: list[str]) -> int:
    """Number of changed lines between two line lists (added + removed)."""
    return sum(1 for d in difflib.ndiff(a, b) if d[:1] in "+-")


def check(stem: str, show_diff: bool = False) -> dict:
    flags = flag_map.get(stem, "")
    src = (TXT_DIR / f"{stem}.txt").read_text(encoding="utf-8")
    chaya_path = TXT_DIR / "chaya" / f"{stem}.txt"
    chaya_src = chaya_path.read_text(encoding="utf-8") if chaya_path.exists() and "--chaya" in flags else ""
    chaya = load_chaya_list(chaya_path) if chaya_src else []

    xml = serialize(build(src, flags, chaya))
    txt2, chaya2 = convert_element(build(src, flags, chaya), "--extra-space-after-location" in flags)
    try:
        xml2 = serialize(build(txt2, flags, chaya2))
    except Exception as e:  # the writer's output does not even rebuild
        xml2 = f"rebuild failed: {e!r}"
    chaya_txt2 = "\n\n".join(chaya2) + "\n" if chaya2 else ""

    a, b = src.splitlines(), txt2.splitlines()
    lbl = "--line-by-line" in flags
    result = {
        "stem": stem,
        "lines": len(a),
        "strict": diff_count(a, b),
        "layout": diff_count(layout_insensitive(a, lbl), layout_insensitive(b, lbl)),
        "chaya": diff_count(chaya_layout_insensitive(chaya_src.splitlines()),
                            chaya_layout_insensitive(chaya_txt2.splitlines())),
        "xml_same": xml == xml2,
    }
    if show_diff:
        sys.stdout.writelines(difflib.unified_diff(
            [l + "\n" for l in layout_insensitive(a, lbl)], [l + "\n" for l in layout_insensitive(b, lbl)],
            f"{stem}.txt (original)", f"{stem}.txt (round trip)", n=1))
        sys.stdout.writelines(difflib.unified_diff(
            xml.splitlines(True), xml2.splitlines(True), f"{stem} XML", f"{stem} XML'", n=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stems", nargs="*", help="Text stems to check (default: all)")
    parser.add_argument("--diff", metavar="STEM", help="Show the txt and XML diffs for one text")
    parser.add_argument("--strict", action="store_true", help="Fail unless every txt round trip is exact up to layout")
    args = parser.parse_args()

    stems = args.stems or sorted(p.stem for p in TXT_DIR.glob("*.txt"))
    if args.diff:
        check(args.diff, show_diff=True)
        return

    results = [check(s) for s in stems]
    print(f"{'text':34} {'lines':>6} {'strict':>7} {'layout':>7} {'chāyā':>6}  XML'=XML")
    for r in results:
        print(f"{r['stem']:34} {r['lines']:6} {r['strict']:7} {r['layout']:7} {r['chaya']:6}  {'yes' if r['xml_same'] else 'NO'}")
    failed = [r for r in results if not r["xml_same"] or (args.strict and (r["layout"] or r["chaya"]))]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
