# Staggered dialogue verse — plan

## Background

In `texts/project_editions/txt/bhAskarabhaTTa_unmattarAghava.txt`, a single verse
is sometimes split across several speaker turns, with each turn's fragment
printed further to the right than the last — visually continuing the verse
line across the page (see scan of KM 14, verse 39). In the source .txt this is
marked with leading tabs before each fragment, with the tab count incrementing
by 1 for each successive fragment in the run:

```
r"amaḥ —	kimatrAsmahe |
	vatsA yAhi gRhaM vrajAma        (1 tab)
lakSmaNaH —
		kimidaM gehaM                  (2 tabs)
r"amaH —
			kutaH                          (3 tabs)
lakSmaNaH —
				kAnane vatsyAmaH               (4 tabs)
r"amaH —
	kathamAgatA vanabhuvaM         (resets to 1 tab; new pAda)
...
```

The tab count resets to 1 at the start of each new pāda (quarter-verse) run —
i.e. whenever the count would not be exactly `previous + 1`. Confirmed against
verse 39 (4 pādas, 4 separate stagger runs, tab counts 1→2→3, 1→2→3, 1, 1→2).

Currently (as of commit 7383515) `tei_builder.py`'s `_handle_verse_line` only
splits on the *first* tab (`line.split("\t", 1)`), so for lines with 2+ tabs,
the extra tabs just leak into the verse payload text untouched. Confirmed in
the already-built `texts/project_editions/xml/bhAskarabhaTTa_unmattarAghava.xml`,
e.g.:

```xml
<l>	kimidaṃ gehaṃ<caesura/><lb n="24"/></l>
<l>		kutaḥ<caesura/><lb n="26"/></l>
<l>			kānane<caesura/><lb n="28"/> vatsyāmaḥ<caesura/><lb n="29"/></l>
```

Each fragment is its own `<l>` inside its own `<lg>` inside its own `<sp>`
(one per speaker turn) — they are not siblings within a shared `<lg>`.

## Goal

Render each fragment in HTML (and conceptually in XML) offset to the right by
an amount corresponding to where the previous fragment(s) in the same
stagger run ended — reproducing the print layout — but using an **akṣara
(syllable) count**, not pixel/character measurement, as the offset unit, per
user direction. skrutable.scansion.Scanner already provides IAST syllabification:

```python
from skrutable.scansion import Scanner
v = Scanner().scan("kimidaṃ gehaṃ", from_scheme="IAST")
syllables = [s for s in v.text_syllabified.replace("\n", " ").split(" ") if s]
# -> ['ki', 'mi', 'daM', 'ge', 'haM']  (5 aksaras)
```

## Division of labor (per user direction — keep tei_builder.py minimal)

### 1. `tei_builder.py` — mechanical only, no new dependency

In `_handle_verse_line` (around line 611), currently:

```python
pre_tab, after_tab = line.split("\t", 1)
```

This only handles a single leading tab. Needs to instead count *all* leading
tabs on the line (after any speaker-cue / pre_tab head text is separated out)
and record that count on the `<l>` element as `rend="indent(N)"`, stripping
the tabs from the text so they don't leak into the verse payload as they do
today. No akṣara counting, no run-tracking, no skrutable import here — just
faithfully preserve "this line had N leading tabs" as structured data instead
of literal whitespace.

Needs care around:
- Lines with a speaker-cue `pre_tab` (non-tab-indented case) vs. pure
  tab-indented continuation lines — only the latter get `rend="indent(N)"`.
- Interaction with existing tab-based dispatch logic elsewhere in the file
  (lines ~26, ~240, ~329, ~393, ~549-558 per earlier grep) — audit each for
  whether it assumes single-tab or needs updating for multi-tab lines.

### 2. `convert_xml_to_html.py` — owns the interesting logic

This module already walks the document sequentially to build the HTML tree
(see `process_lg_content`, `_render_l_as_spans`, and the `sp` handling loop
around line 909+), so it's the natural place to track cross-turn state.

Needs to:
- Track the current stagger run as `<sp>`/`<l>` elements are visited in
  order: a fragment with `rend="indent(N)"` where N == running max + 1
  continues the current run; N == 1 (or non-incrementing) starts a new run.
