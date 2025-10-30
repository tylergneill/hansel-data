# Texts

This directory houses the library's source texts. For the full ingestion, validation, and transform pipeline, see the [top-level repository README](https://github.com/tylergneill/hansel-data/blob/main/README.md).

Corresponding metadata can be found in the top-level `metadata` directory.

## Original Submissions

The `original_submissions/` directory preserves first-imported files exactly as they were received. These submissions may contain extra paratext and often require download for inspection because of formats such as `.doc` or `.pdf`.

## Project Digital Editions

Curated project editions live in `project_editions/xml/` and `project_editions/txt/`. TEI-XML and plain-text are maintained as co-equal working formats; their correspondence is outlined in `DATA_MODEL.md` and enforced by the round-trip scripts described in the top-level README.

Together, these co-editions are streamlined for consistent NLP processing, manually proofed over time, and validated before publication. Validation currently includes:
- schema validation of XML against the SARIT Simple profile
- structural checks of plain-text via `utils/validation/txt/validate.py -s`

Metadata about editorial state and outstanding tasks is recorded in the corresponding files under `metadata/markdown`.

## Transforms

Derivative HTML outputs are generated automatically from XML project editions, and XML and plain-text can be reciprocally generated from each other. Regeneration scripts live in `utils/transforms`; see the [repository README](https://github.com/tylergneill/hansel-data/blob/main/README.md) for the orchestrated workflow.
