from pathlib import Path
from lxml import etree
import csv, re

HERE = Path(__file__).parent
CLI_DIR = HERE.parent / "cli"
reports_dir = CLI_DIR / "reports"
jing_log = CLI_DIR / "build" / "jing.raw"
out_csv = HERE / "makefile_fails.csv"

rows = []

# --- Schematron (SVRL) ---
ns = {"svrl": "http://purl.oclc.org/dsdl/svrl"}
for f in sorted(reports_dir.glob("*.svrl.xml")):
    try:
        t = etree.parse(str(f))
    except Exception:
        continue
    for fa in t.xpath("//svrl:failed-assert", namespaces=ns):
        msg = " ".join(fa.xpath(".//svrl:text//text()", namespaces=ns)).strip()
        if not msg:
            continue
        # normalize to match Oxygen side: use the data XML basename + ".svrl.xml"
        data_name = f.name  # already like foo.svrl.xml in your flow
        rows.append([data_name, "SCH FAIL", "", "", "", msg])

# --- RELAX NG (Jing) ---
# Jing typically prints: /path/file.xml:LINE:COL: MESSAGE
pat = re.compile(r"""(?P<path>.*?\.xml):(?P<line>\d+):(?P<col>\d+):\s*(?P<msg>.+)""")
if jing_log.exists():
    for ln in jing_log.read_text(errors="ignore").splitlines():
        m = pat.match(ln.strip())
        if not m:
            continue
        path = Path(m.group("path")).name
        msg  = m.group("msg").strip()
        # normalize filename to the same key space as Oxygen CSV
        svrl_name = path.replace(".xml", ".svrl.xml")
        rows.append([svrl_name, "RNG FAIL", m.group("line"), "", "", msg])

# --- write merged CSV ---
with out_csv.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["svrl_file","status","line","test","role","message"])
    w.writerows(rows)

print(f"Wrote {out_csv} ({len(rows)} rows)")
