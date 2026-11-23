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

## Plain-text grammar (draft)

> **Draft for discussion, not yet used by any code.** This section states the plain-text format precisely enough that a parser could be written from it alone. It describes the format as `tei_builder.py` reads it today. Where today's behaviour looks accidental rather than intended, the grammar does not adopt it; the point is listed under "Open questions" at the end instead.

Reading a plain-text file happens in three layers:

1. **Lines.** Every physical line is exactly one kind, decided by its own form (and, for speaker cues, by whether it starts a block).
2. **Structure.** The sequence of line kinds builds the divisions, paragraphs, verses and speeches.
3. **Inline marks.** Inside a line's text, a few bracket pairs mark page breaks, editorial readings, stage directions and Prakrit.

Three per-text settings change what is read: **drama** (speaker cues, `((…))`, `˹…˼`), **chāyā** (a companion file supplies the chāyās) and **line by line** (whether line breaks are recorded). Rules that apply only to drama texts are marked *(drama)*.

### Lines

A **block** starts at the beginning of the file and after every blank line. Being at the start of a block matters only for speaker cues.

A line's kind is the first row of this table that it fits:

| Kind | Form | Example |
|---|---|---|
| blank | nothing, or only spaces and tabs | |
| section | `{title}` | `{pūrvabhāga}` |
| page | `<N>`, N digits only | `<54>` |
| label | `<text>`, any other text in angle brackets | `<kādambarī \|>` |
| location | `[label]` alone | `[275,10]` |
| condensed verse | `[label]`, one or more tabs, verse text | `[1.1ab]⇥viśuddhajñānadehāya …` |
| speaker cue *(drama, block start only)* | `name —` followed by a space and text, by nothing, or by tabs and a verse fragment | `sūtradhāraḥ —` |
| after-verse | `_` then text | `_iti \|` |
| verse | a line containing a tab: optional head text, tab(s), verse text | `⇥kalā cāndrī …`, `uktaṃ ca \|⇥…` |
| prose | anything else | |

