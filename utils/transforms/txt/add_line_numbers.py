"""
Add [page,line] reference tags to a structured text file.

Example:
    python add_line_numbers.py -i input.txt -o output.txt
"""
import re
import argparse


def insert_line_numbers(text, count_structural=False):
    lines = text.splitlines()
    output = []

    current_page = None
    line_number_within_page = 1

    for line in lines:
        stripped = line.strip()

        # Detect page marker like <1> or <327> and track current page
        if re.fullmatch(r"<\d+>", stripped):
            current_page = int(stripped.strip("<>"))
            line_number_within_page = 1
            output.append(line)
            continue

        # Only increment for real content lines (not blank, not markers, not standalone refs)
        is_structural = re.fullmatch(r"\{[^}]+\}", stripped)
        if stripped and not (
            re.fullmatch(r"<[^>]+>", stripped) or
            (is_structural and not count_structural) or
            re.fullmatch(r"\[\d+(?:,\d*)?\]", stripped) or
            re.fullmatch(r"\[\]", stripped)
        ):
            line_number_within_page += 1

        # Replace bare [] with [page,line] using current page from most recent <...> marker
        def repl(match):
            return f"[{current_page},{line_number_within_page}]"

        line = re.sub(r"\[\]", repl, line)
        output.append(line)

    return "\n".join(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fill in [] reference tags with [page,line] numbers.")
    parser.add_argument("-i", "--input", required=True, help="Input text file")
    parser.add_argument("-o", "--output", required=True, help="Output text file")
    parser.add_argument("--count-structural", action="store_true", help="Count {structural} markers as lines")
    args = parser.parse_args()

    with open(args.input, "r") as f:
        text = f.read()

    result = insert_line_numbers(text, count_structural=args.count_structural)

    with open(args.output, "w") as f:
        f.write(result)
