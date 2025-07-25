# Medallion Architecture Concept

The text files in this collection are represented at multiple stages of processing,
both to clarify provenance and to facilitate sharing sooner rather than later.

The “raw → cleaned → curated” progression is nothing new in data processing.
A data-analytics company called Databricks recently made this more colorful with a metaphor of precious metals:
- 🥉 bronze = raw
- 🥈 silver = cleaned
- 🥇 gold = curated

I'm using this metaphor, but specific meanings are adapted for the present context.

## Bronze

These items are preserved as-is at the time of import into HANSEL
and often contain additional information included by their creators.
They may be readable in their own ways,
but they are most likely not yet ready for clean NLP processing.

## Silver

These items have been manually streamlined and restructured.
The streamlining frequently involves removing para-textual notes outright or prepping them to be automatically dropped.
Most importantly, by definition, these items now pass the structural (`-s`) check with `utils.validation.validate`,
which checks for valid use of permitted structural elements (mostly various kinds of brackets).
Given this validation, round-trip conversion between XML and plain-text representations is now possible with `utils.transforms`.

## Gold

These items have undergone further quality improvements, possibly including:
- clarifying and possibly extending structural markup
- proofreading Sanskrit content
- clarifying notation of the underlying edition's errors and corresponding fixes
- restoring line and/or paragraph breaks to better correspond with the source edition

Gold status does not mean items are “perfect”.
See respective metadata files for more information on latest statuses and remaining tasks.  