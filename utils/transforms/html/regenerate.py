import os
import subprocess
from pathlib import Path

PROJECT_ROOT = "/Users/tyler/Git/hansel/hansel-data"
TIER_II_XML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_ii/transforms/xml")
TIER_II_HTML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_ii/transforms/html")
TIER_III_XML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_iii/transforms/xml")
TIER_III_HTML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_iii/transforms/html")
CONVERSION_SCRIPT = os.path.join(PROJECT_ROOT, "utils/transforms/html/convert_xml_to_html.py")

flag_map = {
    "bANa_kAdambarI": '--line-by-line',
    "kumArilabhaTTa_zlokavArtika": '--verse-only',
    "zukasaptati_s": '--line-by-line --extra-space-after-location',
    "zukasaptati_o": '--line-by-line --extra-space-after-location',
}

def regenerate_html(xml_dir, html_dir):
    """
    Converts all XML files in a directory to HTML.
    """
    if not os.path.exists(html_dir):
        os.makedirs(html_dir)

    for filename in os.listdir(xml_dir):
        if filename.endswith(".xml"):
            stem = Path(filename).stem
            xml_path = os.path.join(xml_dir, filename)
            html_path = os.path.join(html_dir, filename.replace(".xml", ".html"))
            
            command = ["python", CONVERSION_SCRIPT, xml_path, html_path]
            
            flags = flag_map.get(stem, "")
            if "--line-by-line" not in flags:
                command.append("--no-line-numbers")
            if "--verse-only" in flags:
                command.append("--verse-only")

            subprocess.run(command)

if __name__ == "__main__":
    regenerate_html(TIER_II_XML_DIR, TIER_II_HTML_DIR)
    regenerate_html(TIER_III_XML_DIR, TIER_III_HTML_DIR)