- For a fragment with `indent(N)`, look back at the N-1 prior fragments in
  the *current run*, syllabify each via `skrutable.scansion.Scanner`
  (`from_scheme="IAST"`), sum their syllable counts, and use that sum as the
  offset.
- Apply the offset as a left-margin style on that fragment's rendered block
  (each `<l>` renders as a block-level `<span>` under `.lg > span` per
  `rich_content_style.css:24`, so `margin-left` on that span is the natural
  hook). Needs a chosen CSS unit per akṣara (e.g. some `em`/`ch` value tuned
  by eye against the source scan — not yet decided).
- Import `skrutable.scansion` in this file (new dependency for this module
  specifically, matching existing precedent of `skrutable` usage in
  `utils/transforms/metadata/*.py`).

## Open questions / not yet decided

- Exact CSS unit per akṣara (em/ch value) — needs visual tuning against the
  source scan once a first draft renders.
- Where exactly in `convert_xml_to_html.py`'s per-`<sp>` loop (around line
  909-1024) to hook in "is this the start of a new run vs. continuing one" —
  needs a closer read of that loop's existing state variables
  (`speech_div`, `verses_ul`, etc.) to avoid duplicating/conflicting with
  existing reset logic (e.g. the `verses_ul = None` reset on `p`/location
  markers, which may or may not coincide with pāda/run boundaries).
- Whether `<l rend="indent(N)">` should carry N as the raw tab count (as
  currently planned) or something else — settled: raw tab count, mechanical
  only in tei_builder.py.
- No decision yet on plain-text (`.txt` export) or non-`rich-text` output —
  presumably stagger indentation is a rich/HTML-only concern and plain-text
  keeps literal tabs or drops them; not discussed.

## Status

Implemented (2026-07-16):

1. `tei_builder.py` `_handle_verse_line`: counts all leading tabs, strips them
   from the payload, and records `rend="indent(N)"` (N = total tab count) on
   the new `<l>` for pure tab-indented lines with N ≥ 2. Plain single-tab
   verse lines are unchanged (no `rend`), so only the 8 staggered fragments
   of verse 39 differ in the regenerated XML.
2. `convert_xml_to_html.py`: `_stagger_offsets_aksaras` computes TWO offsets
   per `<l>`, one per display mode, counting akṣaras via
   `skrutable.scansion.Scanner`:
   - line mode (`.show-line-breaks`): fragments stack per physical print
     line — rend N == fragments-so-far + 1 continues, else reset; a wrapped
     fragment (internal `<caesura/>`, e.g. "kānane / vatsyāmaḥ") restarts
     the run at its last wrapped part (back at the print margin).
   - paragraph mode (default): each `<l>` displays as one line, so print
     wraps/margin returns don't exist — fragments stack until a half-/full-
     verse boundary (fragment ending ।/॥), from the first rend-carrying
     fragment until the verse closes with ॥. This also catches rend-less
     mid-verse fragments like "tvaṃ cāhaṃ janakātmajā ca" (a print-line
     start that still needs a paragraph-mode indent).
   The offsets are emitted as inline CSS custom properties on the pāda `<li>`
   (`--stagger-para` / `--stagger-lines`); mode-scoped rules in
   `rich_content_style.css` (both the hansel-app `static/web/css` copy and
   the standalone `assets/css` copy in this repo) apply them as
   `text-indent`, which shifts only the first displayed line. Unit:
   `STAGGER_CH_PER_AKSARA = 2.75` (ch per akṣara, ~average IAST syllable
   width; tune by eye against the scan). Verified against KM 13–14: both
   half-verse ladders close at 38 akṣaras (2 × 19, śārdūlavikrīḍita).
   Plain-text HTML and condensed/chāyā paths are untouched.
3. Afterthought (xml→txt, known to be otherwise stale): `<l rend="indent(N)">`
   re-emits N tabs, deferred past a leading bare-cue `<lb>` so they don't
   strand on the cue's line (this also restores the previously-lost single
   tab of ordinary bare-cue verse lines); the final `\t\s+` → `\t` cleanup
   was narrowed to `\t +` so it no longer swallows the extra tabs.
