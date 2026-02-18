# HANSEL Text Data Model

HANSEL maintains two co-equal, losslessly convertible representations of its digital editions: TEI-XML and lightly marked-up plain-text. Via TEI, texts are validated against the SARIT "Simple" schema (`schemas/sarit.rng` + `schemas/sarit.isosch`) by the workflows in `utils/validation/xml/`.

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
| `<caesura/>`                                 | Tabs within verse halves.                                                                                                                | Marks *yati* breaks between *pādas*.                                                                                                                                                                                                                    |
| `<head>`                                     | Trailing `_` at line end                                                                                                                 | For brief prose preceding verse, e.g., `uktaṃ ca`.                                                                                                                                                                                                      |                                                                                                                                        |
| `<back>`                                     | Verse line followed by material after `\|\|`                                                                                             | E.g., "\|\| iti \|"                                                                                                                                                                                                                                     |
| `<pb n="123">` plus `<lb>` sequence          | `<123>` or `<123,45>`, either on its own line or inline.                                                                                 | Records numerical page (and optionally line) break info.<br/><br/>Attribute `break="no"` corresponds to hyphenated line ending.                                                                                                                         |
| `<milestone n="additional structural info">` | `<additional structural info>`                                                                                                           | Edition-specific, e.g., super-sections.                                                                                                                                                                                                                 |
| `<note>`                                     | Parentheses `(text)`                                                                                                                     | Ancillary in-line remarks that do not belong to the text.                                                                                                                                                                                               |
| `<choice>/<sic>/<corr>` and related          | Editorial brackets<br/>`≤...≥`<br/>`«...»`<br/>`¿...¿`                                                                                   | See "Editorial markup and interpretation" below.                                                                                                                                                                                                        |

## Location markers and condensed verse format

Location markers drive the data model. For prose material, including occasional embedded verse, location is recorded as physical page and line number. This follows academic practice and facilitates efficient cross-reference.

By contrast, for texts consisting primarily of numbered verse, location is instead the logical half-verse, e.g., "1.1ab". This is represented more concisely in plain-text as e.g. `[1.1ab]<TAB>text`, and these location markers receive less emphasis in rich HTML.

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
- Format parity: `utils/transforms/xml/regenerate.py` supports both `--xml` and `--txt` modes to confirm round-trip fidelity between the two representations.

## Character set and punctuation

HANSEL texts use IAST with pre-composed characters (for example, the single-codepoint `ṝ` rather than the three-codepoint stacking combination). HANSEL prefers `ṃ ṛ ḷ e o` over ISO 15919 `ṁ r̥ l̥ ē ō`, and the extended set `ḻ ẖ ḫ ṁl` represents `ळ ᳵ ᳶ लँ`. For Prakrit, diaeresis `¨` is used for post-hiatus vowels that would otherwise be ambiguous with Sanskrit (e.g., `jaïo`) and breve `˘` is used to explicit short vowels `ĕ ŏ`.

The website provides transliteration options via the Sanscript JavaScript package.

Punctuation conventions:

- vertical bar `|` for the daṇḍa (`। ॥`)
- apostrophe `'` reserved for avagraha `ऽ`
- em dash `—` for syntactic breaks, en dash `–` for ranges, hyphen `-` for line-break continuations
- underscore `_` for pending `<head>` material as described above

On macOS you can enter the editorial brackets with Option + , (`≤`), Option + . (`≥`), Option + \ (`«`), Option + Shift + \ (`»`), and Option + Shift + ? (`¿`).
