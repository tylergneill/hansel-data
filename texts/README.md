# Texts

This folder contains HANSEL's text data.

Corresponding metadata can be found in the `../metadata` folder.

# Versioning Concept

In addition to using Git to track the evolution of every file,
this collection also retains a static copy of the originally submitted file,
whatever its format.

Then, from these submitted originals are produced the master files in XML and plain-text.
These are generally modified only to reflect substantial updates to the curated text.

Finally, any changes to master files are reflected in transforms
automatically generated from masters.

## Originals

These items are preserved as-is at the time of import into HANSEL.
They often contain additional information included by their creators,
and they may well be more human-readable,
but frequently they are not yet ready for consistent NLP processing.
Often, given file types like `.doc` etc.,
these do not render in-browser and so must be downloaded for inspection.

## Masters

HANSEL uses two parallel master formats: plain-text and XML.
The `DATA_MODEL.md` indicates how the respective components of each correspond to each other.

These items have been manually streamlined and restructured.
Among other things, this streamlining frequently involves removing para-textual notes outright
or prepping them to be automatically dropped.
More essentially, these items pass automatic validation:
- plain-text form passes the structural (`-s`) check with `utils.validation.validate`
- XML passes schema based validation against the SARIT "simple" schema
  - NEED A SCRIPT-BASED WORKFLOW FOR THIS / OR OXYGEN IF BETTER
- both survive roundtrip transformation basically intact
  - `utils.transforms.xml.convert_xml_to_plaintext`
  - `utils.transforms.xml.convert_plaintext_xml`

These items can then undergo further quality improvements, possibly regarding:
- structural markup
- Sanskrit content proofreading
- notation of underlying edition's errors and corresponding fixes
- line-by-line correspondence with source edition

See respective metadata files for the status of each text and what tasks remain.

## Transforms

From the plaintext source files, several additional data types are automatically produced.

- Using `utils.transforms.html.convert_xml_to_html`, XML is transformed into HTML, of two types:
  - "plain" is a simpler, search-friendly representation
  - "rich" is built for in-browser reading

In addition, all five data stages (originals, plain-text, XML, and HTML x2)
are packages together as `.zip` files for cumulative download.
