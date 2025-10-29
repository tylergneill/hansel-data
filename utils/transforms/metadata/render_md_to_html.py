import markdown
from pathlib import Path
import sys

from skrutable.transliteration import Transliterator

T = Transliterator(from_scheme='HK', to_scheme='IAST')

HTML_WRAPPER = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>metadata for {title}</title>
    <style>
        body {{ font-family: sans-serif; max-width: 700px; margin: 2em auto; line-height: 1.6; }}
        h1, h2, h3 {{ border-bottom: 1px solid #ccc; }}
        pre, code {{ background-color: #f4f4f4; padding: 0.2em 0.4em; }}
    </style>
</head>
<body>
{body}
</body>
</html>"""

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
            html_body = markdown.markdown(content, extensions=["mdx_gfm"], output_format='html5')

        wrapped_html = HTML_WRAPPER.format(title=T.transliterate(md_file.stem), body=html_body)

        out_file = html_out_dir / (md_file.stem + ".html")
        out_file.write_text(wrapped_html, encoding="utf-8")
        print(f"Rendered {md_file.relative_to(project_root)} -> {out_file.relative_to(project_root)}")

    print(f"\nProcessed {len(md_files)} files.")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
