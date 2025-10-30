# Utils and Static Data Bundle

This directory contains the scripts and configuration that generate HANSEL's derived formats (HTML, JSON, etc.) from the curated project editions and metadata.

## Key Entry Points

- `transforms/regenerate_all.py`: orchestrates regeneration of metadata, XML/text interchange, and HTML outputs. Requires either `--xml` or `--txt` to set the operating mode for the XML ↔ plaintext step.
- `validation/txt/validate.py`: runs structural (`-s`) and optional content (`-c`) checks on plain-text editions.

Additional context on how these pieces fit together, and on version numbering for the static data bundle, is presented in the [top-level repository README](https://github.com/tylergneill/hansel-data/blob/main/README.md).
