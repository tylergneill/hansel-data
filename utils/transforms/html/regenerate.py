import os
import subprocess

PROJECT_ROOT = "/Users/tyler/Git/hansel/hansel-data"
TIER_II_XML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_ii/transforms")
TIER_II_HTML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_ii/transforms/html")
TIER_III_XML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_iii/transforms")
TIER_III_HTML_DIR = os.path.join(PROJECT_ROOT, "texts/tier_iii/transforms/html")
CONVERSION_SCRIPT = os.path.join(PROJECT_ROOT, "utils/transforms/xml/convert_xml_to_html.py")

def regenerate_html(xml_dir, html_dir):
    """
    Converts all XML files in a directory to HTML.
    """
    if not os.path.exists(html_dir):
        os.makedirs(html_dir)

    for filename in os.listdir(xml_dir):
        if filename.endswith(".xml"):
            xml_path = os.path.join(xml_dir, filename)
            html_path = os.path.join(html_dir, filename.replace(".xml", ".html"))
            subprocess.run(["python", CONVERSION_SCRIPT, xml_path, html_path])

if __name__ == "__main__":
    regenerate_html(TIER_II_XML_DIR, TIER_II_HTML_DIR)
    regenerate_html(TIER_III_XML_DIR, TIER_III_HTML_DIR)