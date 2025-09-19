# Tier Architecture Concept

The text files in this collection are represented at multiple stages of processing,
both to clarify provenance and to facilitate sharing sooner rather than later.

The “original → cleaned → curated” progression is nothing new in data processing.
A data-analytics company called Databricks is known for its precious-metals metaphor:
“Bronze → Silver → Gold”.
This emphasizes value of the final, most specific transformation,
but in practice, the “original”̦ or “raw” data is also valuable
for preserving unique and interesting details.

Thus, I adapt this to a more neutral system of numbered “Tiers”.
After all, in some contexts, 1 is more valuable than 3,
while in others, 3 is more valuable than 1.

## Tier I

These items are preserved as-is at the time of import into HANSEL.
They often contain additional information included by their creators,
and they may well be more human-readable,
but frequently they are not yet ready for consistent NLP processing.

## Tier II

These items have been manually streamlined and restructured according to HANSEL's data model.
Among other things, this streamlining frequently involves removing para-textual notes outright 
or prepping them to be automatically dropped.
More essentially, these items now pass the structural (`-s`) check with `utils.validation.validate`,
which checks for valid use of permitted HANSEL structural elements (mostly various kinds of brackets),
and they survive roundtrip conversion from plaintext to XML and back.

See `DATA_MODEL.md` for more detail.

## Tier III

These items have undergone further quality improvements, possibly regarding:
- structural markup
- Sanskrit content proofreading
- notation of underlying edition's errors and corresponding fixes
- line-by-line correspondence with source edition

See respective metadata files for the status of each file and what tasks remain.
