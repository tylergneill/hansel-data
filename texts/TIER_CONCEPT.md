# Tier Architecture Concept

The text files in this collection are represented at multiple stages of processing,
both to clarify provenance and to facilitate sharing sooner rather than later.

The “original → cleaned → curated” progression is nothing new in data processing.
A data-analytics company called Databricks is known for its precious-metals metaphor:
“Bronze → Silver → Gold”.
This emphasizes value of the final, most specific transformation,
but in practice, the “original”̦ or “raw” data is also valuable
for preserving unique and interesting details.

Thus, I adapt this to a more neutral system of numbered Tiers.

## Tier I

These items are preserved as-is at the time of import into HANSEL
and often contain additional information included by their creators.
They may be readable in their own ways,
but they are most likely not yet ready for clean NLP processing.

## Tier II

These items have been manually streamlined and restructured according to HANSEL's data model.
Among other things, this streamlining frequently involves removing para-textual notes outright 
or prepping them to be automatically dropped.
Even more importantly, these items now pass the structural (`-s`) check with `utils.validation.validate`,
which checks for valid use of permitted HANSEL structural elements (mostly various kinds of brackets),
and it survives roundtrip conversion from plaintext to XML and back.

See `DATA_MODEL.md` for more detail.

## Tier III

These items have undergone further quality improvements, possibly including:
- clarifying and possibly extending structural markup
- further proofreading Sanskrit content
- clarifying notation of the underlying edition's errors and corresponding fixes
- restoring line and/or paragraph breaks to better correspond with the source edition

See respective metadata files for the status of each file and remaining tasks.  