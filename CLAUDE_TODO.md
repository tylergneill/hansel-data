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
