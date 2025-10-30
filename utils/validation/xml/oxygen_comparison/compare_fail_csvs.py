# compare_csv.py  — multiset-aware comparison with counts
import csv, re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).parent
INPUT_A = HERE / "makefile_fails.csv"                  # Makefile (SVRL + optional Jing)
INPUT_B = HERE / "oxygen_fails.csv"                    # Oxygen (parsed blocks)

def norm_file(name: str) -> str:
    n = (name or "").strip()
    n = n.replace("\\", "/")
    n = n.split("/")[-1]
    n = n.replace(".xml.svrl.xml", ".svrl.xml")
    return n

def norm_status(s: str, msg: str = "") -> str:
    s = (s or "").strip().upper()
    m = (msg or "").lower()

    # Collapse common engine/severity tokens
    if s in {"JING", "ERROR", "ERR", "RNG", "RNG ERROR", "VALIDATION ERROR"}:
        return "RNG FAIL"
    if s in {"SCHEMATRON", "SCHEMATRON ERROR", "SAXON", "SAXON-HE", "SAXON-PE", "SAXON-EE", "SCH"}:
        return "SCH FAIL"
    # Heuristics if status missing/odd but message clearly from RNG or SCH
    if "schematron" in m or "assert" in m or "svrl" in m:
        return "SCH FAIL"
    return s or "RNG FAIL"  # default to RNG FAIL if empty/unknown

_qmap = {
    "“": '"', "”": '"', "„": '"',
    "’": "'", "‘": "'",
}
def norm_quotes(s: str) -> str:
    for k, v in _qmap.items():
        s = s.replace(k, v)
    return s

def norm_regex_tokens(s: str) -> str:
    # Oxygen often doubles backslashes; Jing often single-escapes
    s = s.replace("\\\\S+", r"\S+")
    s = s.replace("\\\\s+", r"\s+")
    s = s.replace("\\\\d+", r"\d+")
    return s

def norm_msg(m: str) -> str:
    m = (m or "").strip()
    m = norm_quotes(m)
    m = norm_regex_tokens(m)
    m = re.sub(r"\s+", " ", m)
    # Drop leading engine noise like "error:" or "fatal:"
    m = re.sub(r"^(error|fatal|warning)\s*:\s*", "", m, flags=re.I)
    return m

def load_counts(path: Path):
    c = Counter()
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            svrl = norm_file(row.get("svrl_file"))
            msg_raw = row.get("message") or ""
            status = norm_status(row.get("status"), msg_raw)
            msg = norm_msg(msg_raw)
            if not svrl or not msg:
                continue
            c[(svrl, status, msg)] += 1
    return c

A = load_counts(INPUT_A)  # Makefile
B = load_counts(INPUT_B)  # Oxygen

keysA, keysB = set(A), set(B)
onlyA = sorted(keysA - keysB)
onlyB = sorted(keysB - keysA)
both  = sorted(keysA & keysB)

def pr(title, rows, both_counts=False):
    print(f"{title}: {len(rows)}")
    for svrl, status, msg in rows:
        if both_counts:
            print(f"{svrl} — {status} — {msg}  [Makefile:{A.get((svrl,status,msg),0)}  Oxygen:{B.get((svrl,status,msg),0)}]")
        else:
            n = A.get((svrl,status,msg),0) or B.get((svrl,status,msg),0)
            print(f"{svrl} — {status} — {msg}  [count:{n}]")

pr("Makefile-only", onlyA)
print()
pr("Oxygen-only", onlyB)
print()
pr("Shared (both)", both, both_counts=True)

# CSV artifacts with counts
def write_csv(path: Path, rows, include_both=False):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if include_both:
            w.writerow(["svrl_file","status","message","count_makefile","count_oxygen"])
            for k in rows:
                svrl,status,msg = k
                w.writerow([svrl,status,msg,A.get(k,0),B.get(k,0)])
        else:
            w.writerow(["svrl_file","status","message","count"])
            for k in rows:
                svrl,status,msg = k
                n = A.get(k,0) or B.get(k,0)
                w.writerow([svrl,status,msg,n])

write_csv(HERE / "only_makefile.csv", onlyA)
write_csv(HERE / "only_oxygen.csv", onlyB)
write_csv(HERE / "shared_both.csv", both, include_both=True)
print("\nWrote: only_makefile.csv, only_oxygen.csv, shared_both.csv")
