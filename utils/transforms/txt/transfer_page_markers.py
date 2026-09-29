"""
Insert <p.N> or <N> page markers into the base at the page boundaries of the suggester.

The base is the text that receives the page markers; the suggester is a second
transcription of the same text that supplies them. Either can be OCR, a hand
transcription, or anything in between.

The suggester separates pages with "<p.N>" or "=== N ===" markers, each on its
own line (any surrounding blank lines are ignored); --marker picks one or takes
a custom regex, and by default whichever the suggester uses is detected. Text
before the first marker is ignored. For every boundary between
consecutive suggester pages, the last and first few characters on either side
are fuzzy-matched against the base, and "\\n\\n<N>\\n\\n" is inserted at the
best-scoring position (as <p.N> if the suggester uses <p.N>). Candidates are ranked by context similarity with a bonus
for landing near the position expected from the previous boundary plus the
suggester page length.

Only boundaries are inserted, so the first suggester page's marker is never
added. Existing page markers in the base are left in place.

Example:
    python transfer_page_markers.py --base base.txt --suggester suggester.txt -o output.txt --log log.txt
"""
import re
import argparse
import difflib
import unicodedata


# Page-marker formats that can be named instead of spelled out as a regex.
MARKERS = {
    "p": r"^\s*<p\.(\d+)>\s*$",              # <p.12>
    "equals": r"^\s*===\s*(\d+)\s*===\s*$",  # === 12 ===
}

CTX = 30


def marker_regex(value):
    """argparse type for --marker: 'auto', a name from MARKERS, or a regex."""
    return MARKERS.get(value, value)


def resolve_marker(marker, text):
    """Turn --marker auto into whichever named marker the text actually uses."""
    if marker != "auto":
        return marker
    for regex in MARKERS.values():
        pattern = re.compile(regex)
        if any(pattern.match(line) for line in text.splitlines()):
            return regex
    raise SystemExit("suggester: no page markers found; expected <p.12> or === 12 ===, "
                     "or pass --marker a regex")


def split_pages(text, marker):
    """Split `text` into [(page_number, page_text)] on lines matching `marker`.

    The page number is the marker's first capture group. Text before the first
    marker is dropped.
    """
    pattern = re.compile(marker)
    pages = []
    for line in text.splitlines(keepends=True):
        m = pattern.match(line)
        if m:
            pages.append((int(m.group(1)), []))
        elif pages:
            pages[-1][1].append(line)
    return [(pno, "".join(lines)) for pno, lines in pages]


def one_line(s):
    return re.sub(r"\s+", " ", s).strip()


def ratio(a, b):
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def normalize_with_map(raw):
    """Fold `raw` for matching and map each output char back to its raw index.

    NFKD-folds, lowercases, drops combining marks, erases line-end hyphenation
    ("-\\n" plus following whitespace), skips [...] bracket blocks, keeps only
    alphanumerics and | ' ", and collapses everything else to single spaces.

    Returns:
        (normalized string, list of raw indices, one per normalized char)
    """
    out = []
    out_map = []
    i = 0
    n = len(raw)

    def emit_space(raw_i):
        if out and out[-1] == " ":
            return
        out.append(" ")
        out_map.append(raw_i)

    while i < n:
        if raw.startswith("-\n", i):
            i += 2
            while i < n and raw[i].isspace():
                i += 1
            continue
        if raw[i] == "[":
            j = raw.find("]", i + 1)
            i = (j + 1) if j != -1 else (i + 1)
            continue
        ch = raw[i]
        if ch.isspace():
            emit_space(i)
            i += 1
            continue
        s = unicodedata.normalize("NFKD", ch.lower())
        s = "".join(c for c in s if not unicodedata.combining(c))
        kept = False
        for c in s:
            if c.isalnum() or c in {"|", "'", '"'}:
                out.append(c)
                out_map.append(i)
                kept = True
        if not kept:
            emit_space(i)
        i += 1

    while out and out[0] == " ":
        out.pop(0); out_map.pop(0)
    while out and out[-1] == " ":
        out.pop(); out_map.pop()

    return "".join(out), out_map


def topk_signature_hits(hay, sig, k=30, min_size=18):
    """Return up to k (start, size) longest-match hits of `sig` in `hay`, sorted by start."""
    hits = []
    masked = hay
    for _ in range(k):
        sm = difflib.SequenceMatcher(None, masked, sig, autojunk=False)
        a, b, size = sm.find_longest_match(0, len(masked), 0, len(sig))
        if size < min_size:
            break
        hits.append((a, size))
        masked = masked[:a] + (" " * size) + masked[a + size:]
    hits.sort()
    dedup = []
    last = None
    for a, size in hits:
        if last is None or abs(a - last) > 10:
            dedup.append((a, size))
            last = a
    return dedup


def snap_boundary(hay, b, left, right, K=40):
    best = None
    Lw = len(left)
    Rw = len(right)
    for bb in range(max(0, b - K), min(len(hay), b + K + 1)):
        left_slice  = hay[max(0, bb - Lw):bb]
        right_slice = hay[bb:min(len(hay), bb + Rw)]
        sL = ratio(left_slice, left[-len(left_slice):])
        sR = ratio(right_slice, right[:len(right_slice)])
        score = 0.5 * (sL + sR)
        if best is None or score > best[0]:
            best = (score, bb, sL, sR)
    return best


