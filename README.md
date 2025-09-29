# HANSEL: Human-Accessible and NLP-ready Sanskrit E-Text Library

A companion project to the now-defunct GRETIL.

HANSEL is a Sanskrit e-text library. 
It is also a website giving access to that library. 

This repo contains the library data and code.
[Another repo](https://github.com/tylergneill/hansel-app) contains code for the website..

# Data Repo Concept and Structure

Users submit e-text material to HANSEL via email (`hanselrepository@gmail`) in any format that they like.
These are preserved in `texts/originals`.

The project maintainer manually converts this content into a plain-text file.
This is stored in `texts/processed_txt`,
and a corresponding metadata file, in Markdown, is stored in `metadata`.

The plain-text file is structurally reworked until it passes `utils.validation.validate -s`.
It is then transformed into TEI-XML with `utils.transforms.xml.convert_plaintext_to_xml`.
The quality of this XML representation is tested by converting it round-trip back to plain-text
with `utils.transforms.xml.convert_xml_to_plaintext`.
This constitutes structural validation.

The XML can then be transformed into more usable HTML with `utils.transforms.html.convert_xml_to_html`.

All file types are zipped together using `utils.transforms.zip_texts`.

Metadata is also transformed to HTML, with `utils.metadata.render_md_to_html`,
and consolidated in two ways: `utils.metadata.zip_metadata` and `utils.metadata.jsonify_metadata`.

All file consolidations are packaged with the latest `VERSION` file,
which is bumped to the current date whenever there are changes to core data (`originals`, `processed_txt`, `metadata`).
Derivatives (XML, HTML, JSON, zips) are automatically ensured to have the latest `VERSION` and regenerated as needed.

# Integration with App Repo

The web app repo has a dummy data folder `static/data` for local dev testing.
At actual runtime, the `docker run` option `-v, --volume` overwrites the dummy data 
by mounting a local clone of this data repo.  

See dev instructions at https://github.com/tylergneill/hansel-app for more info.

# Curation and Governance

During HANSEL's initial phase, the creator will oversee all repository activities.

Once HANSEL has been operating and accepting contributions for a few years,
control will be distributed more widely to a team of experts.
