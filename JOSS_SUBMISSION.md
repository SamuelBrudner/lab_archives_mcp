# JOSS Submission Checklist for lab_archives_mcp

This document tracks completion of JOSS submission requirements.

## ✅ Licensing (COMPLETE)

- [x] OSI-approved license file (MIT) at repo root → `LICENSE`
- [x] `pyproject.toml` updated with MIT license
- [x] License statement in README with link to LICENSE file

## ✅ Functionality (COMPLETE)

Core tools are stable and tested:
- [x] `list_labarchives_notebooks()` - List all notebooks
- [x] `list_notebook_pages(notebook_id, folder_id)` - Navigate pages/folders
- [x] `read_notebook_page(notebook_id, page_id)` - Read page content
- [x] `search_labarchives(query, limit)` - Semantic vector search
- [x] `upload_to_labarchives(...)` - File upload (marked experimental)

All features have basic tests and are documented.

## ✅ Documentation (COMPLETE)

README includes:
- [x] Installation instructions (conda-lock setup)
- [x] Configuration steps for LabArchives API keys
- [x] End-to-end usage example (list → navigate → read → search)
- [x] API schemas documented via Pydantic models
- [x] Integration guides for Claude Desktop and Windsurf (both verified)
- [x] Clear project scope statement (read-only + vector search)

## ✅ Testing & CI (COMPLETE)

- [x] pytest suite passes locally (`pytest -m "not integration"`)
- [x] GitHub Actions workflow added (`.github/workflows/tests.yml`)
- [x] Integration tests marked appropriately and skip without credentials
- [x] Instructions in CONTRIBUTING.md for running full integration tests

## ✅ Community Guidelines (COMPLETE)

- [x] `CONTRIBUTING.md` created with:
  - Dev environment setup
  - How to run tests & style checks
  - Where to open issues/PRs
  - Commit message format (Conventional Commits)
- [x] Contributing guidelines linked from README
- [x] `CODE_OF_CONDUCT.md` added
- [x] GitHub issue templates (bug report, feature request)
- [x] Pull request template

## ✅ Packaging & Release (COMPLETE)

- [x] Version set to v0.1.0 in `pyproject.toml`
- [x] `CHANGELOG.md` updated with v0.1.0 release notes
- [x] Console entry point (`labarchives-mcp`) works after install
- [x] Package metadata complete (authors, description, classifiers)

## ✅ JOSS Paper (COMPLETE)

- [x] `paper.md` created (~1000 words) with:
  - Summary / Statement of Need
  - Functionality description
  - State of the field / related work
  - Example usage
  - Acknowledgements
- [x] `paper.bib` with relevant citations
- [x] ORCID placeholder (needs to be updated with actual ORCID)

## 🔲 Release Tasks (TODO)

- [ ] Update ORCID in `paper.md` if available
- [ ] Run final test suite: `pytest -v -m "not integration"`
- [ ] Tag release: `git tag v0.1.0`
- [ ] Push tag: `git push origin v0.1.0`
- [ ] Create GitHub Release with changelog
- [ ] (Optional) Add Zenodo DOI badge after first release

## Next Steps for JOSS Submission

1. **Verify all files are committed**:
   ```bash
   git status
   git add LICENSE CONTRIBUTING.md CODE_OF_CONDUCT.md paper.md paper.bib .github/
   git commit -m "chore: add JOSS submission materials"
   ```

2. **Tag the release**:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0 for JOSS submission"
   git push origin main
   git push origin v0.1.0
   ```

3. **Create GitHub Release**:
   - Go to https://github.com/SamuelBrudner/lab_archives_mcp/releases/new
   - Select tag v0.1.0
   - Use content from CHANGELOG.md for release notes
   - Publish release

4. **Submit to JOSS**:
   - Go to https://joss.theoj.org/papers/new
   - Provide repository URL: https://github.com/SamuelBrudner/lab_archives_mcp
   - The JOSS bot will validate:
     - LICENSE file exists
     - paper.md and paper.bib exist
     - Repository has tagged release
     - README has installation instructions

5. **Post-submission**:
   - Respond to reviewer feedback
   - Make requested changes in new commits
   - Update paper if needed

## Optional Enhancements

- Add Codecov integration for coverage reports
- Add Zenodo integration for DOI generation
- Add CITATION.cff file for GitHub citation widget
- Add badges to README (test status, coverage, DOI)

## Repository Checklist Status

✅ All minimum blockers for JOSS submission are complete:
- License ✅
- CI for tests ✅
- CONTRIBUTING.md ✅
- End-to-end usage example in docs ✅
- Tagged release (pending) 🔲
- Paper.md ✅