def pick_boundary_with_prior(hay, left, right, hits, expected_in_hay, scale_len, snap_k=40):
    best = None
    dist_scale = max(1500, int(0.5 * max(1, scale_len)))
    for a, size in hits:
        b0 = a + len(left)
        snapped = snap_boundary(hay, b0, left, right, K=snap_k)
        if snapped is None:
            continue
        ctx_score, b, sL, sR = snapped
        dist = abs(b - expected_in_hay)
        pos_bonus = 1.0 - min(1.0, dist / dist_scale)
        score = 0.75 * ctx_score + 0.25 * pos_bonus
        if best is None or score > best[0]:
            best = (score, b, sL, sR, pos_bonus, size)
    return best


def trim_span_around(raw, i):
    a = i
    while a > 0 and raw[a - 1] in " \t":
        a -= 1
    b = i
    while b < len(raw) and raw[b] in " \t":
        b += 1
    return a, b


def transfer_page_markers(suggester_src, base_src, marker="auto"):
    """Insert page markers into `base_src` at the page boundaries found in `suggester_src`.

    Args:
        suggester_src: Suggester text with "<p.N>" or "=== N ===" page markers.
        base_src: Base text to receive the markers: <p.N> if the suggester
            uses <p.N>, otherwise <N>.
        marker: "auto" to detect the suggester's marker format, or a regex
            whose group 1 is the page number.

    Returns:
        (patched base text, log text with one entry per inserted marker)
    """
    marker = resolve_marker(marker, suggester_src)
    prefix = "p." if marker == MARKERS["p"] else ""
    sugg_pages = split_pages(suggester_src, marker)

    sugg_pages_norm = [(pno, normalize_with_map(txt)[0], txt) for pno, txt in sugg_pages]
    base_norm, base_map = normalize_with_map(base_src)

    repls = []
    log = []
    cursor = 0

    for idx in range(len(sugg_pages_norm) - 1):
        p_i, s_i_norm, s_i_raw = sugg_pages_norm[idx]
        p_j, s_j_norm, s_j_raw = sugg_pages_norm[idx + 1]

        sugg_len = max(1, len(s_i_norm))
        left  = s_i_norm[-CTX:]
        right = s_j_norm[:CTX]
        sig   = left + right

        search_start = cursor + int(0.8 * sugg_len)
        win = int(0.8 * sugg_len) + 6000
        w0 = max(0, min(search_start, len(base_norm)))
        w1 = max(w0, min(w0 + win, len(base_norm)))
        hay = base_norm[w0:w1]

        hits = topk_signature_hits(hay, sig)
        if not hits:
            w1b = min(len(base_norm), w0 + win + int(0.6 * sugg_len))
            hay = base_norm[w0:w1b]
            hits = topk_signature_hits(hay, sig)

        expected = cursor + sugg_len
        expected_in_hay = max(0, min(expected - w0, len(hay)))

        picked = pick_boundary_with_prior(hay, left, right, hits, expected_in_hay, sugg_len) if hits else None

        if picked is None:
            boundary_norm = min(len(base_norm) - 1, cursor + sugg_len)
            score = 0.0; sL = sR = pos_bonus = None; hit_size = 0; cand_n = 0
        else:
            score, b_hay, sL, sR, pos_bonus, hit_size = picked
            boundary_norm = w0 + b_hay
            cand_n = len(hits)

        boundary_norm = max(0, min(boundary_norm, len(base_map) - 1))
        ins_at_raw = base_map[boundary_norm]

        a, b = trim_span_around(base_src, ins_at_raw)
        repls.append((a, b, f"\n\n<{prefix}{p_j}>\n\n"))

        cursor = boundary_norm

        sugg_after = one_line(s_j_raw[:220])
        base_after = one_line(base_src[b:b + 220])
        log.append(
            f"\n=== PAGE {p_j} (after {p_i}) ===\n"
            f"score={score:.3f}  cand={cand_n}  hit={hit_size}  "
            f"sL={sL if sL is not None else 'NA'}  sR={sR if sR is not None else 'NA'}  "
            f"pos={pos_bonus if pos_bonus is not None else 'NA'}\n\n"
            f"SUGGESTER AFTER:\n{sugg_after}\n\n"
            f"BASE AFTER:\n{base_after}\n"
        )

    patched = base_src
    for a, b, txt in sorted(repls, key=lambda x: x[0], reverse=True):
        patched = patched[:a] + txt + patched[b:]

    patched = re.sub(r"^﻿", "", patched)
    patched = re.sub(r"^\s+(?=\S)", "", patched)

    return patched, "".join(log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Insert <p.N> or <N> page markers into the base from the suggester's page breaks.")
    parser.add_argument("--base", required=True, help="Base text file to receive <p.N> or <N> markers")
    parser.add_argument("--suggester", required=True, help="Suggester text file with <p.N> or === N === page markers")
    parser.add_argument("--marker", default="auto", type=marker_regex,
                        help="suggester page marker: auto (default: <p.12> or === 12 ===, "
                             "detected), p, equals, or a regex whose group 1 is the page number")
    parser.add_argument("-o", "--output", required=True, help="Output text file")
    parser.add_argument("--log", help="Optional file for a per-boundary match log")
    args = parser.parse_args()

    with open(args.base, "r", encoding="utf-8") as f:
        base_src = f.read()
    with open(args.suggester, "r", encoding="utf-8") as f:
        suggester_src = f.read()

    result, log = transfer_page_markers(suggester_src, base_src, args.marker)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result)
    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(log)
