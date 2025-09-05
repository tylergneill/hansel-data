import argparse
import re

def process_hyphens_and_newlines(content, outpath):
    """
    returns content without hyphens or single-newlines, replaced with space or nothing as appropriate
    """

    replacement_patterns = [
        (r'-\n(<\d+>)\n\t', '\\1'),
        (r'([^\n/\|\]\)>}-])\n\t', '\\1'),
        (r'-\n\t', ''),
        (r'-\n(<\d+>)\n([^\n])', '\\1\\2'),
        (r'(\n[^\t\n-]+)\n([^\n\t])', '\\1 \\2'),
        (r'-\n', ''),
        (r'([^\n ])(<\d+> )', '\\1 \\2'),
    ]

    for pattern, replacement in replacement_patterns:
        while re.search(pattern, content):
            content = re.sub(pattern, replacement, content)

    return content

def _cli() -> None:
    ap = argparse.ArgumentParser(description="Process hyphens and newlines at line-end")
    ap.add_argument("src")
    ap.add_argument("out")
    args = ap.parse_args()

    with open(args.src) as f:
        content = f.read()
    processed_content = process_hyphens_and_newlines(content, args.out)
    with open(args.out, 'w') as f:
        f.write(processed_content)

    print("Wrote", args.out)

if __name__ == "__main__":
    _cli()
