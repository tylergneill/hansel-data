## Original bug

In `bhAskarabhaTTa_unmattarAghava` (and other drama texts), some speaker
designations render unbolded in the rich HTML (e.g. "rāmaḥ —" at p.7 l.21).

Root cause: the source `.txt` convention for "new speaker, cue immediately
followed by a verse, no dialogue on the same line" is a bare line:

```
rāmaḥ —

	prāṇapriyāṃ prāptavatīṃ ...
```

`SPEAKER_RE` in `utils/transforms/xml/tei_builder.py` was
`r"^(\S+) — (.*)$"` — it requires a space *and* trailing content after the
em dash, so a bare `"name —"` line never matched. It fell through to
generic prose handling and got absorbed as literal text inside the
*previous* speaker's still-open `<sp>` block, so it never got wrapped in
`<speaker>`/`<span class="speaker">` and never rendered bold.

Confirmed as a systemic issue, not a one-off: same shape recurs in
`bhAskarabhaTTa_unmattarAghava.txt` (13x), `bhagavadajjuka.txt`, and
`kRSNamizra_prabodhacandrodaya.txt` (e.g. `kṣamā —` at 4,66).

## Fix #1 — DONE, believed solid

`utils/transforms/xml/tei_builder.py:49`
```python
SPEAKER_RE = re.compile(r"^(\S+) — (.*)$")
```
→
```python
SPEAKER_RE = re.compile(r"^(\S+) —\s*(.*)$")
```
Now a bare `"name —"` line matches with empty `trailing_text`, which
correctly calls `_open_sp(speaker_name)` and returns (no stray `<p>`
created).

**Caution**: do NOT widen this further without re-checking
`kRSNamizra_prabodhacandrodaya.xml` line ~2,90 (`cārvākaḥ — deva —`),
where `"deva —"` is a vocative address embedded in trailing text, not a
new speaker — pre-existing, separate, out-of-scope issue, unrelated to
this fix.

## Fix #2 — DONE, believed solid

**Regression found + fixed**: `utils/transforms/html/convert_xml_to_html.py`,
in the `sp` handling loop, the plain-text renderer only prepends
`"speakerName — "` when it hits the *first `<p>` child* of an `<sp>`
(`if speaker_name and not speaker_shown:` in the `sp_child.tag == "p"`
branch). Fix #1 now produces `<sp>` elements whose first child is an
`<lg>` (verse), not a `<p>` — so `speaker_shown` never got set, and the
speaker name/dash got wrongly prepended onto the *next unrelated
paragraph* instead.

Fixed by adding the same `speaker_shown` logic to the
`elif sp_child.tag == "lg":` branch (currently in place, ~line 999-1005 of
`convert_xml_to_html.py`): when it's the first content in the `<sp>`, emit
`<p>{speaker_name} — </p>` into `speech_div_plain` right before calling
`process_lg_content`, and set `speaker_shown = True`.

## Fix #3 attempt A (empty `<p>` for CSS spacing) — REVERTED, bad idea

First attempt: to restore the vertical gap between `<span class="speaker">`
and the following `<ul class="verses">` (gap normally comes from an
intervening `<p>`, but the bare-cue case has no `<p>` at all), I inserted
an **empty `<p/>`** purely as a structural hook for whatever CSS rule
creates the gap.

