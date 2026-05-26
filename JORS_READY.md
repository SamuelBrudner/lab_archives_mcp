# JORS Submission Checklist

Final pre-upload check for the 26 May 2026 JORS resubmission.

## Upload package

Primary files for the JORS portal:

- `jors_metapaper.md` - revised metapaper, including the architecture figure reference.
- `jors_response_to_reviewers.md` - point-by-point response to editor and reviewer comments.
- `jors_cover_letter.md` - resubmission cover letter for the editor.
- `paper.bib` - bibliography cited by the metapaper.
- `docs/figures/architecture.png` - revised Figure 1 asset referenced by the metapaper.

Supporting source files to keep with the repository package:

- `jors_metapaper.tex` - LaTeX rendering of the revised metapaper.
- `jors_metapaper.org` - Org source used for the manuscript history.
- `docs/figures/architecture.mmd` - source for the architecture diagram.
- `docs/figures/architecture.svg` - vector rendering of the architecture diagram.
- `CITATION.cff` - repository citation metadata.
- `README.md`, `LICENSE`, `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md` - repository-facing metadata and governance files.

## Pre-upload verification

- [x] Revised manuscript is present as `jors_metapaper.md`.
- [x] Response document is present as `jors_response_to_reviewers.md`.
- [x] Editor cover letter is present as `jors_cover_letter.md`.
- [x] Referenced figure asset is present at `docs/figures/architecture.png`.
- [x] Figure source and alternate rendering are present at `docs/figures/architecture.mmd` and `docs/figures/architecture.svg`.
- [x] Bibliography is present as `paper.bib`.
- [x] Repository metadata files are present: `README.md`, `CITATION.cff`, `LICENSE`, `CONTRIBUTING.md`, and `CODE_OF_CONDUCT.md`.
- [x] The reviewed archive tag exists locally as `v0.3.2`.
- [x] The reviewed archive version DOI is recorded consistently as <https://doi.org/10.5281/zenodo.17772522>.
- [x] The current source-tree version DOI is recorded as <https://doi.org/10.5281/zenodo.19672568>.
- [x] No compulsory editor or reviewer item remains unaddressed in `jors_response_to_reviewers.md`.
- [x] Local validation passed during the revision: `conda run -p ./conda_envs/test-env pytest -q -m "not integration" --cov=src --cov-report=term --cov-report=xml` completed with 239 passing tests, one skipped test, six deselected integration tests, and 74% total line coverage.

## Version and citation story

- JORS archive/citation target: `v0.3.2`, version DOI <https://doi.org/10.5281/zenodo.17772522>.
- Zenodo concept DOI: <https://doi.org/10.5281/zenodo.17728440>.
- Archived release date: 2025-12-01.
- Current source tree: `0.4.0`, version DOI <https://doi.org/10.5281/zenodo.19672568>, Git tag dated 2026-04-20 and Zenodo publication dated 2026-04-21.
- Cite `0.4.0` only when discussing linked-data export or other changes after the archived JORS snapshot.

## Final submission status

The repository package is ready for portal upload. The actual JORS portal submission remains the external action to perform after this repository check.
