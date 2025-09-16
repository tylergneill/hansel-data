# HANSEL

“Human-Accessible and NLP-ready Sanskrit E-Text Library.” A companion project to GRETIL.

See project website: https://hansel-library.info/about.

# repo concept and structure

Users submit e-text material to HANSEL via email (`hanselrepository@gmail`) in any format that they like.
This submission enters text content Tier I and also gets an associated metadata file.
Even images can be accepted, in which case the basic OCR result serves as the Tier I version.
The Tier I text can be immediately committed to the repo and surfaced on the collection website. 

Next, on a branch, a copy is made of the Tier I file and placed in the Tier II directory.
This new Tier II file is gradually reworked, either in plain-text or in XML,
to conform with HANSEL's data model.
The branch can be merged only once the file passes the automated structure check,
and once a basic manual quality check is performed.
Upon merging, automatic transforms ensure all three end-file types: .txt, .xml, and .html.
These are surfaced on the collection website as a Tier II-status text.

Similarly, Tier II texts may be gradually reworked into Tier III texts,
through further proofreading, structural improvements, and closer alignment to source editions. 

At any point, metadata can be aggregated in a single .json file.
Quality-control on individual metadata files (in Markdown, .md) ensures this transform, as well.

# curation and governance

During HANSEL's initial phase, the creator will oversee all repository activities.

Once HANSEL has been operating and accepting contributions for a few years,
control will be distributed more widely to a team of experts.
