import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TIER_II_XML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_ii/transforms/xml")
TIER_II_PLAIN_DIR = os.path.join(PROJECT_ROOT, "texts/tier_ii/transforms/html/plain")
TIER_II_RICH_DIR = os.path.join(PROJECT_ROOT, "texts/tier_ii/transforms/html/rich")
TIER_III_XML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_iii/transforms/xml")
TIER_III_PLAIN_DIR = os.path.join(PROJECT_ROOT, "texts/tier_iii/transforms/html/plain")
TIER_III_RICH_DIR = os.path.join(PROJECT_ROOT, "texts/tier_iii/transforms/html/rich")
CONVERSION_SCRIPT = os.path.join(PROJECT_ROOT, "utils/transforms/html/convert_xml_to_html.py")

flag_map = {
    "bANa_kAdambarI": '--line-by-line',
    "kumArilabhaTTa_zlokavArtika": '--verse-only',
    "zukasaptati_s": '--line-by-line --extra-space-after-location',
    "zukasaptati_o": '--line-by-line --extra-space-after-location',
}

def regenerate_html(xml_dir, plain_dir, rich_dir):
    """
    Converts all XML files in a directory to both plain and rich HTML versions.
    """
    os.makedirs(plain_dir, exist_ok=True)
    os.makedirs(rich_dir, exist_ok=True)

    xml_files = [f for f in os.listdir(xml_dir) if f.endswith(".xml")]

    # Pass 1: Generate all plain files
    for filename in xml_files:
        stem = Path(filename).stem
        xml_path = os.path.join(xml_dir, filename)
        plain_html_path = os.path.join(plain_dir, filename.replace(".xml", ".html"))
        
        command = ["python", CONVERSION_SCRIPT, xml_path, plain_html_path, "--plain"]
        
        flags = flag_map.get(stem, "")
        if "--verse-only" in flags:
            command.append("--verse-only")
        
        subprocess.run(command)

    # Pass 2: Generate all rich files
    for filename in xml_files:
        stem = Path(filename).stem
        xml_path = os.path.join(xml_dir, filename)
        rich_html_path = os.path.join(rich_dir, filename.replace(".xml", ".html"))
        
        command = ["python", CONVERSION_SCRIPT, xml_path, rich_html_path]
        
        flags = flag_map.get(stem, "")
        if "--line-by-line" not in flags:
            command.append("--no-line-numbers")
        if "--verse-only" in flags:
            command.append("--verse-only")

        subprocess.run(command)

if __name__ == "__main__":
    regenerate_html(TIER_II_XML_DIR, TIER_II_PLAIN_DIR, TIER_II_RICH_DIR)
    regenerate_html(TIER_III_XML_DIR, TIER_III_PLAIN_DIR, TIER_III_RICH_DIR)