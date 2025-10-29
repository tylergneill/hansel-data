#!/usr/bin/env python3
"""
Runs all metadata processing scripts to regenerate cumulative files.
1. Deletes old generated files.
2. Updates the data version.
3. Renders Markdown to HTML.
4. Consolidates Markdown metadata to JSON.
"""

import subprocess
import sys
from pathlib import Path
import os

def main():
    """
    Orchestrates the metadata processing pipeline.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent

    metadata_dir = project_root / 'metadata'
    html_out_dir = metadata_dir / 'transforms' / 'html'
    cumulative_dir = metadata_dir / 'transforms' / 'cumulative'
    
    # Scripts
    update_version_script = project_root / 'utils' / 'transforms' / 'metadata' / 'update_version.py'
    render_script = project_root / 'utils' / 'transforms' / 'metadata' / 'render_md_to_html.py'
    jsonify_script = project_root / 'utils' / 'transforms' / 'metadata' / 'jsonify_metadata.py'

    # 1. Clean output directories
    print("--- Cleaning output directories ---")
    # Clean HTML directory
    if html_out_dir.exists():
        # Get expected html files from md files
        md_files = metadata_dir.glob('*.md')
        expected_html_stems = {p.stem for p in md_files}
        for html_file in html_out_dir.glob('*.html'):
            if html_file.stem not in expected_html_stems:
                os.remove(html_file)
                print(f"Deleted stale file: {html_file}")

    # Clean cumulative directory of versioned files
    if cumulative_dir.exists():
        for f in cumulative_dir.glob('metadata_*.json'):
            os.remove(f)
            print(f"Deleted old version file: {f}")
    print("--- Cleaning complete ---\n")

    try:
        # 2. Update data version
        print("--- Updating data version ---")
        subprocess.run(['python', str(update_version_script)], check=True)
        print("")

        # 3. Render Markdown to HTML
        print("--- Rendering Markdown to HTML ---")
        subprocess.run(['python', str(render_script), str(project_root)], check=True)
        print("")

        # 4. Consolidate metadata to JSON
        print("--- Consolidating metadata to JSON ---")
        subprocess.run(['python', str(jsonify_script), str(project_root)], check=True)
        print("")

        print("Metadata regeneration complete.")

    except subprocess.CalledProcessError:
        print("\n--- Metadata regeneration FAILED. ---")
        sys.exit(1)

if __name__ == '__main__':
    main()