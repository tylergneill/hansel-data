import markdown
from pathlib import Path

from skrutable.transliteration import Transliterator

T = Transliterator(from_scheme='HK', to_scheme='IAST')

MD_DIR = Path("")
OUT_DIR = MD_DIR / "transforms"

# Make sure output dir exists
OUT_DIR.mkdir(parents=True, exist_ok=True)

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

for md_file in MD_DIR.glob("*.md"):
    with md_file.open(encoding="utf-8") as f:
        content = f.read()
        html_body = markdown.markdown(content, extensions=["mdx_gfm"], output_format='html5')

    wrapped_html = HTML_WRAPPER.format(title=T.transliterate(md_file.stem), body=html_body)

    out_file = OUT_DIR / (md_file.stem + ".html")
    out_file.write_text(wrapped_html, encoding="utf-8")
    print(f"Rendered {md_file.name} -> {out_file.name}")
