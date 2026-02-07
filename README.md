# HANSEL: Human-Accessible and NLP-ready Sanskrit E-Text Library

A companion project to GRETIL.

HANSEL is a Sanskrit e-text library. It is also a website giving access to that library. 

This repo contains the library data and code. [Another repo](https://github.com/tylergneill/hansel-app) contains code for the website.


# Data Repository Concept and Structure

## Submission

First-time users submit e-text material to HANSEL through the website contact form (or later by email) in whatever format they prefer. These submitted files are preserved in `texts/original_submissions` and made available on the website as received.

## Project Editions and Metadata

The library curator (Tyler) then manually converts each submission into standardized formats (`texts/project_editions/txt`, `texts/project_editions/xml`) compatible with HANSEL's automated system. These living digital documents, subject to ongoing manual refinement and carefully versioned for accurate citation, constitute HANSEL's project editions.

A corresponding metadata file in `metadata/markdown` serves as the source of truth for bibliographic and versioning information. The XML `<teiHeader>` is populated from a subset of fields in these Markdown files using `utils/transforms/xml/convert_markdown_to_xml.py`.

The XML `<teiHeader>` and `<text>` are validated against RELAX NG and Schematron schemas generated from the SARIT Simple `.odd` file. The plain-text files are validated with the internal tool `utils/validation/txt/validate.py` with the `-s` (structure) flag, and optionally the `-c` (content) flag, which analyzes n-gram frequencies. These two working formats (XML and plain-text) are guaranteed to be fully round-trip convertible using `utils/transforms/xml/convert_plaintext_to_xml.py` and `utils/transforms/xml/convert_xml_to_plaintext.py`.

## Transforms

Once validated, the XML is converted into HTML using `utils/transforms/html/convert_xml_to_html.py`. Metadata is transformed into HTML with `utils/metadata/convert_md_to_html.py` and also consolidated into JSON using `utils/metadata/jsonify_metadata.py`. These transformation scripts reside in `texts/transforms` and `metadata/transforms`, respectively.

## Versioning

In addition to Git and GitHub's fine-grained versioning, changes to project-edition and metadata files are logged in the "Digitization Notes" and "Last Updated" metadata fields. The machine-actionable timestamps from the latter are aggregated into a single `__data_version__` value, equal to the latest change date, and stored in the repository's `VERSION` file.

The same `VERSION` file also records `__bundle_version__`, a Semantic Versioning identifier for the utility code and static data bundle produced by `utils/`. This number increments whenever the transformation tooling or generated outputs change.

Cumulative downloads generated with the website include both the version file and full metadata, complete with datestamps for individual items. Additional file history can be viewed directly on GitHub.


# Data Transform Pipeline
 
Transformations that generate various file formats (TEI-XML, TXT, HTML, JSON) are managed by a coordinated set of Python scripts located in the `utils/transforms/` directory.

The main entry point for regenerating all derivative data is `utils/transforms/regenerate_all.py`, which executes the following sequence:

1.  `utils/transforms/metadata/regenerate.py`: Processes all metadata files, rendering each Markdown metadata file to HTML and also consolidating all of them into a single JSON file.
2.  `utils/transforms/xml/regenerate.py --xml/--txt`: Converts processed plain-text files into TEI-XML `<text>` format or vice versa, depending on the mode flag, which specifies which will be generated. When run with `--xml`, it also updates the TEI headers in XML files using information from the corresponding Markdown metadata.
3.  `utils/transforms/html/regenerate.py`: Converts TEI-XML files into HTML, producing both "rich" (the primary display format on the HANSEL website) and "plain" versions. The "plain" version is also embedded within the "rich" one to improve in-browser full-text search performance. 

Note that `utils/transforms/regenerate_all.py` also requires the `--xml` or `--txt` flag to determine the operating mode for `utils/transforms/xml/regenerate.py`.

# Integration with App Repo

The web app repository includes a dummy data folder at `static/data` for local development and testing. At runtime, Docker's `-v, --volume` option mounts a clone of the actual data repository from a local path, either on a developer's machine or the cloud-based public server.

Find dev instructions for the app at https://github.com/tylergneill/hansel-app.

# Curation and Governance

During HANSEL's initial phase, the project creator (Tyler) will oversee all repository activity.

After the project has been running and accepting contributions for some time (on the order of a few years), stewardship will gradually be distributed among a broader team of experts.
