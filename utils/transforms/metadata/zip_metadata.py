#!/usr/bin/env python3
"""
Zips metadata files (.md and .html) into cumulative archives.
"""

import re
import sys
import zipfile
from pathlib import Path


def validate_data_version(project_root: Path):
    """
    Validates that __data_version__ in VERSION matches the latest date
    in the metadata files.
    """
    print("--- Validating data version ---")

    # 1. Read __data_version__ from VERSION file
    version_file = project_root / 'VERSION'
    if not version_file.exists():
        sys.exit(f"Error: VERSION file not found at {version_file}")
    version_content = version_file.read_text(encoding="utf-8")
    version_match = re.search(r'__data_version__\s*=\s*"([^"]+)"', version_content)
    if not version_match:
        sys.exit("Error: Could not find __data_version__ in VERSION file.")
    data_version = version_match.group(1)

    # 2. Find the latest date from all metadata files
    metadata_dir = project_root / 'metadata'
    md_files = list(metadata_dir.glob('*.md'))

    latest_date = ""

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")

        # Find Text Last Updated
        text_date_match = re.search(r"# Text Last Updated\s*\n\s*(\d{4}-\d{2}-\d{2})", content)
        if text_date_match:
            date = text_date_match.group(1)
            if date > latest_date:
                latest_date = date

        # Find Metadata Last Updated
        meta_date_match = re.search(r"# Metadata Last Updated\s*\n\s*(\d{4}-\d{2}-\d{2})", content)
        if meta_date_match:
            date = meta_date_match.group(1)
            if date > latest_date:
                latest_date = date

    if not latest_date:
        print("Warning: No dates found in metadata files to validate against.")

    # 3. Compare and exit on mismatch
    elif data_version != latest_date:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("Error: Version mismatch!")
        print(f"  VERSION file (__data_version__): {data_version}")
        print(f"  Latest date in metadata files:     {latest_date}")
        print("Please update the __data_version__ in the VERSION file.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1)

    print("Data version is up to date.")
    print("--- Validation complete ---\n")


def main(folder: str):
    """
    Zips .md files from metadata/ and .html files from metadata/transforms/html/
    into two separate zip files in metadata/transforms/cumulative/.
    """
    root = Path(folder)

    # Validate version first
    validate_data_version(root)

    metadata_folder = root / 'metadata'
    transforms_folder = metadata_folder / 'transforms'
    cumulative_folder = transforms_folder / 'cumulative'

    version_file = root / 'VERSION'

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
        html_files = list(html_source_folder.glob('**/*.html'))
        if html_files:
            with zipfile.ZipFile(html_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(version_file, version_file.name)
                for html_file in html_files:
                    arcname = html_file.relative_to(html_source_folder)
                    zipf.write(html_file, arcname)
            print(f'Wrote {len(html_files)} files to {html_zip_path}.')
        else:
            print(f'No .html files found in {html_source_folder}.')
    else:
        print(f"Directory not found: {html_source_folder}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')