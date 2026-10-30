# Bhagavadajjuka proofreading fixes (pending)

Fixes that were made on the `proofread-bhagavadajjuka` and `proofread-bhagavadajjuka-2` branches (Apr–Aug 2026) but never merged. Those branches were deleted on 2026-10-30; this file captures what they changed so the work can be redone on a fresh branch.

Original commits, for reference (still reachable by hash until garbage-collected): `3d45588` / `49a1636` (kimartham), `5197082` / `01e9e07` (verse 5 chāyā), `4590a27` (converter tweak, v1 only).

## 1. Join `kim artham` → `kimartham`

File: `texts/project_editions/txt/bhagavadajjuka.txt`

Three identical speech lines by the parivrājaka:

```
parivrājakaḥ — kim artham |
```

should become

```
parivrājakaḥ — kimartham |
```

## 2. Restore lost chāyā for verse 5

The Prakrit verse 5 (Śāṇḍilya, right after `śāṇḍilyaḥ — ˹bho bhaavaṃ |˼`) is not marked as Prakrit, and its chāyā is missing from the chāyā file.

In `texts/project_editions/txt/bhagavadajjuka.txt`, wrap the verse in `˹…˼`:

```
	˹ṇa māmao atthi ṇa bhāduo vā
	pidā kudo me bhaavappasādo |
	ekko ahaṃ aṇṇahadattaṇeṇa
	jaṭṭhiṃ paviṭṭho ṇa khu dhammalohā || 5 ||˼
```

In `texts/project_editions/txt/chaya/bhagavadajjuka.txt`, insert the verse chāyā after the `bhoḥ bhagavan |` line (the chāyā of `bho bhaavaṃ |`):

```
	na māmako 'sti na bhṛātṛko vā
	pitā kuto me bhagavatprasādaḥ |
	eko 'ham annahatatvena
	yaṣṭiṃ praviṣṭo na khalu dharmalobhāt || 5 ||
```

Proofread this chāyā against the edition before committing: `bhṛātṛko` (expected `bhrātṛko`) and `annahatatvena` (cf. Prakrit `aṇṇahadattaṇeṇa`) look like typos carried over from the branch.

## 3. (Optional) Drop a spurious line label before verse chāyā

On v1 only, `utils/transforms/html/convert_xml_to_html.py` was changed where a nested `<lg type="chāyā">` is opened inside a Prakrit verse. Current behavior: a pending lb-label gets *flushed* into the Prakrit verse before the chāyā div opens. The v1 change *discarded* it instead (`self.pending_label = None`). The reasoning was that a trailing `<lb>` at the end of the last Prakrit `<l>` marks the start of the next physical line, and the following `<sp>` already emits the correct coordinate.

v2 left this change out, possibly on purpose. Only apply it after regenerating with fixes 1–2 and confirming a spurious page/line marker actually shows up around verse 5, and check that other drama texts (Unmattarāghava, Prabodhacandrodaya) don't lose legitimate labels.

## Done when

- `make regen` produces the expected XML/HTML diffs for bhagavadajjuka only.
- Verse 5 shows its chāyā in the rich HTML viewer.
- Metadata "Last Updated" / digitization notes for bhagavadajjuka are bumped.
