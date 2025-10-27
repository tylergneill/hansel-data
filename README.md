# HANSEL: Human-Accessible and NLP-ready Sanskrit E-Text Library

A companion project to GRETIL.

HANSEL is a Sanskrit e-text library. 
It is also a website giving access to that library. 

This repo contains the library data and code.
[Another repo](https://github.com/tylergneill/hansel-app) contains code for the website.

# Data Repository Concept and Structure

Users submit e-text material to HANSEL through the website contact form (or by email) in any format they prefer.  
All originally submitted files are preserved in `texts/original_submissions`.

The project maintainer manually converts each submission into a normalized plain-text file, stored in `texts/txt`.  
A corresponding metadata file (in Markdown) is created and stored in `metadata`.

The plain-text file is iteratively revised until it passes structural validation with `utils.validation.validate -s`.  
Once valid, it is transformed into TEI-XML `<text>` format using `utils.transforms.xml.convert_plaintext_to_xml`.  
This XML is then round-tripped back to plain text via `utils.transforms.xml.convert_xml_to_plaintext` to confirm internal consistency.
This completes structural validation.

From there, the XML can be converted into HTML with `utils.transforms.html.convert_xml_to_html`.  
The XML also serves as a co-primary edition of the text alongside the plain-text,
for situations where modifying the XML directly is preferable.  
For example, when the original submission is already in (TEI) XML,
system ingestion may proceed first via XML and only later in plain-text.

The XML `<teiHeader>` is initially generated from Markdown metadata using `utils.transforms.xml.convert_markdown_to_xml`  
and also regularly updated in the same way.
The Markdown file always remains the authoritative metadata source.

All text formats (misc. original submissions, digital edition plain text and XML, HTML)
are bundled together using `utils.transforms.zip_texts`.

Metadata is similarly transformed into HTML via `utils.metadata.render_md_to_html`  
and consolidated in two forms: a zip file (`utils.metadata.zip_metadata`) and JSON (`utils.metadata.jsonify_metadata`).

All consolidated files are packaged with the current `VERSION` file.  
This file is updated to the most recent date whenever changes occur in core data (`original_submissions`, `txt`, `xml`, `metadata`),
according to the three "Updated" fields in the metadata files, which must be updated manually.
Derivative formats (HTML, JSON, ZIPs) automatically inherit the latest version information and are regenerated as needed.

# Data Transform Maintenance

The data in this repository undergoes several transformations 
to automatically produce various output formats (TEI-XML, TXT, HTML, JSON, ZIP). 
These transformations are orchestrated by a set of Python scripts 
located in the `utils/transforms/` directory.

The primary script for regenerating all derivative data is `utils/transforms/regenerate_all.py`. 
This script executes the following in sequence:

1.  `utils/transforms/metadata/regenerate.py`: This script processes all metadata files. It renders Markdown metadata to HTML, consolidates metadata into a JSON file, and then zips all metadata files (Markdown and HTML).
2.  `utils/transforms/xml/regenerate.py --xml/--txt`: This script converts processed plaintext files into TEI-XML `<text>` format or vice verse, depending on respective flags. The `--xml` mode also updates TEI headers in XML files using information from the Markdown metadata.
3.  `utils/transforms/html/regenerate.py`: This script converts the generated TEI-XML files into HTML.

The `utils/transforms/regenerate_all.py` script also requires the `--xml/--txt` flag to determine the mode of `xml/regenerate.py`.

## Version Control and Validation

To ensure data consistency and proper versioning, a strict version check is implemented.
The `__data_version__` value specified in the `VERSION` file at the project root 
must exactly match the latest date found 
in any `# Text Last Updated` or `# Metadata Last Updated` field 
across all Markdown metadata files (`metadata/*.md`). 
This check is performed by the `utils/transforms/metadata/zip_metadata.py` script, 
which is part of the metadata regeneration pipeline. 
If there is a mismatch, the script will fail, 
prompting the maintainer to update the `__data_version__` in the `VERSION` file 
to reflect the latest changes in the metadata. 
This ensures that the `VERSION` file always accurately reflects 
the most recent update across all data.

# Integration with App Repo

The web app repo has a dummy data folder `static/data` for local dev testing.
At actual runtime, the `docker run` option `-v, --volume` overwrites the dummy data 
by mounting a local clone of this data repo.  

Find dev instructions for the app at https://github.com/tylergneill/hansel-app.

# Curation and Governance

During HANSEL's initial phase, the creator will oversee all repository activities.

Once HANSEL has been operating and accepting contributions for a while (a few years?),
control will be distributed more widely to a team of experts.
