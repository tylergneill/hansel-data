# Unspaced text mode (feature spec)

Status: not started. A March 2026 prototype existed on `add-unspaced-transliteration` in both hansel-data and hansel-app. Those branches were deleted on 2026-10-30. This spec keeps the goal and what was learned, without tying a new attempt to that implementation.

## Goal

Let a reader view any text with inter-word spaces removed, as it would appear in continuous (saṃhitā-style) writing, e.g. `tato 'pi gacchati` → `tato'pigacchati`, with sandhi left as it already appears in the edition. The motivation is reading practice and closer correspondence to manuscript/printed-edition layout.

## Requirements

- A reader-level preference (persisted per browser) that toggles unspaced mode for all texts.
- It must compose with the existing transliteration scheme switcher: unspacing happens on IAST, then the chosen scheme is applied.
- Only Sanskrit/Prakrit content gets unspaced. Editorial apparatus stays as-is: page/line labels (`pb-label`, `lb-label`), editorial coordinates, hyphen markers, speaker names?, stage directions?, TOC, metadata panel.
- Search-friendly (plain) mode and in-page search should still work. Decide whether search matches spaced or unspaced forms.
- Downloads are unaffected unless we decide to offer unspaced files as a separate download format.

## Prior prototype (for reference only)

- **Data side**: `utils/transforms/html/unspace_html.py` post-processed every generated plain/rich HTML file. It walked text nodes, skipped the classes above, and ran Skrutable's `Transliterator('IAST','IAST').transliterate(text, avoid_virama_non_indic_scripts=True)`. Output went to `texts/transforms/html/unspaced/{plain,rich}/`, called from `html/regenerate.py`. That added about 60k lines of generated HTML to the repo.
- **App side**: added a `/settings` page and moved the "show all schemes" checkbox there. Both preferences were stored in localStorage and re-applied on `pageshow` (bfcache). The viewer fetched the pre-generated unspaced HTML and used it as the base for transliteration.

## Open questions / alternatives

1. **Pre-generated vs. on-the-fly.** Pre-generating doubles the HTML footprint and has to be regenerated alongside everything else. Unspacing in the browser (or server-side at request time) keeps the data repo lean but needs a JS implementation or a Skrutable endpoint. The rest of the app's transliteration already runs client-side.
2. **Rule source.** Does Skrutable's `avoid_virama_non_indic_scripts` give the desired output for all cases (avagraha, vowel hiatus, Prakrit, verse-final daṇḍas, `-` compounds)? Write test cases first.
3. **Drama texts.** Should speaker labels, stage directions and chāyā be unspaced? The prototype predates the drama-specific HTML classes, so its skip list is incomplete.
4. **Settings page.** It's a reasonable home for reader preferences regardless. It could ship on its own, ahead of this feature.

## Done when

- The toggle works on prose, verse and drama texts, in every transliteration scheme.
- Labels, coordinates and the apparatus are untouched.
- Tests in hansel-app cover the toggle and the localStorage restore.
