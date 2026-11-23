# HANSEL Text Data Model

HANSEL maintains two co-equal representations of its digital editions: TEI-XML and lightly marked-up plain-text, convertible in both directions without loss of content (`utils/transforms/xml/tei_builder.py` and `utils/transforms/xml/convert_xml_to_plaintext.py`). This document is the contract between the two: every construct below is listed with its form on both sides, and "Round trip" says exactly which details of layout a conversion normalizes. Via TEI, texts are validated against the HANSEL schema (`schemas/hansel.rng` + `schemas/hansel.isosch`, derived from SARIT's `sarit.odd`) by the workflows in `utils/validation/xml/`.

Within that schema, the project focuses on a subset of possible text representations:

- printed editions rather than manuscripts or born-digital editions
- single-work texts instead of multi-work books typeset in parallel
- continuous running text, omitting critical apparatus or dense philological notes
- diplomatic transcription supplemented only by explicit editorial markup (`≤...≥`, `«...»`, etc.)

The goal is to keep texts legible and easy to cross-reference while still being machine-actionable with stable identifiers. Close alignment with the printed page also keeps the corpus comparable to fresh OCR output, so line-by-line representation is prioritized whenever possible.

## TEI-XML and Plain-text Elements

| TEI-XML                                      | Plain-text                                                                                                                               | Notes                                                                                                                                                                                                                                                   |
|----------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `<div n="section title">`                    | Curly-bracket `{section title}` on its own line                                                                                          | Begins a logical division, which is never nested.                                                                                                                                                                                                       |
| `<p n="location">`                           | Square-bracket `[location]` on its own line                                                                                              | Begins a prose paragraph.                                                                                                                                                                                                                               |
| `<lg n="location"><l>...</l></lg>`           | Square-bracket `[location]` on its own line, or `[location]` + tab + verse material on the same line (condensed verse format; see below) | Begins a verse group. `<l>` is for a verse half. Location info is recorded at the verse-group level via `<lg n="...">`. When multiple verses share a single location marker, they are wrapped in `<lg type="group">` containing child `<lg>` elements.  |
| `<caesura/>`                                 | A verse line that does not end in a daṇḍa (`\|` or `\|\|`); the verse half continues on the next tab-indented line                     | Marks the *yati* break between *pādas* inside one `<l>`. Each verse line starts with a tab.                                                                                                                                                              |
| `<head>`                                     | Brief prose + tab + first verse half, on the same line                                                                                   | For brief prose introducing a verse on the verse's own first line, e.g., `uktaṃ ca \|<TAB>verse…`. Introductory prose on its own line is ordinary prose: a `<p>` before the `<lg>`, sharing its location.                                                 |
| `<trailer place="inline">`                  | Verse line followed by material after `\|\|`, or a line starting with `_` right after the verse                                          | E.g., "\|\| iti \|" on the verse's last line becomes a `<trailer>` at the end of the `<lg>`; `_iti \|` on the next line is instead appended as text inside the verse's last `<l>`, after its final `<lb>` (so `_` lines need a line-by-line text). Both display inline at the end of the verse. |
| `<pb n="123">` plus `<lb>` sequence          | `<123>` or `<123,45>`, either on its own line or inline.                                                                                 | Records numerical page (and optionally line) break info.<br/><br/>Attribute `break="no"` corresponds to hyphenated line ending.                                                                                                                         |
| `<label>additional structural info</label>`  | `<additional structural info>`                                                                                                           | Edition-specific, e.g., super-sections, colophons. Placed directly in the `<div>` (closing any open speech, paragraph or verse) and counted as a physical line. Takes `n` when it has its own `[location]` line. |
| `<choice>/<sic>/<corr>` and related          | Editorial brackets<br/>`≤...≥`<br/>`«...»`<br/>`¿...¿`                                                                                   | See "Editorial markup and interpretation" below.                                                                                                                                                                                                        |

Drama texts (`--drama`) add these:

| TEI-XML | Plain-text | Notes |
|---|---|---|
| `<sp who="name"><speaker>name</speaker>…</sp>` | `name — text` at the start of a block (after a blank line) | A speech. Its first paragraph or verse continues on the cue's line; it runs until the next cue, `{section}` or `<label>`. A `[location]` line just before the cue goes to the speech's first paragraph or verse. |
| leading `<lb/>` in the first `<l>` | bare cue `name —` with the verse starting on the next line | Not recorded in `--no-line-by-line` texts, where the verse is written back on the line after the cue. |
| `<l rend="indent(N)">` | verse fragment with N leading tabs (also directly after a cue: `name —\t\tfragment`) | Staggered dialogue verse: a verse half shared between speakers, each fragment printed further right. |
| `<stage>` | `((text))`, possibly over several lines | Stage direction, inline wherever it occurs. |
| `<seg type="prakrit" xml:lang="pra-Latn">` with a nested `<seg type="chāyā" xml:lang="san-Latn">` | `˹text˼` in prose | The chāyā comes from the companion file (below). |
| `<lg>` with a child `<lg type="chāyā" xml:lang="san-Latn">` | `˹` before the first verse half and `˼` after the verse's last daṇḍa | A Prakrit verse; its chāyā gets one `<l>` per line of its companion-file entry. |

**Chāyā companion file** (`txt/chaya/<stem>.txt`, with `--chaya`): one entry per `˹…˼` span, in the order the spans occur, entries separated by a blank line. A verse entry has one line per verse half, each indented with a tab.

**Per-text flags** live in `utils/transforms/flag_map.py`:

- Line by line is the default: the text follows the printed lines, and every physical line ends in `<lb n="…"/>` (`break="no"` after a hyphen), so prose line breaks survive the round trip. `--no-line-by-line` marks a text whose lines do not follow printed lines (e.g. one line per speech); there only paragraphs, verse lines and page breaks are recorded.
- `--drama`: speeches, stage directions, Prakrit (above). `--chaya`: read the companion file.
- `--hide-milestones`: display only (HTML).

## Location markers and condensed verse format

Location markers drive the data model. For prose material, including occasional embedded verse, location is recorded as physical page and line number. This follows academic practice and facilitates efficient cross-reference.

By contrast, for texts consisting primarily of numbered verse, location is instead the logical half-verse, e.g., "1.1ab". This is represented more concisely in plain-text as e.g. `[1.1ab]<TAB>text`, and these location markers receive less emphasis in rich HTML.

Each element opened by a location marker gets `@n` (the label) and an `@xml:id` made from it: `[12,3]` → `p12_l3`, any other label → `v` plus the label with non-word characters as `_` (`[1.1ab]` → `v1_1ab`). Further paragraphs or verses under the same marker (e.g. prose, then a verse, then prose again) share its `@n` and get `_2`, `_3`, … appended to the id. A bare id therefore marks the element the `[location]` line actually opened, which is how the writer knows where to put markers back.

In the condensed format, a half-verse line without a closing daṇḍa runs on into the next labelled line inside the same `<l>`, and that `<l>` records both letters: `[1.1a]` + `[1.1b]` → `<l n="ab">`.

Some mixed verse-and-prose texts may alternate constantly between a base layer with numbered verses or aphorisms and a prose commentarial layer. In such cases, section markers (`{section title}`) can be used liberally to mark each base/commentary pairing by the base's logical numbering, while location markers (`[location]`) mark page and line for each component.

## Editorial markup and interpretation

A small set of bracket conventions keeps editorial decisions explicit:

- `<choice><sic>sic</sic><corr>corr</corr></choice>` = `≤sic≥«corr»` 
- `<del>text</del>` = `≤text≥` 
- `<supplied>text</supplied>` = `«text»` 
- `<unclear>text</unclear>` = `¿text¿`

Symbols found in printed editions should be interpreted into one of these patterns. This departs slightly from HANSEL's otherwise strictly diplomatic standard for the sake of clearly signalling interpretive stances.

## Validation workflow

- TEI view: run `make` (or `make compare`) in `utils/validation/xml/` to execute RELAX NG and Schematron checks across `texts/project_editions/xml`.
- Plain-text view: validate structure with `utils/validation/txt/validate.py -s` and optionally profile content with `-c` (n-gram analysis).
- Round trip: `make roundtrip` (see below).

## Round trip

`utils/transforms/xml/roundtrip.py` (`make roundtrip`) builds txt → XML → txt′ → XML′ for every edition, in memory, and promises:

- **XML′ is identical to XML.** Whatever the writer produces rebuilds into exactly the same edition. This is checked strictly; a text that fails is a bug in the builder or the writer.
- **txt′ equals the original txt up to layout**, i.e. up to what the XML does not record: blank lines (except that a speaker cue starts a block), trailing whitespace, chāyā indentation, and, in `--no-line-by-line` texts, where prose lines break. The writer uses one canonical layout for these (a blank line after each `[location]` line and around sections, labels and speeches; a page marker that ends a paragraph stands apart).

`make roundtrip` prints one row per text with these columns:

| Column | Meaning |
|---|---|
| lines | Lines in the original txt. |
| strict | Lines of txt′ that differ from the original txt, compared exactly, blank lines and trailing spaces included. Nonzero here is expected and means only layout differs. |
| layout | The same count after ignoring the layout listed above. Should be 0. |
| chāyā | The layout-insensitive count for the chāyā companion file, ignoring indentation too. Should be 0. |
| XML′=XML | Whether XML′ is identical to XML. Must be yes; the command exits 1 otherwise. |

With `--strict`, the command also exits 1 unless layout and chāyā are 0.

`python utils/transforms/xml/roundtrip.py --diff STEM` shows the remaining differences for one text. To write the reverse conversion to files, `utils/transforms/xml/regenerate.py --txt` writes into `utils/transforms/xml/tmp/txt` (git-ignored); it never writes over the project-edition txt files.

## Character set and punctuation

HANSEL texts use IAST with pre-composed characters (for example, the single-codepoint `ṝ` rather than the three-codepoint stacking combination). HANSEL prefers `ṃ ṛ ḷ e o` over ISO 15919 `ṁ r̥ l̥ ē ō`, and the extended set `ḻ ẖ ḫ ṁl` represents `ळ ᳵ ᳶ लँ`. For Prakrit, diaeresis `¨` is used for post-hiatus vowels that would otherwise be ambiguous with Sanskrit (e.g., `jaïo`) and breve `˘` is used to explicit short vowels `ĕ ŏ`.

The website provides transliteration options via the Sanscript JavaScript package.

Punctuation conventions:

- vertical bar `|` for the daṇḍa (`। ॥`)
- apostrophe `'` reserved for avagraha `ऽ`
- em dash `—` for syntactic breaks, en dash `–` for ranges, hyphen `-` for line-break continuations
- underscore `_` at line start for text that follows a verse on its own line (see `<trailer>` above)

On macOS you can enter the editorial brackets with Option + , (`≤`), Option + . (`≥`), Option + \ (`«`), Option + Shift + \ (`»`), and Option + Shift + ? (`¿`).
