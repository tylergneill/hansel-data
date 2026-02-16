# HANSEL Text Data Model

HANSEL maintains two co-equal, losslessly convertible representations of its digital editions: TEI-XML and lightly marked-up plain-text. Via the TEI-XML, they are validated against the SARIT "Simple" schema (`schemas/sarit.rng` + `schemas/sarit.isosch`) by the workflows in `utils/validation/xml/`.

Within that schema, the project focuses on a subset of possible text representations:

- printed editions rather than manuscripts or born-digital editions
- single-work texts instead of multi-work books typeset in parallel
- continuous running text, omitting critical apparatus or dense philological notes
- diplomatic transcription supplemented only by explicit editorial markup (`≤...≥`, `«...»`, etc.)

The goal is to keep texts legible and easy to cross-reference while still being machine-actionable with stable identifiers. Close alignment with the printed page also keeps the corpus comparable to fresh OCR output, so line-by-line representation is prioritized whenever possible.

## TEI-XML and Plain-text Elements

| TEI-XML                                      | Plain-text                                                                                                                                     | Notes                                                                                                                                                                                                                                             |
|----------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `<div n="section title">`                    | Curly-bracket `{section title}` on its own line                                                                                                | Begins a logical division, which is never nested.                                                                                                                                                                                                 |
| `<p n="location">`                           | Square-bracket `[location]` on its own line                                                                                                    | Begins a prose paragraph.                                                                                                                                                                                                                         |
| `<lg n="location"><l>...</l></lg>`           | *Standard mode:* square-bracket `[location]` on its own line.<br/><br/>*Condensed verse format:* `[location]` + tab + verse material on the same line | Begins a verse group.<br/><br/>*Standard mode:* location info recorded at verse-group level, for which a parent `<lg>` is used.<br/><br/>*Condensed verse format:* location info recorded at the sub-verse level.<br/><br/><l> is for a verse half.      |
| `<caesura/>`                                 | Tabs within verse halves.                                                                                                                      | Marks *yati* breaks between *pādas*.                                                                                                                                                                                                              |
| `<head>`                                     | Trailing `_` at line end                                                                                                                       | For brief prose preceding verse, e.g., `uktaṃ ca                                                                                                                                                                                                  |_`.                                                                                                                                        |
| `<back>`                                     | Verse line followed by prose after `\|\|`                                                                                                      | E.g., "\|\| iti \|"                                                                                                                                                                           |
| `<pb n="123">` plus `<lb>` sequence          | `<123>` or `<123,45>`, either on its own line or inline.                                                                                       | Records numerical page (and optionally line) break info.<br/><br/>Attribute `break="no"` corresponds to hyphenated line ending set.                                                                                                               |
| `<milestone n="additional structural info">` | `<additional structural info>`                                                                                                                 | Edition-specific, e.g., super-sections.                                                                                                                                                                                                           |
| `<note>`                                     | Parentheses `(text)`                                                                                                                           | Ancillary in-line remarks that do not belong to the text.                                                                                                                                                                                         |
| `<choice>/<sic>/<corr>` and related          | Editorial brackets<br/>`≤...≥`<br/>`«...»`<br/>`¿...¿`                                                                                         | See "Editorial markup and interpretation" below.                                                                                                                                                                                                  |

## Standard vs. condensed verse format

The data model has two plaintext input formats, depending on the dominance of numbered verse:
1. Standard (any mix of prose +/- verse): oriented toward physical features of edition
2. Condensed verse format: a compact plaintext notation for texts consisting primarily of numbered verse

Location markers drive both formats. In standard texts, not only page breaks but also all line breaks are recorded. Using this info, it is `<p>` and (parent) `<lg>` elements that carry unique identifiers of the `page,line` type. This follows academic practice and facilitates efficient cross-reference. In condensed verse format texts, location info recorded at the verse or sub-verse level is the primary mode of reference. Page numbers are also marked but hold secondary status, while line breaks are not marked.

From XML onward, there is no distinction between the two formats — all `<lg>` elements are treated identically regardless of the plaintext input variant.

Some mixed verse-and-prose texts may alternate constantly between a base layer with numbered verses or aphorisms and a prose commentarial layer. In such cases, section markers (`<div n="section title">` and `{section title}`) can be used liberally to mark each base/commentary pairing by the base's logical numbering, while location markers ( `<p n="location">`/`<lg n="location">` and `[location]`) can mark page and line for each of the base and commentary components.

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
