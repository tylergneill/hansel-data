# CLAUDE_TODO.md

Pipeline cleanup items identified 2026-02-16 after the condensed-verse-format flag elimination.

## Deferred cleanups (low priority, need investigation)

### `current_caesura` state in `tei_builder.py`
Not dead — controls whether `last_tail_text_sink` is reset in `_process_content_with_midline_elements()` (lines ~454–462). But the interaction is subtle and worth documenting or simplifying if the verse-close logic is ever reworked.

### `in_lg` parameter naming in `convert_xml_to_html.py`
The `in_lg` parameter to `process_children()` is really "suppress line-break labels inside verse groups" — its name doesn't convey that. Renaming to something like `suppress_break_labels` would help, but it's used ~19 times, so save it for a dedicated pass. Low priority since it doesn't affect output.

### `process_hyphens.py` — possibly orphaned
`utils/transforms/process_hyphens.py` defines `process_hyphens_and_newlines()` with a CLI wrapper but is never imported by the pipeline. Might be intentionally kept for manual/standalone use. Ask Tyler before removing.

### `--extra-space-after-location` in `convert_plaintext_to_xml.py`
Defined as a CLI arg (line 22) but never used in txt-to-xml conversion — only meaningful in xml-to-txt. Must stay because `xml/regenerate.py` passes the same flag_map string to both directions and argparse would error if it were removed. Could be fixed by splitting flag_map into per-direction maps, but that's more churn than benefit right now.

### `<sp>` duplicates the section loop's element rules — `convert_xml_to_html.py`
Two loops decide how content renders: the section loop over `<div>` children (~line 1010)
and the `<sp>` loop over speech children (~line 1029). Both independently handle `<p>`,
`<lg>`, `<stage>` and coordinate markers, so any rule added to one must be added to the
other by hand. Nothing enforces that, and the two have already drifted.

Found via `<milestone>`, which ended up with four separate renderings depending only on
where in the tree it landed: `<h2>` as a `<div>` child, `<h2>` from a milestone-only `<p>`,
`<li class="milestone-verse">` inside an `<lg>`, and *nothing at all* inside an `<sp>`
(virUpAkSadeva `<prastāvanā>` at txt line 123 — encoded correctly, present in the XML,
silently dropped in HTML). Placement in the source decides visibility, which is not a
distinction the markup is meant to carry.

Fix: render each element type in one place — the shared `process_children()` walker that
every path already funnels through — and let the loops handle only genuine container
concerns (speaker attribution, speech divs, coordinate h2 placement). Removes the
duplicate-by-hand requirement rather than adding a fifth special case next time.

Scope: touches the main rendering loops, so needs the full-corpus diff (all 10 texts,
XML structure + rich HTML) to confirm no output changes. Deferred as too broad to fold
into the milestone work; the narrow fix there handles `<milestone>` in the shared walker.

Related: `((iti niṣkrāntau))` closing a scene is absorbed into the preceding speaker's
`<sp>` rather than closing it, which is what gave the following `<prastāvanā>` the wrong
parent. Arguably an encoding question rather than a converter one — worth deciding
separately whether a scene-closing stage direction should end the speech.

### `_is_condensed_lg()` duplication
Identical 5-line helper in both `xml/convert_xml_to_plaintext.py` and `html/convert_xml_to_html.py`. Extracting to a shared module would require `sys.path` manipulation in both consumers (they run as standalone scripts from different directories). Not worth the import complexity for 5 lines.

## Existing TODOs found in code

### Unimplemented structural note handler — `tei_builder.py:155`
`# 2c) TODO: Other structural note (...) not to be counted as physical line`
Placeholder for a future handler. No current texts need it.

### Header/text generation order dependency — `xml/regenerate.py:39`
`# TODO: resolve why order of these two matters (namespaces?)`
teiHeader must be generated before text content. Likely a namespace initialization issue. Fragile but works.

### State reset necessity — `convert_xml_to_html.py:469`
`# TODO: investigate whether necessary to reset like this`
`self.current_page, self.current_line = '', '1'` before the main content loop. Probably unnecessary since `<pb>` and `<p>` elements always set these before first use, but needs verification across all texts.
