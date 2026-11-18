"""Unit tests for ``change_date_attributes`` in tei_builder.py.

Covers every free-text contributor date currently found in HANSEL's metadata.
Run from the repo root with:

    python -m unittest discover -s utils/transforms/xml/tests
"""
import sys
import unittest
from pathlib import Path

# tei_builder is imported as a sibling script module elsewhere, so do the same here.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tei_builder import change_date_attributes  # noqa: E402


class ChangeDateAttributesTest(unittest.TestCase):

    CASES = {
        # single month or year -> @when
        "Aug 2026": {"when": "2026-08"},
        "Jan 2026": {"when": "2026-01"},
        "May 2026": {"when": "2026-05"},
        "Oct 2026": {"when": "2026-10"},
        "July 2025": {"when": "2025-07"},
        "September 2026": {"when": "2026-09"},
        "Sept 2026": {"when": "2026-09"},
        "2025": {"when": "2025"},
        "2026": {"when": "2026"},
        # already ISO -> kept as is
        "2022-02-01": {"when": "2022-02-01"},
        # month ranges sharing one year, any dash, spaced or not
        "Jan–Mar 2026": {"from": "2026-01", "to": "2026-03"},
        "Jan–Feb 2026": {"from": "2026-01", "to": "2026-02"},
        "Feb–June 2026": {"from": "2026-02", "to": "2026-06"},
        "May–Jul 2025": {"from": "2025-05", "to": "2025-07"},
        "July–Aug 2026": {"from": "2026-07", "to": "2026-08"},
        "Mar–May 2023": {"from": "2023-03", "to": "2023-05"},
        "March – September 2026": {"from": "2026-03", "to": "2026-09"},
        "March – July 2026": {"from": "2026-03", "to": "2026-07"},
        "June — July 2026": {"from": "2026-06", "to": "2026-07"},
        "June-July 2026": {"from": "2026-06", "to": "2026-07"},
        "June - July 2026": {"from": "2026-06", "to": "2026-07"},
        # range across years
        "Dec 2025 – Jan 2026": {"from": "2025-12", "to": "2026-01"},
        # year ranges
        "2016–2017": {"from": "2016", "to": "2017"},
        "2017–2021": {"from": "2017", "to": "2021"},
        "2020–2025": {"from": "2020", "to": "2025"},
        "2024–2025": {"from": "2024", "to": "2025"},
        # decade
        "2000s": {"from": "2000", "to": "2009"},
        # unparseable -> no attribute
        "Date unknown": {},
        "": {},
        "Spring 2026": {},
        "Jan–2026": {},
    }

    def test_known_values(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(change_date_attributes(text), expected)


if __name__ == "__main__":
    unittest.main()
