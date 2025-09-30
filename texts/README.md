# Texts

This folder contains HANSEL's text data.

See `DATA_MODEL.md` to understand the format of each file.

Corresponding metadata can be found in the `../metadata` folder.

# Versioning Concept

In addition to using Git to track the evolution of every file,
this collection also retains a copy of the originally submitted file,
whatever its format.

## Originals

These items are preserved as-is at the time of import into HANSEL.
They often contain additional information included by their creators,
and they may well be more human-readable,
but frequently they are not yet ready for consistent NLP processing.
Often, given file types like `.doc` etc.,
these do not render in-browser and so must be downloaded for inspection.

## Processed .txt

These items have been manually streamlined and restructured 
according to HANSEL's plain-text data model.
Among other things, this streamlining frequently involves removing para-textual notes outright
or prepping them to be automatically dropped.
More essentially, these items now pass the structural (`-s`) check with `utils.validation.validate`,
which checks for valid use of permitted HANSEL structural elements (mostly various kinds of brackets),
AND they survive roundtrip transformation from plaintext to XML and back (see below).

These items can then undergo further quality improvements, possibly regarding:
- structural markup
- Sanskrit content proofreading
- notation of underlying edition's errors and corresponding fixes
- line-by-line correspondence with source edition

See respective metadata files for the status of each text and what tasks remain.

## Transforms

From the plaintext source files, several additional data types are automatically produced.

- Using `utils.transforms.xml.convert_plaintext_to_xml`, the plaintext is transformed into TEI-XML.
  -  `utils.transforms.xml.convert_xml_to_plaintext` is used only for roundtrip testing. 
- Using `utils.transforms.html.convert_xml_to_html`, the XML is transformed into HTML, of two types: 
  - "plain" is a simpler, search-friendly representation
  - "rich" is built for in-browser reading

In addition, all five data stages (originals, processed plaintext, XML, and HTML x2)
are packages together as `.zip` files for cumulative download.
