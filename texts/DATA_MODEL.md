# Data Model Origin and Purpose

HANSEL's Sanskrit e-text data model, based on plaintext, originates in the Pramāṇa NLP project.

It focuses primarily on representing the following:
- printed editions — NOT manuscripts or born-digital editions
- single-work texts — NOT books with multiple works typeset in parallel
- natural language — NOT philological detail like notes, apparatus, etc.
- diplomatic transcription that e.g. OCR would see — NOT born-digital improvements
 
These latter things aren't necessarily precluded by the data model,
but insofar as it supports them, they are secondary.

The goal is to have e-texts that are both useful for humans
(readable and easy to cross-reference against source material)
and consistently structured for machines
(automatically parsable, with unique identifiers).
They should also be easy to compare against fresh OCR output,
in order to enable continuous improvement.
For this latter reason, these e-texts tend toward line-by-line representation.


# Embodiment through Validation and Conversion Processes

In addition to this document, which describes the data model in words,
and a small number of initial documents to exemplify it (see below),
the data model is best expressed though 1) the data repository's included
plaintext-XML roundtrip conversion process and 2) automatic validation,
as explained below.

1. Texts most validly express the data model
insofar as they successfully survive automatic transformations from plaintext to XML —
this XML can then be used to render HTML for web presentation, etc. —
and back again from the produced XML to plaintext with minimal deviation.

2. A structural validation script can also detect basic model violations.
Also, insofar as structure can be automatically isolated from content for this purpose,
validation can then also check the (IAST) Sanskrit content of the files.
It does this by comparing file content both against a set of allowed characters
and against empirically-calibrated frequency expectations for all possible character combinations (n-grams).

To see these transforms and validations in action,
anyone can clone the repo and execute the Python scripts
in `utils/transforms/xml` and in `utils/validation`, respectively.


# Examples

The first files included in the repository serve as examples:
- Bāṇa's _Kādmabarī_
- Kumārila's _Ślokavārtika_
- _Śukasaptati Simplicior_
- _Śukasaptati Ornatior_


# Markup Scheme

## Structural Markup

HANSEL data is typified by plaintext structural markers preceding textual content.
The primary markers and what they correspond to in TEI-XML are:
- Section markers `{...}` (on own line only) → `<div>` (flat, never nested)
- Location markers `[...]` (either on own line or in-line with tab-separation) → either `<p>` or `<lg>` (latter can nest x1 for groups).
- Tab `\t` indent → `<lg>`/`<l>`
- Page markers `<page[col][,line]>` → `<pb>`, (possibly also `<cb>`, `<lb>`) (with `n` attribute)

The location marker `[...]` is the heart of the structural markup,
constituting a unique identifier for each part of the text.
Typical scopes are a prose paragraph
(in which case the label inside the `[...]` marker is `page,starting_line_number`)
or a verse or group of verses
(in which case the label is either `page,starting_line_number` or the verse number).

Further structural notes use `<...>` → `<milestone>` (with `n` attribute).

For handling short bits of prose or annotations closely associated with verse material (e.g., closing iti):
  - Material preceding/following on same lines as verse material represented by `<head>/<back>`, respectively
  - Head-material on a preceding line can be manually associated with verse material below by using trailing underscore `_`, e.g., "uktaṃ ca |_".

Line-end markup is interpreted strictly:
- Newline `\n` → `<lb>` (with `n` attribute)
- Hyphen `-` → `break="no"` attribute for `<pb>` and `<lb>` (and `<cb>`)

A `--line-by-line` option in the XML conversion gives control 
over handling of this line-end information.
So too is there a script, `utils/transforms/process_hyphens.py`, 
which will automatically drop them from plaintext.


## Editorial Markup

The data model also includes editorial bracket sets that describe the evolving e-text itself, NOT the printed edition source:
- `≤...≥` is _ante-correctionem_ (to be deleted)
- `«...»` is _post-correctionem_ (to be kept)
- `¿...¿` is a doubtful reading (also to be kept but suspected of being mistaken)
- Notes `(...)` → `<note>` (any other sort of note not directly helping to establish the author's natural-language flow)

Editorial markup as found in the printed edition itself 
should be *interpreted* and *re-represented* in one of the above ways. 
E.g., if the editor used "[...]" for an unwanted interpolation 
or "(...)" to suggest a correction for some number of _akṣaras_, 
these would need to be interpreted with `≤...≥` 
and a combination of `≤...≥«...»` (around the correct number of _akṣaras_), respectively.
This constitutes an exception to the diplomatic transcription policy. 

In this way, to a limited extent, these editorial markup elements allows for ongoing improvement of the material
alongside the goal of retaining fidelity to a less-refined version of the text as presented in the source.

NB: The special characters above can be easily typed on Mac using the option `⌥` key +
comma `,`, period `.`, backslash `\`, vertical bar `|`, and question mark `?`, respectively.


## Verse vs. Prose, Logical vs. Physical Orientation

The data model has two structural flavors, depending on the dominance of numbered verse:
1. Strictly numbered verse - primarily oriented toward verse numbering
2. Anything else (prose/verse) - primarily oriented toward physical features of edition

A strictly-numbered, verse-only text basically has two tab-separated columns:
logical verse identifiers on the left, text on the right.
Edition page numbers are recorded for reference purposes,
but they are not used for location markers.

For texts without this kind of numbered-verse structure
(e.g., verse base text + commentary, _śāstric_ treatise, _gadyakāvya_, or even unnumbered verse)
structure must instead orient to the physical features of the edition:
page and line numbers for the beginning of each paragraph.
This reflects academic practice.

NB: Section markers `{...}` can be used liberally to e.g.,
divide a prose commentary according to the numbered verses of the base text
on which it relies.

Especially in conjunction with the latter type,
line-by-line diplomatic representation, complete with line-final hyphenation,
enables later automatic derivation of line number information for the purpose of creating location markers,
freeing the transcriber from the burden of manually counting lines during digitization.


# Character Set

The transliteration scheme used is IAST, with the following preferences:
- pre-composed characters (e.g., single-character `ṝ` rather than triple-character `ṝ`)
- standard IAST `ṃ ṛ ḷ e o` (rather than ISO 15919 `ṁ r̥ l̥ ē ō`)
- special chars `ḻ ẖ ḫ ṁl` for `ळ ᳵ ᳶ लँ`
- lowercase except for e.g. emphasis of proper names or indication of grammatical _anubandhas_
- Prakrit: diaresis `¨`for otherwise ambiguous intra-word vowel hiatus (e.g., jaïo), breve `˘` for short vowels (ĕ ŏ)

Punctuation preferences:
- simple ASCII vertical bar `|` for _daṇḍa_ (`। ॥`)
- simple apostrophe `'` reserved for _avagraha_ `ऽ` rather than quotation
- em-dash `—` for syntax breaks, en-dash `–` for ranges, hyphen `-` reserved for line-final word-breaks
- underscore `_` for pending `<head>` material (see above)