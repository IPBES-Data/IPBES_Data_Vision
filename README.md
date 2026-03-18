# IPBES Data Management Vision

Living-document implementation for the **IPBES Data Management Vision** using Quarto and R.

## Repository

- Source repo: <https://github.com/IPBES-Data/IPBES_Data_Vision>
- Website: <https://ipbes-data.github.io/IPBES_Data_Vision/>

## Source of Truth

- Main source document: `IPBES_Data_Vision.qmd`
- Metadata is authoritative in YAML frontmatter of `IPBES_Data_Vision.qmd`, including:
  - `title`
  - `version`
  - `release_date`
  - `doi`
  - `contact_email`
  - `release_notes`
  - `editors`

The same frontmatter metadata drives HTML metadata display and PDF title pages/citation content.

## Build

Requirements:

- R
- Quarto
- TinyTeX (for PDF builds)

Commands:

- `make build`
  - Render website HTML to `_site/`
  - Sync archived PDFs from `releases/` into `_site/releases/` (if present)
- `make build-pdf`
  - Build versioned PDF from frontmatter version into `releases/`
  - Render website HTML
  - Copy archived PDFs into `_site/releases/`
  - Update `_site/assets/IPBES-Data-Management-Vision-latest.pdf`

## Output Structure

- Published website output: `_site/`
- Current page: `_site/index.html`
- Older releases page: `_site/older-releases.html`
- Published PDFs for website links: `_site/releases/*.pdf`
- Latest PDF alias: `_site/assets/IPBES-Data-Management-Vision-latest.pdf`
- Persistent local PDF archive source: `releases/`

## Older Releases Behavior

- `older-releases.qmd` lists PDFs from `releases/` matching:
  - `IPBES-Data-Management-Vision-v*.pdf`
- The current version is excluded from the “older releases” table.
- To simulate multiple releases locally:
  1. Update `version` in `IPBES_Data_Vision.qmd`
  2. Run `make build-pdf`
  3. Repeat for another version

## Release Workflow (GitHub)

- PR checks: `.github/workflows/pr-check.yml`
- Release publish: `.github/workflows/release.yml`
- Release workflow builds website and PDF artifacts, uploads PDF to GitHub release, and deploys `_site/` to `gh-pages`.

## Key Documents

- `IMPLEMENTATION_PLAN.md`
- `RELEASE.md`
