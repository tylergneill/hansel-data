import re

SECTION_RE = re.compile(r"^{([^}]+)}\s*$")
LOCATION_VERSE_RE = re.compile(r"^\[([^\]]+?)\]\t*(.*)$")  # [label] +/- tabbed verse content
VERSE_NUM_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)*)\s*([a-z]{1,4})?\s*$", re.I)
PAGE_RE = re.compile(r"^<(\d+)>$")  # <page>
PAGE_LINE_RE = re.compile(r"^<(\d+),(\d+)>$")  # <page,line>
ADDITIONAL_STRUCTURE_NOTE_RE = re.compile(r"^<[^\n>]+>$")  # other <...>
VERSE_MARKER_RE = re.compile(r"\|\| ([^|]{1,20}) \|\|(?: |$)")
VERSE_BACK_BOUNDARY_RE = re.compile(r"\|\|(?![^|]{1,20} \|\|)")
CLOSE_L_RE = re.compile(r"\|\|?(?:[ \n]|$)")
HYPHEN_EOL_RE = re.compile(r"-\s*$")  # tweak later if you need fancy hyphens
MID_LINE_PAGE_RE = re.compile(r"<(\d+)(?:,(\d+))?>")
COMBINED_VERSE_END_RE = re.compile(f"{VERSE_MARKER_RE.pattern}|{VERSE_BACK_BOUNDARY_RE.pattern}")
PENDING_HEAD_RE = re.compile(r"^(.*\|)\s*-$")
