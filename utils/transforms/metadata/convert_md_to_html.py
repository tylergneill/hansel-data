import markdown
from pathlib import Path
import re
import sys

from skrutable.transliteration import Transliterator

T = Transliterator(from_scheme='HK', to_scheme='IAST')

# Specify which metadata fields (H1 headers) to keep in the generated HTML.
# Comment out fields to hide them.
FIELDS_TO_KEEP = [
    'Title',
    'Authors',
    'Author',
    'Attributed Author',
    'Work Description',
    'Edition',
    'Edition Short',
    'Edition PDFs',
    'Genres',
    'Structure',
    'Translations',
    'Contributors',
    'Source Collection',
    'Source File Link',
    'Source File License',
    'HANSEL License',
    'Pandit Work ID',
    'Pandit Author IDs',
    'Pandit Attributed Author ID',
    # 'PDF Page Offset',
    'Extent',
    'File Size (KB)',
    'Digitization Notes',
    'File Creation Method',
    'Text Type',
    'Word Division Style',
    'Additional Files',
    'Additional Notes',
    'Original Submission Last Updated',
    'Text Last Updated',
    'Metadata Last Updated',
]

HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>metadata for {title}</title>
    <style>
        body {{ font-family: sans-serif; max-width: 700px; margin: 2em 0; padding-left: 6em; line-height: 1.6; }}
        h1, h2, h3 {{ border-bottom: 1px solid #ccc; }}
        pre, code {{ background-color: #f4f4f4; padding: 0.2em 0.4em; }}
    </style>
</head>
<body>
{body}
</body>
</html>"""


def filter_md_sections(md_content, allowed_fields):
    """
    Parses markdown content by H1 headers and retains only the sections
    whose headers are in allowed_fields.
    """
    # Regex to split by H1 headers: ^# Header Title
    # Capture the title so we can check it.
    # The split will result in: [preamble, title1, body1, title2, body2, ...]
    parts = re.split(r'^# (.+)$', md_content, flags=re.MULTILINE)

    filtered_chunks = []

    # Handle preamble (text before first header)
    if parts[0].strip():
        filtered_chunks.append(parts[0])

    # Iterate over pairs of (title, body)
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i+1]

        if title in allowed_fields:
            # Reconstruct the section
            filtered_chunks.append(f"# {title}{body}")

    return "".join(filtered_chunks)


def main(root_folder='.'):
    project_root = Path(root_folder).resolve()
    markdown_in_dir = project_root / 'metadata' / 'markdown'
    html_out_dir = project_root / 'metadata' / 'transforms' / 'html'

    # Make sure output dir exists
    html_out_dir.mkdir(parents=True, exist_ok=True)

    md_files = list(markdown_in_dir.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {markdown_in_dir}")
        return

    for md_file in md_files:
        with md_file.open(encoding="utf-8") as f:
            content = f.read()
            filtered_content = filter_md_sections(content, FIELDS_TO_KEEP)
            html_body = markdown.markdown(filtered_content, extensions=["mdx_gfm"], output_format='html5')
            
            # Prefix miscellaneous links to point to /static/data/
            html_body = re.sub(r'href="/?miscellaneous/', 'href="/static/data/miscellaneous/', html_body)

        wrapped_html = HTML_WRAPPER.format(title=T.transliterate(md_file.stem), body=html_body)

        out_file = html_out_dir / (md_file.stem + ".html")
        out_file.write_text(wrapped_html, encoding="utf-8")
        print(f"Rendered {md_file.relative_to(project_root)} -> {out_file.relative_to(project_root)}")

    print(f"\nProcessed {len(md_files)} files.")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
