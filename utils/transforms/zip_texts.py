#!/usr/bin/env python3
"""
Zips text files from tier_i, tier_ii, and tier_iii directories into cumulative archives.
"""

import sys
import zipfile
from pathlib import Path

def main(folder: str):
    """
    Zips files from each of the tier_i, tier_ii, and tier_iii directories into
    separate zip files in their respective transforms/cumulative/ subdirectories.
    """
    root = Path(folder)
    texts_folder = root / 'texts'

    # Get version
    version_file = root / 'VERSION'
    version_content = version_file.read_text(encoding="utf-8")
    version = version_content.strip().split('"')[1]

    # Define the directories and their corresponding zip file names
    tier_map = {
        "tier_i": f"tier_i_{version}.zip",
        "tier_ii": f"tier_ii_{version}.zip",
        "tier_iii": f"tier_iii_{version}.zip"
    }

    for tier_dir_name, zip_file_name in tier_map.items():
        source_dir = texts_folder / tier_dir_name
        if not source_dir.is_dir():
            print(f"Directory not found: {source_dir}")
            continue

        # Define the output directory and create it if it doesn't exist
        output_dir = source_dir / 'transforms' / 'cumulative'
        output_dir.mkdir(parents=True, exist_ok=True)

        # Define the full path for the output zip file
        zip_path = output_dir / zip_file_name

        # Get all files in the source directory (non-recursive)
        files_to_zip = [f for f in source_dir.iterdir() if f.is_file()]

        if files_to_zip:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in files_to_zip:
                    zipf.write(file, file.name)
            print(f"Wrote {len(files_to_zip)} files to {zip_path}.")
        else:
            print(f"No files found in {source_dir} to zip.")

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
