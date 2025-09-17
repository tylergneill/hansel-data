#!/usr/bin/env python3
"""
Runs all metadata processing scripts:
1. Renders Markdown metadata to HTML.
2. Consolidates Markdown metadata to JSON.
3. Zips all metadata (.md, .html).
"""

import subprocess
from pathlib import Path

def main():
    """
    Orchestrates the metadata processing pipeline.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    
    # Scripts
    render_script = project_root / 'utils' / 'transforms' / 'metadata' / 'render_md_to_html.py'
    jsonify_script = project_root / 'utils' / 'transforms' / 'metadata' / 'jsonify_metadata.py'
    zip_script = project_root / 'utils' / 'transforms' / 'metadata' / 'zip_metadata.py'

    # 1. Render Markdown to HTML
    print("--- Rendering Markdown to HTML ---")
    subprocess.run(['python', str(render_script), str(project_root)])
    print("")

    # 2. Consolidate metadata to JSON
    print("--- Consolidating metadata to JSON ---")
    subprocess.run(['python', str(jsonify_script), str(project_root)])
    print("")

    # 3. Zip metadata files
    print("--- Zipping metadata files ---")
    subprocess.run(['python', str(zip_script), str(project_root)])
    print("")

    print("Metadata processing complete.")

if __name__ == '__main__':
    main()