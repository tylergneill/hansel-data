"""
Fill in empty <> page markers and report any that break the sequence.

Page markers sit alone on their own line and hold a page number (<327>). A
marker left empty (<>) is filled with the number that continues the run of
markers around it: the previous page number plus the step, where the step is
inferred from the last two known numbers (default +1).

Every filled or existing number is then checked against the expected sequence,
and any marker that does not continue the pattern is reported as a violation.
Markers that are not purely numeric (<kādambarī |>) are left untouched and
ignored by both the filling and the checking.

Examples:
    python fill_page_numbers.py -i input.txt -o output.txt
    python fill_page_numbers.py -i input.txt --check
"""
import re
import argparse
import sys


PAGE_MARKER = re.compile(r"^<(\d*)>$")


def fill_page_numbers(text, start=None, step=None):
    """Fill empty <> markers in `text` and collect sequence violations.

    Numbering runs forward from the first known page number. Empty markers take
    the previous number plus the step; the step is inferred from the first two
    known numbers unless given explicitly. A marker whose existing number does
    not match the expected value is left as written and reported, and numbering
    resumes from the number actually present so a single correction does not
    cascade into a violation on every later marker.

    Args:
        text: Full file contents.
        start: Page number for the first marker. Defaults to the first known
            number counted back over any empty markers preceding it, or 1 if
            every marker is empty.
        step: Increment between markers. Defaults to the most common difference
            between adjacent known numbers, or 1.

    Returns:
        A (result, filled, violations) tuple. `result` is the text with empty
        markers filled, joined with "\\n" (any trailing newline in the input is
        dropped). `filled` is a list of (line_number, page) for markers this run
        filled in. `violations` is a list of (line_number, found, expected) for
        markers whose number broke the sequence.
    """
    lines = text.splitlines()

    # Numbers of every numeric marker, with its position in the marker run, so
    # a step can be measured only between markers that are actually adjacent.
    known = []
    position = 0
    for line in lines:
        match = PAGE_MARKER.match(line.strip())
        if not match:
            continue
        if match.group(1):
            known.append((position, int(match.group(1))))
        position += 1

    if step is None:
        deltas = [second - first
                  for (pos_a, first), (pos_b, second) in zip(known, known[1:])
                  if pos_b - pos_a == 1]
        # Source pages are sometimes skipped, so the most common adjacent
        # difference is a safer step than any single pair.
        step = max(set(deltas), key=deltas.count) if deltas else 1
    if start is None:
        # Walk back from the first known number over any empty markers ahead of it.
        start = known[0][1] - known[0][0] * step if known else 1

    output = []
    filled = []
    violations = []
    expected = start

    for index, line in enumerate(lines, start=1):
        match = PAGE_MARKER.match(line.strip())
        if not match:
            output.append(line)
            continue

        found = match.group(1)
        if found:
            page = int(found)
            if page != expected:
                violations.append((index, page, expected))
            expected = page + step
            output.append(line)
        else:
            page = expected
            filled.append((index, page))
            expected = page + step
            output.append(f"<{page}>")

    return "\n".join(output), filled, violations


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill in empty <> page markers and check the sequence.")
    parser.add_argument("-i", "--input", required=True, help="Input text file")
    parser.add_argument("-o", "--output", help="Output text file (omit with --check)")
    parser.add_argument("--check", action="store_true", help="Only report violations; write nothing")
    parser.add_argument("--start", type=int, help="Page number of the first marker")
    parser.add_argument("--step", type=int, help="Increment between markers (default: inferred)")
    args = parser.parse_args()

    if not args.check and not args.output:
        parser.error("either -o/--output or --check is required")

    with open(args.input, "r") as f:
        text = f.read()

    result, filled, violations = fill_page_numbers(text, start=args.start, step=args.step)

    for line_number, page in filled:
        print(f"filled line {line_number}: <{page}>")
    for line_number, found, expected in violations:
        print(f"line {line_number}: found <{found}>, expected <{expected}>", file=sys.stderr)

    if not args.check:
        with open(args.output, "w") as f:
            f.write(result)

    sys.exit(1 if violations else 0)
