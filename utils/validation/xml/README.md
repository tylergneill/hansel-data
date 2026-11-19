# HANSEL XML Validation Workflow

This directory holds the validation toolchain for HANSEL's TEI-XML project editions (`texts/project_editions/xml/`): the schemas, the Makefile that runs them, and helpers for comparing results with the Oxygen XML Editor.

- `schemas/` — validation assets:
  - `hansel.odd`, `hansel.rng`, `hansel.isosch` — **the HANSEL schema**, used by default (see below);
  - `sarit.odd`, `sarit.rng`, `sarit.isosch` — SARIT's schema, kept untouched for comparison;
  - `tei_all.rng` — stock TEI P5 4.10.2 `tei_all`, for the cross-check;
  - `iso-schematron/` — the ISO Schematron skeleton XSLTs that turn an `.isosch` into a validator stylesheet.
- `Makefile` — runs RELAX NG (Jing) and Schematron (Saxon) for every XML file, the `tei_all` cross-check, and the schema compilation.
- `compile_odd.py` — compiles an ODD into `.rng` + `.isosch` with the TEI Stylesheets.
- `saxon_cli.py` — a pip-only stand-in for the `saxon` command line.
- `cli/` — per-run output: SVRL reports and raw Jing logs (git-ignored).
- `oxygen_comparison/` — scripts for reconciling Oxygen logs with CLI results.

## The HANSEL schema

HANSEL's XML is validated against its own customization of SARIT's schema. SARIT (`sarit.odd`) is an "ODD by example": TEI narrowed down to what the SARIT corpus uses. That corpus has no drama, and its closed value lists don't include some of HANSEL's own type labels, so SARIT's schema rejects markup HANSEL needs. (SARIT has a single schema; "SARIT Simple" is the name of its prose encoding guidelines, not of a separate schema.)

`hansel.odd` is a copy of `sarit.odd` with these changes only:

| Change | Why |
|---|---|
| `schemaSpec/@ident` is `hansel`; own `teiHeader` title | identifies the customization |
| `sp/@who` allowed (SARIT deletes it) | drama: each speech points at its speaker's `castList` role |
| `lg/@type` adds `group` | several verses sharing one location marker are wrapped in `<lg type="group">` |
| `seg/@type` adds `prakrit`, `chāyā` | drama: a Prakrit passage and its Sanskrit chāyā are paired as two `<seg>`s |

Everything HANSEL's schema accepts is still standard TEI, which `make validate-tei-all` checks against stock `tei_all`.

## Prerequisites

Either Homebrew engines:

```sh
brew install jing-trang saxon
```

or the pip-only route, which comes with the repo's main requirements (run from the repo root):

```sh
pip install -r requirements.txt
```

The repo's `requirements.txt` includes `jingtrang` and `saxonche`, which provide `pyjing` and the `saxonche` library used by `saxon_cli.py` and `compile_odd.py`. Java requirements differ: Homebrew's `saxon` is the Java Saxon-HE (Homebrew installs OpenJDK for it), while pip's `saxonche` is SaxonC, a self-contained native build that needs no Java. Jing is a Java program either way: `pyjing` just runs the bundled `jing.jar`, so it needs `java` on `PATH` (GitHub's `ubuntu-latest` runners have it).

## Validating

From this directory (or `make validate` / `make validate-tei-all` from the repo root):

```sh
make validate                                       # Homebrew engines
make validate JING=pyjing SAXON="python saxon_cli.py"  # pip-only
make validate-tei-all                               # cross-check against stock TEI
```

Each file gets one status line, plus its first errors if it fails. `make validate` exits non-zero if any file fails RELAX NG or Schematron, so CI can gate on it. A Schematron failure is either a failed `<assert>` or a fired `<report>` (TEI writes many of its rules as reports). SVRL reports land in `cli/reports/`, raw Jing output and the failure summary in `cli/build/`.

To run the old SARIT check instead:

```sh
make validate RNG=schemas/sarit.rng SCH=schemas/sarit.isosch
```

Other variables (`XML_DIR`, `OUT_DIR`, `SKEL`, …) can be overridden the same way.

## Recompiling the HANSEL schema

Only needed when `schemas/hansel.odd` changes:

```sh
make schemas
```

This downloads the pinned inputs into the git-ignored `.cache/` (once), then runs `compile_odd.py`, which writes `schemas/hansel.rng` and `schemas/hansel.isosch`. Commit both. The pinned inputs are:

- TEI Stylesheets 7.58.0 (GitHub release `TEIC/Stylesheets`, `tei-xsl-7.58.0.zip`);
- TEI P5 4.10.2 `p5subset.xml`, fetched on its own from TEI's versioned Vault (byte-identical to the copy in the 333 MB `tei-4.10.2.zip` release).

`make fetch-tei-all` refreshes `schemas/tei_all.rng` from the same Vault; it's only needed when bumping the TEI version. To bump either version, change it in both the Makefile and `compile_odd.py`, recompile and recommit.

The repo's ISO Schematron skeleton XSLTs print a harmless "unrecognized element … param" warning on schemas compiled with these newer Stylesheets (which emit `sch:param`). The checks still run correctly.

## Oxygen Workflow

The files in `oxygen_comparison/` let you keep a record of Oxygen XML Editor runs. After exporting logs from Oxygen, drop them into `oxygen_comparison/oxygen_logs.txt` and normalise them:

```sh
python oxygen_comparison/oxygen_logs_to_csv_blocks.py
```

This produces `oxygen_comparison/oxygen_fails.csv` with the same columns as the CLI CSV, which `python oxygen_comparison/make_reports_to_csv.py` writes to `oxygen_comparison/makefile_fails.csv`.

## Comparing Results

To check whether the GUI and CLI validations agree, place the exported Oxygen log as `oxygen_comparison/oxygen_logs.txt`, then run either

```sh
make compare
```

or the comparison script directly:

```sh
python oxygen_comparison/compare_fail_csvs.py
```

The process writes `oxygen_comparison/only_makefile.csv`, `oxygen_comparison/only_oxygen.csv`, and `oxygen_comparison/shared_both.csv`, grouping by SVRL file, status, and message. Counts from each source are embedded so you can spot drift easily.

## Notes

- All output (`cli/build`, `cli/reports`, Oxygen CSVs, comparison CSVs) is derived and can be regenerated.
- `make clean` removes the generated reports/CSVs and recreates an empty `oxygen_comparison/oxygen_logs.txt` ready for the next run.
