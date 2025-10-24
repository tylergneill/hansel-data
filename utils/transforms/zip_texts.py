#!/usr/bin/env python3
"""
Zips text files from originals and masters directories into cumulative archives.

This script creates several zip files:
- 'originals_misc.zip' from files in 'texts/originals'.
- 'txt.zip' from files in 'texts/masters/txt'.
- 'xml.zip' from files in 'texts/masters/xml'.
- 'html_plain.zip' from files in 'texts/transforms/html/plain'.
- 'html_rich.zip' from files in 'texts/transforms/html/rich'.
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
    """Orchestrates zipping of files based on folder structures."""
    root = Path(folder)
    texts_folder = root / 'texts'
    output_dir = texts_folder / 'transforms' / 'cumulative'
    version_file = root / 'VERSION'

    # originals
    source_dir_originals = texts_folder / 'originals'
    zip_path = output_dir / 'originals_misc.zip'
    create_zip(source_dir_originals, zip_path, version_file)

    # txt
    source_dir_txt = texts_folder / 'masters' / 'txt'
    zip_path_txt = output_dir / 'txt.zip'
    create_zip(source_dir_txt, zip_path_txt, version_file)

    # xml
    source_dir_xml = texts_folder / 'masters' / 'xml'
    zip_path_xml = output_dir / f'xml.zip'
    create_zip(source_dir_xml, zip_path_xml, version_file)

    # html files (plain and rich)
    source_dir_html_plain = texts_folder / 'transforms' / 'html' / 'plain'
    zip_path_html_plain = output_dir / f'html_plain.zip'
    create_zip(source_dir_html_plain, zip_path_html_plain, version_file)

    source_dir_html_rich = texts_folder / 'transforms' / 'html' / 'rich'
    zip_path_html_rich = output_dir / f'html_rich.zip'
    create_zip(source_dir_html_rich, zip_path_html_rich, version_file)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')