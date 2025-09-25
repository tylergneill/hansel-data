#!/usr/bin/env python3
"""
Zips text files from tier_i, tier_ii, and tier_iii directories into cumulative archives.

- For tier_i, it creates a single 'tier_i_misc.zip' from files in 'texts/tier_i'.
- For tier_ii and tier_iii, it creates three archives:
  - '_txt.zip' from plaintext files in the tier's root directory.
  - '_html.zip' from 'transforms/html'.
  - '_xml.zip' from 'transforms/xml'.
"""

import sys
import zipfile
from pathlib import Path

def create_zip(source_dir, zip_path, version_file):
    """Helper function to create a zip archive from a source directory."""
    if not source_dir.is_dir():
        print(f"Source directory not found, skipping: {source_dir}")
        return

    files_to_zip = [f for f in source_dir.iterdir() if f.is_file() and f.stem != '.DS_Store']

    if files_to_zip:
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(version_file, version_file.name)
            for file in files_to_zip:
                zipf.write(file, file.name)
        print(f"Wrote {len(files_to_zip)} files to {zip_path}.")
    else:
        print(f"No files found in {source_dir} to zip.")

def main(folder: str):
    """Orchestrates zipping of text tiers based on their structure."""
    root = Path(folder)
    texts_folder = root / 'texts'

    # Get version
    version_file = root / 'VERSION'
    version_content = version_file.read_text(encoding="utf-8")
    version = version_content.strip().split('"')[1]

    # --- Tier i ---
    tier_i_dir = texts_folder / 'tier_i'
    if tier_i_dir.is_dir():
        output_dir_i = tier_i_dir / 'transforms' / 'cumulative'
        zip_path_i = output_dir_i / 'tier_i_misc.zip'
        create_zip(tier_i_dir, zip_path_i, version_file)

    # --- Tier ii and iii ---
    for tier in ['tier_ii', 'tier_iii']:
        tier_dir = texts_folder / tier
        if not tier_dir.is_dir():
            print(f"Directory not found: {tier_dir}")
            continue

        output_dir = tier_dir / 'transforms' / 'cumulative'
        
        # txt files
        zip_path_txt = output_dir / f'{tier}_txt.zip'
        create_zip(tier_dir, zip_path_txt, version_file)

        # html files
        source_dir_html = tier_dir / 'transforms' / 'html'
        zip_path_html = output_dir / f'{tier}_html.zip'
        create_zip(source_dir_html, zip_path_html, version_file)

        # xml files
        source_dir_xml = tier_dir / 'transforms' / 'xml'
        zip_path_xml = output_dir / f'{tier}_xml.zip'
        create_zip(source_dir_xml, zip_path_xml, version_file)

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')