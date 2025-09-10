# Origin and Purpose

HANSEL's Sanskrit e-text data model, based on plaintext, originates in the Pramāṇa NLP project.

It focuses primarily on the following:
- printed editions — NOT manuscripts or born-digital editions
- single-work texts — NOT books with multiple works typeset in parallel
- natural langauge — NOT philological detail like notes, apparatus, etc.
- diplomatic transcription that e.g. OCR would see — NOT born-digital improvements
 
The data model doesn't necessarily shun these latter things,
but insofar as it supports them, they are secondary.

The goal is e-texts that are both useful for humans
(readable and easy to cross-reference with relevant printed edition)
and consistently structured for machines
(automatically parsable, with comprehensive identifiers).


# Marker Categories and Bracket Sets

The primary structural elements and what they correspond to in TEI-XML are:
1) Section markers {...} (own line only) → <div> (flat, never nested).
2) Location markers [...] ... → either <p> or <lg> (latter can nest x1).
3) Tab → <lg>/<l>
4) Page markers <page[-col][,line]> → <pb>, (<cb>, <lb>) (n attribute)
5) Line-end newline → <lb> (n attribute as counted on book page)
6) Notes (...) → <note> (those that disrupt author's natural-language flow)

In addition, there are editorial bracket sets that describe the e-text itself, NOT the printed edition source:
7) ≤...≥ is ante-correctionem (to be deleted)
8) «...» is post-correctionem (to be kept)
9) ¿...¿ is anything confusing (to be kept)

Editorial markup as found in the printed edition itself should be interpreted and re-represented in one of the above ways. E.g., if the editor used [...] for an unwanted interpolation or (...) to suggestion a correction for some number of akṣaras, these would need to be interpreted with ≤...≥ and a combination of ≤...≥«...» (with the correct number of akṣaras), respectively. 


# Verse/Prose and Logical/Physical Orientation

The data model has two orientation flavors, depending on the dominance of numbered verse:
1. Numbered verse only - primarily oriented toward verse numbering
2. Prose +/- verse - primarily oriented toward physical features of edition

A verse-only text basically has two tab-separated columns: logical verse identifiers on the left, text on the right.
Edition page numbers are recorded for reference purposes, but they are not used for location markers. 

Substantial presence of prose (e.g. commentary on verse base text, śāstric treatise, gadyakāvya, etc.)
requires changing location marker orientation to the physical features of the edition:
page and line numbers for the beginning of each paragraph.


# Character Set

The transliteration scheme used is IAST, with the following preferences:
- pre-composed characters (e.g., single-char ṝ rather than triple-char ṝ)
- standard IAST ṃ ṛ ḷ e o (rather than ISO 15919 ṁ r̥ l̥ ē ō)
- special chars ḻ ẖ ḫ lṁ for ळ ᳵ ᳶ लँ
- lowercase except for e.g. emphasis of proper names or indication of grammatical anubandhas
- Prakrit: diaresis for otherwise ambiguous intra-word vowel hiatus (e.g., jaïo), breve for short vowels (ĕ ŏ)

Punctuation preferences:
- ASCII | for danda
