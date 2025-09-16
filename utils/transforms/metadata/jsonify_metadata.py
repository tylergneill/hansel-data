#!/usr/bin/env python3
"""
Consolidate Markdown‑based metadata files into a single JSON file.

Changes:
• Each record now includes `"Filename": "<basename.md>"`.
• The top‑level key is the filename (stem) transliterated from HK → IAST
  using skrutable.Transliterator.
"""

import json
import os
import re
import sys
from pathlib import Path


from skrutable.transliteration import Transliterator
T = Transliterator(from_scheme="HK", to_scheme="IAST")   # HK → IAST

_heading = re.compile(r'^# (.+)')

def _normalise(section_lines):
    while section_lines and section_lines[0] == '':
        section_lines.pop(0)
    while section_lines and section_lines[-1] == '':
        section_lines.pop()

    if section_lines and all(re.match(r'^[-*]\s+', l) for l in section_lines):
        return [re.sub(r'^[-*]\s+', '', l) for l in section_lines]

    return ' '.join(section_lines).strip()

def parse_markdown(path: Path) -> dict:
    """Return a dict of metadata, including the filename."""
    meta, key, buf = {}, None, []
    for raw in path.read_text(encoding='utf-8').splitlines():
        h = _heading.match(raw)
        if h:
            if key is not None:
                meta[key] = _normalise(buf)
            key, buf = h.group(1).strip(), []
        else:
            buf.append(raw.rstrip('\n'))
    if key is not None:
        meta[key] = _normalise(buf)

    # Add filename field
    meta["Filename"] = path.name[:-3]
    return meta

def get_file_extension(filename_without_extension):
    search_folder = './texts/tier_i'
    for item in os.listdir(search_folder):
        base_name, extension = os.path.splitext(item)
        if base_name.lower() == filename_without_extension.lower():
            return extension

def main(folder: str):
    root = Path(folder)
    metadata_folder = root / 'metadata'
    consolidated = {}
    for md in metadata_folder.glob('*.md'):
        record = parse_markdown(md)
        translit_key = T.transliterate(md.stem)
        consolidated[translit_key] = record

    for k, record in consolidated.items():

        # convert file size (kb) to float
        consolidated[k]['File Size (KB)'] = float(consolidated[k]['File Size (KB)'])

        # detect and store Tier I file type
        consolidated[k]['Tier I Filetype'] = get_file_extension(consolidated[k]['Filename'])

    metadata_file = metadata_folder / 'transforms' / 'cumulative' / 'metadata.json'
    metadata_file.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2),
                   encoding='utf-8')
    print(f'Wrote {metadata_file} ({len(consolidated)} files).')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
