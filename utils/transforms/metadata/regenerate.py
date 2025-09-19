#!/usr/bin/env python3
"""
Runs all metadata processing scripts to regenerate cumulative files.
1. Deletes old generated files.
2. Renders Markdown metadata to HTML.
3. Consolidates Markdown metadata to JSON.
4. Zips all metadata (.md, .html).
"""

import subprocess
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
    render_script = project_root / 'utils' / 'transforms' / 'metadata' / 'render_md_to_html.py'
    jsonify_script = project_root / 'utils' / 'transforms' / 'metadata' / 'jsonify_metadata.py'
    zip_script = project_root / 'utils' / 'transforms' / 'metadata' / 'zip_metadata.py'

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
        for f in cumulative_dir.glob('metadata_md_*.zip'):
            os.remove(f)
            print(f"Deleted old version file: {f}")
        for f in cumulative_dir.glob('metadata_html_*.zip'):
            os.remove(f)
            print(f"Deleted old version file: {f}")
    print("--- Cleaning complete ---\n")


    # 2. Render Markdown to HTML
    print("--- Rendering Markdown to HTML ---")
    subprocess.run(['python', str(render_script), str(project_root)])
    print("")

    # 3. Consolidate metadata to JSON
    print("--- Consolidating metadata to JSON ---")
    subprocess.run(['python', str(jsonify_script), str(project_root)])
    print("")

    # 4. Zip metadata files
    print("--- Zipping metadata files ---")
    subprocess.run(['python', str(zip_script), str(project_root)])
    print("")

    print("Metadata regeneration complete.")

if __name__ == '__main__':
    main()
