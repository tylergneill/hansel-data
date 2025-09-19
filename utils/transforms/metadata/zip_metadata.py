#!/usr/bin/env python3
"""
Zips metadata files (.md and .html) into cumulative archives.
"""

import sys
import zipfile
from pathlib import Path


def main(folder: str):
    """
    Zips .md files from metadata/ and .html files from metadata/transforms/html/
    into two separate zip files in metadata/transforms/cumulative/.
    """
    root = Path(folder)
    metadata_folder = root / 'metadata'
    transforms_folder = metadata_folder / 'transforms'
    cumulative_folder = transforms_folder / 'cumulative'

    # Get version
    version_file = root / 'VERSION'
    version_content = version_file.read_text(encoding="utf-8")
    version = version_content.strip().split('"')[1]

    # Create cumulative directory if it doesn't exist
    cumulative_folder.mkdir(exist_ok=True)

    # 1. Zip markdown files from metadata/
    md_zip_path = cumulative_folder / 'metadata_md.zip'
    md_files = list(metadata_folder.glob('*.md'))

    if md_files:
        with zipfile.ZipFile(md_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(version_file, version_file.name)
            for md_file in md_files:
                zipf.write(md_file, md_file.name)
        print(f'Wrote {len(md_files)} files to {md_zip_path}.')
    else:
        print(f'No .md files found in {metadata_folder}.')

    # 2. Zip HTML files from metadata/transforms/html/
    html_source_folder = transforms_folder / 'html'
    html_zip_path = cumulative_folder / 'metadata_html.zip'

    if html_source_folder.is_dir():
        # Using '**/*.html' to match user request "html/**"
        html_files = list(html_source_folder.glob('**/*.html'))
        if html_files:
            with zipfile.ZipFile(html_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(version_file, version_file.name)
                for html_file in html_files:
                    # arcname should be relative to the source folder to maintain structure
                    arcname = html_file.relative_to(html_source_folder)
                    zipf.write(html_file, arcname)
            print(f'Wrote {len(html_files)} files to {html_zip_path}.')
        else:
            print(f'No .html files found in {html_source_folder}.')
    else:
        print(f"Directory not found: {html_source_folder}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
