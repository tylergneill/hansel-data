# Bare speaker-cue line-count bug

## Status: confirmed, NOT fixed

## What "bolding" issue this superseded

An earlier bug in this same area (speaker names not rendering bold when a
bare cue — `"name —"` with nothing else on the line — preceded a verse) is
FIXED (`SPEAKER_RE` in `utils/transforms/xml/tei_builder.py` now matches
`r"^(\S+) —\s*(.*)$"`, allowing trailing content to be empty). Not discussed
further here.

## The actual, still-open bug: line-count double-counting

The source `.txt` distinguishes two shapes:

```
sūtradhāraḥ — ((nepathyābhimukhamavalokya ।)) ārye, itastāvat ।
```
(speaker cue and speech share one physical line)

vs.

```
sūtradhāraḥ —
((nepathyābhimukhamavalokya ।)) ārye, itastāvat ।
```
(speaker cue alone on its own physical line; speech starts on the next)

This distinction must be preserved downstream — each shape should produce a
different physical-line count.

### Confirmed case: `bhAskarabhaTTa_unmattarAghava.txt`, p.14 l.1

Printed source (KM p.14): `लक्ष्मणः —` and `ताताज्ञया यन्त्रिताः ।` are on
the **same physical line**, both labeled `14,1`.

Current HTML rendering instead shows:
```
(p.14, l.1)
लक्ष्मणः —
    (p.14, l.2) ताताज्ञया यन्त्रिताः ।
p.14, l.3
रामः —
    (p.14, l.4) आयाताः कति वा वयं कथय मे
```

i.e. the cue and its speech are being counted as two separate physical
lines (l.1 and l.2) when the source has them on one (l.1) — an
over-counting/double-counting bug. Every line after this point in the text
is shifted accordingly (रामः's line shows l.3/l.4 instead of the correct
l.2/l.3).

Current tracked XML for this passage
(`texts/project_editions/xml/bhAskarabhaTTa_unmattarAghava.xml`):
```xml
<p xml:id="p14_l1" n="14,1">lakṣmaṇaḥ — <lb n="2"/></p>
<lg xml:id="p14_l1_2" n="14,1">
  <l>		tātājñayā yantritāḥ ।<lb n="3"/></l>
```

The `<lb n="2"/>` immediately after the bare cue is what's causing the
speech line to be treated as line 2 instead of staying on line 1 — but per
the corrected understanding above, that's wrong for THIS case (cue + speech
share a physical line in the print source). The `<lg>` itself is still
(coincidentally, not correctly) labeled `n="14,1"`, but the `<lb n="2"/>`
and `<lb n="3"/>` markers cause the HTML renderer to display l.2 for the
speech and shift everything after.

### What actually needs to happen

The txt→XML step needs to tell these two source shapes apart and encode
them differently, so the physical-line count matches the print source
exactly:

- Bare cue on its own line, speech starts next line → cue consumes one
  physical line, speech starts the next (two physical lines total).
- Cue and speech share one physical line → only one physical line total,
  no extra `<lb>` inserted between them.

Not yet investigated: how `_handle_line`/`_open_sp` in `tei_builder.py`
currently distinguishes (or fails to distinguish) these two source shapes,
and where exactly the erroneous extra `<lb>` is being introduced for the
same-line case specifically. Needs fresh investigation — do not assume the
old (superseded) bolding-fix diagnosis still applies; re-derive the root
cause for this specific miscount from scratch.

## Next steps when resuming

1. Re-read `_handle_line` / bare-cue branch in `tei_builder.py` fresh, with
   the corrected understanding above (same-line vs. separate-line cue
   shapes both exist in source and must be told apart).
2. Find where the txt source actually signals which shape a given case is
   (presumably: whether there's text after the cue's `—` on the same raw
   line, vs. a blank/newline before the next content).
3. Fix so physical-line count matches print source exactly for both shapes.
4. Re-verify against p.14 l.1 (this file) and any other bare-cue instances
   across `bhAskarabhaTTa_unmattarAghava.txt`, `bhagavadajjuka.txt`,
   `kRSNamizra_prabodhacandrodaya.txt` (13+ occurrences previously noted
   across these three texts, exact count/locations not reconfirmed here).
5. Full regen + diff against tracked baseline for all affected texts,
   checking line numbers match the printed edition exactly (not shifted).
