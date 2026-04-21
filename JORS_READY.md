# JORS Submission Checklist

Final pre-upload check for the 15 April 2026 JORS resubmission.

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
- [x] The reviewed archive DOI is recorded consistently as <https://doi.org/10.5281/zenodo.17728440>.
- [x] No compulsory editor or reviewer item remains unaddressed in `jors_response_to_reviewers.md`.
- [x] Local validation passed: `conda run -n labarchives-mcp-pol pytest -q` completed with 217 passed and 6 skipped on 15 April 2026.

## Version and citation story

- JORS archive/citation target: `v0.3.2`, DOI <https://doi.org/10.5281/zenodo.17728440>.
- Archived release date: 2025-11-30.
- Current source tree: `0.3.3`, a post-archive maintenance release dated 2025-12-16.
- Cite `0.3.3` only when discussing changes after the archived JORS snapshot.

## Final submission status

The repository package is ready for portal upload. The actual JORS portal submission remains the external action to perform after this repository check.