(`⇥` stands for a tab. A cue's `name` is one word: no spaces.)

Because cues count only at the start of a block, a line inside a paragraph that happens to begin `word — …` is prose (e.g. `bravīṣi — ‘āryaputrasya …` in Bhāskarabhaṭṭa's Unmattarāghava).

**Spans over several lines.** Four constructs may continue onto following lines. The lines are joined first, the joined line is then classified, and each place where a line was joined becomes a line break inside the construct:

- a label: from `<` to the line containing `>`;
- a stage direction: from `((` to the line containing `))` (text after `))` on that line stays on it);
- editorial markup: from `≤` to the line containing `≥` (with its `«…»`, if any);
- *(drama)* Prakrit: from `˹` to the line containing `˼`. If every joined line is a verse line, the span is a Prakrit verse; otherwise it is prose.

Formally (a draft in EBNF; `TAB` is a tab, `text` is any characters):

```
line            = blank | section | page | label | location | condensed
                | cue | after_verse | verse | prose ;
section         = "{" text "}" ;
page            = "<" digits ">" ;
label           = "<" text ">" ;                 (* text not all digits *)
location        = "[" loc "]" ;
condensed       = "[" loc "]" TAB { TAB } verse_text ;
cue             = name " —" [ " " text | TAB { TAB } verse_text ] ;
after_verse     = "_" text ;
verse           = [ head ] TAB { TAB } verse_text ;
prose           = text ;                         (* none of the above *)

loc             = page_line | verse_number | other_label ;
page_line       = digits "," digits ;
verse_number    = digits { ( "." | "," ) digits } [ letters ] ;   (* letters: 1–4 of a–z *)
verse_text      = text [ verse_end [ trailer ] ] ;
half_end        = ( "|" | "||" | "।" | "॥" ) [ " " ] ;   (* at the end of a line *)
verse_end       = "||" " " number_text " " "||" | "||" ;   (* also with ॥ *)
```

### Structure

1. **Section.** `{title}` closes everything that is open and starts `<div n="title">`. Content before the first section goes into one unnamed division.
2. **Location.** `[label]` closes the open paragraph and verse and opens a paragraph `<p n="label">`. If nothing is added to that paragraph, it is dropped. Inside a speech, the paragraph belongs to the speech.
3. **Prose.** Prose lines join the open paragraph, also across blank lines, until the next location, verse, label, section or cue. Prose right after a verse under the same location opens a new paragraph with the same `n`. Outside drama, prose with no location before it is an error.
4. **Verse.** Verse lines build an `<lg>`:
   - A line that ends in a daṇḍa (`|`, `||`, `।`, `॥`) ends a verse half `<l>`. A line that doesn't ends at a caesura, and the next verse line continues the same `<l>`.
   - The verse ends at a verse-end mark: `|| number ||` (the number being 1–20 characters without a daṇḍa), or a `||` not followed by such a number. Text after the last verse-end mark on the line is an inline `<trailer>`.
   - At the end of a line, a daṇḍa inside editorial markup counts by its reading: `≤|≥«||»` ends the verse.
   - Text before the tab is a `<head>` and starts a new verse.
   - Extra tabs at the start of a verse line record staggered dialogue verse: `rend="indent(N)"`, N being the number of tabs.
   - Several verses under one location are wrapped in `<lg type="group">`. The location's `n` goes on the verse or on the group.
5. **After-verse.** `_text` is appended to the last verse half of the verse just before it.
6. **Condensed verse.** In `[label]⇥text` the label is a verse number with optional pāda letters. Consecutive lines with the same number form one `<lg n="number">`, and each line is an `<l n="letters">`. A half without a closing daṇḍa runs on into the next line's `<l>`, which then records both letters (`n="ab"`).
7. **Label.** `<text>` closes the open speech, paragraph and verse and becomes a `<label>` directly in the division. If a location line came just before it, with nothing in between, the location moves onto the label.
8. **Page.** `<N>` on its own line is a page break between the line before and the line after.
9. **Speech** *(drama)*. A cue at the start of a block closes the previous speech and opens `<sp who="name">`:
   - text after the cue starts the speech's first paragraph;
   - a bare cue means the speech's content starts on the next line;
   - tabs after the cue mean the content is a staggered verse fragment.

   A location line just before the cue applies to the speech's first paragraph or verse. A speech runs, across blank lines, locations and page breaks, until the next cue, label or section. Prose outside any speech and location is a paragraph of its own.

### Inline marks

| Mark | Meaning |
|---|---|
| `<N>` | page break inside the line |
| `≤a≥«b»` | correction: printed `a`, read `b` (`<choice>`) |
| `≤a≥` | deletion (`<del>`) |
| `«a»` | supplied text (`<supplied>`) |
| `¿a¿` | unclear text (`<unclear>`) |
| `((a))` *(drama)* | stage direction (`<stage>`) |
| `˹a˼` *(drama)* | Prakrit; takes the next entry of the chāyā file |
| `-` at the end of a line | in line-by-line texts, the word continues on the next line (`break="no"`) |

- Marks never overlap. Reading left to right, the mark that starts first wins; when two start at the same place, the longer wins (`≤a≥«b»` over `≤a≥`).
- Inside `˹…˼`, stage directions, editorial marks and page breaks are read. Inside `((…))` and inside editorial marks, nothing else is read: only line breaks.

```
text      = { plain | page_mark | edit | stage | prakrit } [ "-" ] ;
page_mark = "<" digits [ "," digits ] ">" ;
edit      = "≤" plain "≥" [ "«" plain "»" ] | "«" plain "»" | "¿" plain "¿" ;
stage     = "((" plain "))" ;                                  (* drama *)
prakrit   = "˹" { plain | page_mark | edit | stage } "˼" ;     (* drama *)
```

### Line numbering (line-by-line texts)

- `[page,line]` sets the current line number. `<N>` on its own line makes the next line line 1 of page N.
- Every line with content advances the count by one: prose, verse, condensed verse, cue lines (bare cues too) and each physical line of a label. Blank, section, location and page lines don't count.
- Each line break inside the text becomes `<lb n="…"/>` carrying the next line's number, with `break="no"` after a hyphen. A page break at the end of a line takes the place of that line's `<lb>`.

### Chāyā file

`txt/chaya/<stem>.txt` has one entry per `˹…˼` span, in the order the spans occur, separated by blank lines. A verse entry has one line per verse half, each starting with a tab. Entries may contain editorial marks.

### Open questions

Each of these is a place where today's builder does something the grammar above doesn't state, or states only by accident. Each needs a decision before a parser is written.

1. **Blank lines.** Today they matter only for cues in drama texts; a paragraph runs on across blank lines until the next location. Should a blank line end a paragraph everywhere?
2. **`((…))` outside drama.** Lines are joined at an open `((` in every text, but `((…))` is read as a stage direction only in drama texts. Should stage directions be drama-only (and no joining elsewhere), or allowed everywhere?
3. **Nothing inside `((…))`.** Editorial marks and page breaks inside a stage direction are kept as literal characters. None occur today. Intended?
4. **Page line inside a Prakrit span.** In Bhagavadajjuka at p.20, `<20>` on its own line inside `˹…˼` gives `<lb n="21"/><pb n="20"/><lb n="1"/>`; everywhere else the page break takes the place of the line break. Making it uniform would change that one spot in the XML.
5. **`<N,M>`.** A page-and-line marker is supported but used nowhere, and the line number it sets comes out one lower than written. Drop it, or fix it?
6. **Comma in location labels.** `[12,3]` means page and line, but commas also appear in verse numbers (`[5,1.1ab]` in Ślokavārttika) and in Prabodhacandrodaya's act,unit labels. Proposal: a label is page and line only when it is exactly digits, comma, digits, and texts with other coordinates say so in their settings.
7. **After-verse lines aren't counted.** A `_` line doesn't advance the line count. That works today only because a location line always follows. Count it?
8. **Settings.** Drama could be detected from the text itself (any speaker cue), and chāyā from the presence of the companion file, leaving line by line as the only setting. Keep the flags, or detect?

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
