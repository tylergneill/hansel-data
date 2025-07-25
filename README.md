# HANSEL

“Human-Accessible and NLP-ready Sanskrit E-Text Library.” An updated successor project to GRETIL.

Deployment About page: https://hansel-stg.duckdns.org/about.

# repo concept and structure

Users submit e-text material to HANSEL via email (`hanselrepository@gmail`) in any format that they like.
This submission enters the “bronze” tier of text content and also gets an associated metadata file.
Even images can be accepted, in which case the basic OCR result serves as the bronze version.
The bronze text can be immediately committed to the repo and surfaced on the collection website. 

Next, on a branch, a copy is made of the bronze file and placed in the “silver” tier.
This new silver file is gradually reworked, either in plain-text or in XML,
to conform with HANSEL's data model.
The branch can be merged only once the file passes the automated structure check,
and once a basic manual quality check is performed.
Upon merging, automatic transforms ensure all three end-file types: .txt, .xml, and .html.
These are surfaced on the collection website as a silver-status text.

Similarly, silver texts may be gradually reworked into gold texts,
through further proofreading, structural improvements, and closer alignment to source editions. 

At any point, metadata can be aggregated in a single .json file.
Quality-control on individual metadata files (in Markdown, .md) ensures this transform, as well.

# curation and governance

During HANSEL's initial phase, the creator will oversee all repository activities.

Once HANSEL has been operating and accepting contributions for a few years,
control will be distributed more widely to a team of experts.
