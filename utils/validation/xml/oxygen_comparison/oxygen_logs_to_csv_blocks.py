import csv, pathlib, re

HERE = pathlib.Path(__file__).parent
text = (HERE / "oxygen_logs.txt").read_text(encoding="utf-8", errors="ignore")
blocks = text.strip().split("\n\n")  # blank line separates problems
rows = []

def norm_svrl_name(path):
    name = pathlib.Path(path).name
    # Oxygen sometimes yields foo.xml.svrl.xml; makefile uses foo.svrl.xml
    name = name.replace(".xml.svrl.xml", ".svrl.xml")
    return name

for b in blocks:
    # turn the block's "Key: Value" lines into a dict
    pairs = re.findall(r'^(.*?):\s*(.*)$', b, re.MULTILINE)
    if not pairs: 
        continue
    d = {k.strip(): v.strip() for k, v in pairs}
    file_path = d.get("Main validation file") or d.get("System ID")
    if not file_path:
        continue

    engine = (d.get("Engine name") or "").lower()
    if "schematron" in engine:
        status = "SCH FAIL"
    elif "jing" in engine:
        status = "RNG FAIL"
    else:
        status = (d.get("Severity") or "error").upper()

    desc = d.get("Description", "")
    line = d.get("Start location", "").split(":")[0] if "Start location" in d else ""

    rows.append([
        norm_svrl_name(file_path) + ".svrl.xml" if not file_path.endswith(".svrl.xml") else norm_svrl_name(file_path),
        status,
        line,
        "",  # test
        "",  # role
        desc
    ])

with (HERE / "oxygen_fails.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["svrl_file","status","line","test","role","message"])
    w.writerows(rows)

print(f"Wrote oxygen_fails.csv ({len(rows)} rows)")
