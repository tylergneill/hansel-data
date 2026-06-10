"""
Validation checks for parsed metadata records.

Each check function takes (filename, record) and returns a list of warning
strings (empty list = no issues). Warnings are non-fatal; they are printed
but do not halt the pipeline.
"""

import re


def _check_edition_pdfs(filename, record):
    warnings = []
    items = record.get("Edition PDFs", [])
    if isinstance(items, str):
        items = [items]
    if not items:
        return warnings
    first = items[0]
    if not first:
        return warnings
    if not first.startswith("["):
        warnings.append(
            f"{filename}: Edition PDFs first item does not start with '[' "
            f"and will be ignored by the app: {first!r}"
        )
    elif "](" not in first:
        warnings.append(
            f"{filename}: Edition PDFs first item looks like a link but is "
            f"missing '](' and will be ignored by the app: {first!r}"
        )
    return warnings


_CHECKS = [
    _check_edition_pdfs,
]


def validate_record(filename, record):
    warnings = []
    for check in _CHECKS:
        warnings.extend(check(filename, record))
    return warnings
