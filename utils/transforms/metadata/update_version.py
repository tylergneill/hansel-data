#!/usr/bin/env python3
"""
Updates the __data_version__ in the VERSION file based on the latest date
found in the metadata files.
"""

import re
import sys
from pathlib import Path

def main():
    """
    Updates the __data_version__ in the VERSION file.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent

    # 1. Find the latest date from all metadata files
    metadata_dir = project_root / 'metadata' / 'markdown'
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

        # Find Original Submission Last Updated
        submission_date_match = re.search(r"# Original Submission Last Updated\s*\n\s*(\d{4}-\d{2}-\d{2})", content)
        if submission_date_match:
            date = submission_date_match.group(1)
            if date > latest_date:
                latest_date = date

    if not latest_date:
        print("Warning: No dates found in metadata files. Not updating VERSION.")
        return

    # 2. Read and update __data_version__ in VERSION file
    version_file = project_root / 'VERSION'
    if not version_file.exists():
        sys.exit(f"Error: VERSION file not found at {version_file}")
    version_content = version_file.read_text(encoding="utf-8")

    version_match = re.search(r'__data_version__\s*=\s*"([^"]+)"', version_content)
    if not version_match:
        sys.exit("Error: Could not find __data_version__ in VERSION file.")
    
    current_version_date = version_match.group(1)

    if current_version_date != latest_date:
        print(f"Updating __data_version__ from {current_version_date} to {latest_date}")
        new_version_content = re.sub(
            r'__data_version__\s*=\s*"[^"]+"',
            f'__data_version__ = "{latest_date}"',
            version_content
        )
        version_file.write_text(new_version_content, encoding="utf-8")
        print("VERSION file updated.")
    else:
        print(f"__data_version__ is already up to date ({latest_date}).")

if __name__ == '__main__':
    main()
