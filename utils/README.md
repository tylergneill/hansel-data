# Utils and Static Data Bundle

This folder contains code that transforms HANSEL's core file types — project digital editions (`.txt`, `.xml`) and metadata (`.md`) — into derived formats (`.html`, `.json`).

## Versioning

This repository's [VERSION file](https://github.com/tylergneill/hansel-data/blob/main/VERSION) contains two values:
- `__data_version__`: a **datestamp** for the core data, corresponding to the latest "Last Updated" value found in the metadata
- `__bundle_version__`: a **Semantic Versioning number** for this utility code and the transforms it produces, i.e., the static data bundle