**User feedback: this was a bad idea.** An empty `<p>` with no semantic
content, inserted purely to trigger an unknown CSS selector in a
*different* repo (this repo's only stylesheet,
`texts/transforms/html/rich/assets/css/rich_content_style.css`, has no
`.speaker`/`.verses`/`.speech` rules — the real site CSS lives elsewhere,
not accessible here), is a guess dressed up as a fix. **Reverted.**
Current state of `convert_xml_to_html.py` has NO empty-`<p>` spacing hack.
The vertical-spacing-gap problem is UNSOLVED and out of scope until we
have a better idea (possibly this needs to be solved in the site's CSS
repo, not here, since we can't see the actual rule).

## Fix #3 attempt B (line-label placement) — SUPERSEDED, wrong diagnosis

Second attempt (before realizing the deeper bug): tried to fix the empty
`<p>` from attempt A also mispositioning the `(p.7, l.21)` line-number
label — moving it off the (now-deleted) empty `<p>` and onto the `<p>`
itself. This was built on top of attempt A's already-rejected empty-`<p>`
hack, so it's moot. Also, per the next section, the *diagnosis* was wrong:
the issue isn't just label *placement*, it's label *counting*.

## THE REAL BUG (confirmed, root-caused, NOT YET FIXED)

User showed a diff screenshot: after fix #1, the verse `prāṇapriyāṃ
prāptavatīṃ...` (originally line 22 in the printed edition) was being
labeled `(p.7, l.21)` instead of `(p.7, l.22)` — i.e. line numbering
silently shifted back by one, and this affects EVERY line after every
bare speaker cue for the rest of the text (confirmed via diff: e.g.
`p.11, l.17` → wrongly became `p.11, l.16`, etc., cascading).

**This is a real physical-line miscount, not just a display/placement
bug.** Confirmed against the actual printed edition (user provided a
photo of the source page): `rāmaḥ —` occupies its own physical line, and
`prāṇapriyāṃ prāptavatīṃ...` starts on the NEXT line. These are two
distinct physical lines that must both be counted.

### Root cause, precisely

In `utils/transforms/xml/tei_builder.py`, `_handle_line`, the drama
speaker-line branch (~line 344-364):

```python
if s.drama:
    speaker_match = SPEAKER_RE.match(line)
    if speaker_match:
        speaker_name = speaker_match.group(1)
        trailing_text = speaker_match.group(2).strip()
        self._open_sp(speaker_name)
        if trailing_text:
            ...
            self._process_content_with_midline_elements(trailing_text, "prose", ...)
            self._finalize_physical_line(line)
        return
```

When `trailing_text` is empty (bare cue), `_open_sp` is called but then
**nothing else happens for that line** — no
`_process_content_with_midline_elements` call, meaning `_emit_lb` (the
function that increments `s.lb_count`, the physical-line counter — see
`_emit_lb` at ~line 430) never fires for this line. The physical line the
cue occupies is completely invisible to the counter, and the *next* thing
that happens (the verse's own `<lg n="7,21">`, whose `n=` is just
inherited from `s.current_loc_label` set by the original `[7,21]` bracket
marker and never re-synced) ends up mislabeled as line 21, when it should
be 22.

Contrast with the **with-dialogue** case (`trailing_text` non-empty):
`_process_content_with_midline_elements(..., "prose", ...)` DOES call
`_emit_lb`, which increments `lb_count` and appends a real `<lb n="X">` to
the `<p>` holding the dialogue text — that's what correctly marks "this
line is done, the next one starts now."

Before fix #1, this bug was accidentally *masked*: the bare-cue line fell
through to generic prose handling (since `SPEAKER_RE` didn't match at
all), which happened to still call the normal prose-line machinery
(`_emit_lb` etc.), producing a stray unbolded `<p>rāmaḥ — <lb n="22"/></p>`
that nobody noticed was also doing double duty as the line counter. Fix
#1 correctly stopped creating that stray `<p>`, but in doing so also
silently dropped the line-counting side effect that nobody knew was
bundled into it.

### Fix attempted (in progress, NOT working yet)

**Step 1, `tei_builder.py`** (currently in the working tree, seems
correct in isolation): in the bare-cue branch, emit a real `<lb>` element
directly as a child of `<sp>` (sibling of `<speaker>`, before whatever
comes next) so the physical line is still counted, mirroring what the
with-dialogue path does via its own trailing `<lb>`:

```python
speaker_name = speaker_match.group(1)
trailing_text = speaker_match.group(2).strip()
self._open_sp(speaker_name)
if not trailing_text:
    # Bare cue ("name —") occupies its own physical line, with no
    # dialogue <p> to hold an <lb>. Emit one directly on <sp> so the
    # line is still counted (mirrors the with-dialogue path below,
    # which emits its own trailing <lb> at the end of the <p>).
    self._emit_lb(s.current_sp, line)
    self._finalize_physical_line(line)
if trailing_text:
    ...
```

Verified via regeneration into scratch (NOT applied to tracked XML yet):
produces `<sp who="rāmaḥ"><speaker>rāmaḥ</speaker><lb n="22"/><lg
xml:id="p7_l21" n="7,21">...` — the `<lb n="22"/>` correctly appears
before `<lg>`, and the verse's own trailing `<lb>` correctly bumps to
`n="23"` for the second pāda. This part looks right.

Also confirmed a **second real case** exists combining a page break with a
bare cue: `bhAskarabhaTTa_unmattarAghava.txt` line 697 (`<14>` / `[14,1]`
/ `lakṣmaṇaḥ —`) and `bhagavadajjuka.txt` line 1089 (`<48>` / `[48,1]` /
`rāmilakaḥ —`). Per explicit user instruction: **when a page break is
pending at a bare cue, the page-break label SHOULD still render, on its
own line, before the speaker attribution** — unlike a plain line-break
label, which should be suppressed entirely (see next section).

**Step 2, `convert_xml_to_html.py`** (in progress, BROKEN, currently
reverted-in-spirit but the attempted patch is still visible in the diff
and needs rework): the `for sp_child in element.iterchildren():` loop in
the `sp`-handling section only dispatches on `sp_child.tag in
("speaker", "p", "lg", "stage")` — a bare `<lb>` child (my new Step 1
output) falls through completely unhandled by the existing code, so the
line-count fix in the XML wouldn't actually reach the HTML rendering
without new handling.

Attempted addition: handle `sp_child.tag == "lb"` by advancing
`self.current_line` and then dropping `self.pending_label` (per user's
explicit instruction: suppress the marker entirely for a bare-cue line,
neither before nor after the speaker attribution) — **except** when
`self.pending_label` is already a `pb-label` (page break) at that point,
in which case render it in its own `<p>`, before the `<span
class="speaker">`.

**This attempt broke the structure.** Verified via regeneration into
scratch (`unmattaraghava_rich_v2.html`): inserting the `<lb>` as the new
*first* child of `<sp>` means `speech_div` gets lazily created for the
`<lb>` before the loop reaches `<lg n="7,21">`. The `<lg>`'s own
location-marker check (`if n_attr and ',' in n_attr: if n_attr !=
last_sp_location:`, ~line 932-941 of `convert_xml_to_html.py`) then
treats `"7,21"` as a **brand-new** location (since `last_sp_location` is
still `"7,20"` from the previous `<sp>` — the `<lb>` branch never updates
it), incorrectly resetting `speech_div`/`speech_div_plain`/`verses_ul` to
`None` and emitting a **duplicate** `<h3 id="7_21">` heading mid-`<sp>`.
Result: the speaker span ends up orphaned alone in its own
`<div class="speech rich-text">`, followed by the h3, followed by a
*second* speech div containing just the verse — visually broken, and the
verse's first-pāda label reverted to showing `21` instead of the intended
`22` (still wrong, in a new way).

### What's left to figure out (NOT YET RESOLVED)

Root problem: introducing a real `<lb>` as an `<sp>` child changes which
child the loop sees "first," which conflicts with the existing
location-marker-change detection logic (designed around `<p>`/`<lg>`
being the meaningful location-bearing elements, not `<lb>`).

Two directions considered, not yet chosen or attempted:

1. **Peek-ahead in the HTML converter**: when the loop sees a bare
   `<lb>` as the first child of `<sp>`, look ahead to the *next* sibling's
   `n=` attribute and pre-set `last_sp_location` to that value, so the
   subsequent `<lg n="7,21">` doesn't re-trigger a reset (it'll match
   `last_sp_location` and take the "same location" branch instead of the
   "new location" branch).

2. **Different XML representation**: don't emit a bare `<lb>` as a
   structural `<sp>` child at all in `tei_builder.py`; encode "this cue
   consumed one physical line" some other way that doesn't interfere with
   the HTML converter's existing per-child dispatch (e.g. an attribute
   directly on `<sp>`, or bake the +1 directly into the `<lg>`'s own `n=`
   so it reads `"7,22"` instead of `"7,21"` — though that would change
   what the `<h3>` location heading displays, which may or may not be
   desired; needs discussion).

User was about to weigh in on which direction to take when we paused.

## Separate, confirmed pre-existing bug (unrelated, do not fix as part of this)

`PENDING_HEAD_RE` in `tei_builder.py`:
```python
CHAR_FOR_PENDING_HEAD = "_"
PENDING_HEAD_RE = re.compile(f"^(.*[\|—,])\s*{re.escape(CHAR_FOR_PENDING_HEAD)}$")
```
Requires the character immediately before trailing `_` (after optional
whitespace) to be one of `|`, `—`, `,`. But real source lines use the
Devanagari danda `।` (e.g. `kimatrāsmahe ।_`), which is NOT in that
character class, so `PENDING_HEAD_RE` never matches this case, and the
literal `_` sentinel leaks straight into the rendered output as visible
text. Confirmed both in the tracked baseline XML and after fix #1/#2 —
byte-identical in both, i.e. NOT something touched by this session's
changes. Flagged to user; out of scope unless they ask for it separately.

## State of the repo right now (as of pausing)

- `utils/transforms/xml/tei_builder.py`: modified — SPEAKER_RE fix (fix
  #1) + the new bare-cue `_emit_lb` call (Step 1 above). The `_emit_lb`
  addition looks correct in isolation (verified via scratch regen) but
  its downstream HTML consumer (Step 2) is broken, so **do not regard
  this as done** until Step 2 is resolved and re-verified end-to-end.
- `utils/transforms/html/convert_xml_to_html.py`: modified — fix #2
  (`speaker_shown` for `lg` branch, solid) + a **broken, in-progress**
  attempt at handling the new bare `<lb>` sp_child + pb-label-before-
  speaker-span logic. This needs rework per the two directions above
  before it's usable. The old empty-`<p>` CSS-spacing hack (attempt A)
  has been fully reverted and is NOT present.
- Tracked XML/HTML files under `texts/`: still reflect only fix #1 + fix
  #2 (from earlier regeneration), NOT the in-progress line-count fix —
  the line-count bug (verse mislabeled after a bare cue) is still present
  in these tracked files. Do not regenerate/commit until Step 2 is
  actually fixed and verified.
- Scratch test files (not tracked, safe to ignore/delete) live under the
  session's scratchpad dir, e.g. `unmattaraghava_xmltest.xml`,
  `unmattaraghava_rich_v2.html`, `find_case.py`, `check_diff.py`.

## Next steps when resuming

1. Decide between the two directions above (peek-ahead vs. different XML
   representation) for making the bare-cue line-count fix compatible with
   `convert_xml_to_html.py`'s location-marker/h3 logic.
2. Re-verify the page-break-before-bare-cue case specifically:
   `bhAskarabhaTTa_unmattarAghava.txt` line 697 (`lakṣmaṇaḥ —` after
   `<14>`/`[14,1]`) and `bhagavadajjuka.txt` line 1089 (`rāmilakaḥ —`
   after `<48>`/`[48,1]`) — confirm the pb-label renders on its own line
   before the speaker span, and the line count after it is correct.
3. Re-verify the plain bare-cue case (no page break) — confirm NO label
   renders at all (neither lb-label before nor after the speaker span),
   and that subsequent line numbers are correct (not shifted).
4. Full regen + diff against current tracked baseline for all 3 affected
   texts (`bhAskarabhaTTa_unmattarAghava`, `bhagavadajjuka`,
   `kRSNamizra_prabodhacandrodaya`), checking every changed line makes
   sense structurally (no orphaned divs, no duplicate h3s) AND numerically
   (line numbers match the printed edition, not shifted).
5. The vertical-CSS-spacing-gap problem (bare cue directly followed by
   `<ul class="verses">` with no block element between, so whatever gap
   rule exists in the *separate* site CSS repo may not fire) is still
   unsolved and was explicitly not to be worked around with a fake empty
   `<p>`. Needs its own decision — possibly out of scope for this repo
   entirely.
