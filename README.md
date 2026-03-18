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
  - `concept_doi`
  - `contact_email`
  - `release_notes`
  - `editors`

The same frontmatter metadata drives HTML metadata display and PDF title pages/citation content. The version DOI is injected at release time via `IPBES_DOI`; when missing, outputs show `**Will be inserted upon release**`.

## Build

Requirements:

- R
- Quarto
- TinyTeX (for PDF builds)

Commands:

- `make build-index`
  - Render `_site/index.html`
- `make build-older-release`
  - Render `_site/older-releases.html`
- `make build-release-doc`
  - Render hidden `_site/release.html`
- `make build-setup-doc`
  - Render hidden `_site/setup.html`
- `make build-help-admin-doc`
  - Render hidden `_site/help_admin.html`
- `make build-pdf`
  - Build versioned PDF from frontmatter version into `build/`
  - Update `_site/assets/IPBES-Data-Management-Vision-latest.pdf`
- `make build`
  - Run all targets above (public pages, hidden docs, and latest PDF)

## Output Structure

- Published website output: `_site/`
- Current page: `_site/index.html`
- All releases page: `_site/older-releases.html`
- Hidden admin docs:
  - `_site/release.html`
  - `_site/setup.html`
  - `_site/help_admin.html`
- Latest PDF alias: `_site/assets/IPBES-Data-Management-Vision-latest.pdf`
- Transient local PDF build artifact: `build/IPBES-Data-Management-Vision-<version>.pdf`

## All Releases Behavior

- `older-releases.qmd` queries Zenodo records using `concept_doi` from `IPBES_Data_Vision.qmd`.
- It lists available versions with version DOI plus Zenodo download/record links.
- No local `releases/` folder is used or published.

## Release Workflow (GitHub)

- PR checks: `.github/workflows/pr-check.yml`
- Release publish: `.github/workflows/release.yml`
- Release workflow reserves a Zenodo version DOI before rendering, injects it via `IPBES_DOI`, appends the DOI to GitHub release notes, builds website/PDF artifacts, uploads the PDF to the release, and deploys `_site/` to `gh-pages`.
- Required release secrets/variables:
  - `ZENODO_TARGET` (repository variable: `sandbox` or `production`; defaults to `production` if unset/invalid)
  - `ZENODO_API_BASE` (repository variable: production API base URL)
  - `ZENODO_SANDBOX_API_BASE` (repository variable: sandbox API base URL)
  - `ZENODO_TOKEN` (secret used when `ZENODO_TARGET=production`)
  - `ZENODO_SANDBOX_TOKEN` (secret used when `ZENODO_TARGET=sandbox`)
- Switch environments by changing only `ZENODO_TARGET`.
- Release workflow reads `version` and `concept_doi` from `IPBES_Data_Vision.qmd` frontmatter and derives Zenodo concept record id from `concept_doi`.

## Key Documents

- `IMPLEMENTATION_PLAN.md`
- `RELEASE.qmd`
- `setup.qmd`
- `help_admin.qmd`
