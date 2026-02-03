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

    # Set default for PDF Page Offset if missing
    if "PDF Page Offset" not in meta:
        meta["PDF Page Offset"] = ["1 → 1"]

    # Add filename field
    meta["Filename"] = path.name[:-3]
    return meta

def get_file_extension(filename_without_extension):
    search_folder = './texts/original_submissions'
    for item in os.listdir(search_folder):
        base_name, extension = os.path.splitext(item)
        if base_name.lower() == filename_without_extension.lower():
            return extension

def parse_additional_files(file_list):
    """
    Parse a list of markdown links with descriptions into structured data.
    Format: [Text](URL): Description
    """
    parsed_files = []
    if not file_list:
        return parsed_files
    
    if isinstance(file_list, str):
        file_list = [file_list]

    for file_string in file_list:
        # Expected format: [Text](URL): Description or [Text](URL)
        start_bracket = file_string.find('[')
        end_bracket = file_string.find(']')
        start_paren = file_string.find('(')
        end_paren = file_string.find(')')
        
        if start_bracket != -1 and end_bracket != -1 and start_paren != -1 and end_paren != -1:
            if start_bracket < end_bracket < start_paren < end_paren:
                text = file_string[start_bracket+1:end_bracket]
                url = file_string[start_paren+1:end_paren]
                description = file_string[end_paren+1:].strip()
                if description.startswith(':'):
                    description = description[1:].strip()
                
                # Replace miscellaneous path
                if url.startswith('miscellaneous/'):
                     url = '/static/data/' + url
                elif url.startswith('/miscellaneous/'):
                     url = '/static/data' + url

                # Filetype
                filetype = ''
                lower_url = url.lower()
                if lower_url.endswith('.txt'): filetype = '.txt'
                elif lower_url.endswith('.xml'): filetype = '.xml'
                elif lower_url.endswith('.html'): filetype = '.html'
                elif lower_url.endswith('.doc'): filetype = '.doc'
                
                parsed_files.append({
                    'text': text, 
                    'url': url, 
                    'description': description,
                    'filetype': filetype
                })
    return parsed_files

def main(folder: str):
    root = Path(folder)
    metadata_markdown_in_dir = root / 'metadata' / 'markdown'

    # Get version
    version_file = root / 'VERSION'
    version_content = version_file.read_text(encoding="utf-8")
    version_match = re.search(r'__data_version__\s*=\s*"([^"]+)"', version_content)
    if not version_match:
        sys.exit("Could not find __data_version__ in VERSION file.")
    version = version_content.splitlines()[0].split('"')[1]

    consolidated = {}
    for md in metadata_markdown_in_dir.glob('*.md'):
        record = parse_markdown(md)
        translit_key = T.transliterate(md.stem)
        consolidated[translit_key] = record

    for k, record in consolidated.items():

        # convert file size (kb) to float
        consolidated[k]['File Size (KB)'] = float(consolidated[k]['File Size (KB)'])

        # detect and store original file type
        consolidated[k]['Original Submission Filetype'] = get_file_extension(consolidated[k]['Filename'])
        
        # parse additional files
        if 'Additional Files' in consolidated[k]:
             consolidated[k]['Additional Files'] = parse_additional_files(consolidated[k]['Additional Files'])

    # Add version to the consolidated data
    consolidated['version'] = version

    metadata_json_file = root / 'metadata' / 'transforms' / 'metadata.json'
    metadata_json_file.write_text(json.dumps(consolidated, ensure_ascii=False, indent=2),
                   encoding='utf-8')
    print(f'Wrote {metadata_json_file} ({len(consolidated)} files).')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
