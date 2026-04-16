# IMPLEMENTATION_PLAN.md

## 1. Purpose

This repository implements the **IPBES Data Management Vision** as a single-source living document with reproducible HTML/PDF publishing.

Implementation goals:

1. Keep one authoritative source document.
2. Keep release metadata in one place (frontmatter).
3. Publish website pages + PDF outputs consistently.
4. Preserve older PDF releases for traceability via Zenodo.

Authoritative repository:
- https://github.com/IPBES-Data/IPBES_Data_Vision

Public website:
- https://ipbes-data.github.io/IPBES_Data_Vision/

## 2. Current Design (Implemented)

1. **Single source content**
   - `IPBES_Data_Vision.qmd` is the canonical source for the living document.

2. **Frontmatter as metadata authority**
   - Release identity and publication metadata are defined in YAML frontmatter of `IPBES_Data_Vision.qmd`.
   - No YAML track files or external metadata generation layer.

3. **Quarto website output**
   - `_quarto.yml` defines site rendering for:
     - `IPBES_Data_Vision.qmd` (published as `index.html`)
     - `older-releases.qmd` (published as `older-releases.html`)

4. **PDF title pages via Pandoc template partial**
   - `templates/title.tex` reads metadata directly from frontmatter (`title`, `version`, `release_date`, `doi`, `editors`, `contact_email`).
   - No hardcoded version/date macros in source body.

5. **No local PDF archive**
   - Versioned PDFs are not committed to the repository.
   - The release workflow generates PDFs on demand and uploads them to GitHub release assets and Zenodo.
   - `older-releases.qmd` queries Zenodo live using `concept_doi` from the main document's frontmatter.
   - Latest alias is `_site/assets/IPBES-Data-Management-Vision-latest.pdf`.

## 3. Repository Structure

```text
/
  IPBES_Data_Vision.qmd          # Living document source + release metadata
  older-releases.qmd             # Archive page (queries Zenodo live)
  templates/title.tex            # PDF title-page partial (frontmatter-driven)
  _quarto.yml                    # Quarto website configuration
  Makefile                       # Local build commands
  .github/workflows/             # CI/CD workflows
  README.md
  IMPLEMENTATION_PLAN.md
```

## 4. Required Frontmatter Metadata

Required in `IPBES_Data_Vision.qmd`:

1. `title`
2. `version`
3. `release_date`
4. `concept_doi`
5. `contact_email`
6. `release_notes`
7. `editors` (list with name/institution/orcid)

## 5. Build and Publication Flow

### 5.1 Local

1. `make build`
   - Render all website HTML into `_site/`.

2. `make build-pdf`
   - Read `version` from frontmatter.
   - Build `build/IPBES-Data-Management-Vision-v<version>.pdf`.
   - Copy to `_site/assets/IPBES-Data-Management-Vision-latest.pdf`.
   - Optionally inject DOI via `IPBES_DOI` env var.

### 5.2 CI/CD

1. PR checks workflow (`pr-check.yml`) validates buildability and artifact presence.
2. Release workflow (`release.yml`) triggers on GitHub Release published:
   - Resolves Zenodo target (`sandbox` vs `production`) via `ZENODO_TARGET` repo variable.
   - Reads `version` and `concept_doi` from frontmatter.
   - Reserves a new Zenodo version DOI via the Zenodo API.
   - Injects reserved DOI as `IPBES_DOI` at build time.
   - Appends DOI to GitHub release notes.
   - Builds website HTML and PDF artifact.
   - Uploads PDF to Zenodo draft (manual publish on Zenodo required to mint the DOI).
   - Uploads PDF to GitHub release assets.
   - Deploys `_site/` to `gh-pages` branch.

## 6. Older Releases Behavior

1. `older-releases.qmd` queries Zenodo live using `concept_doi` from `IPBES_Data_Vision.qmd` frontmatter.
2. It lists available versions with version DOI and Zenodo download/record links.
3. No local `releases/` folder is used or published.
4. If no releases exist on Zenodo, the page shows "No older released PDFs available yet."

## 7. Governance Rules

1. All source updates are made through git commits.
2. Metadata shown in outputs must come from frontmatter, not hardcoded strings.
3. Website and PDF outputs must remain reproducible from repository state.
4. `IMPLEMENTATION_PLAN.md` and `README.md` must be updated when architecture or workflow changes.

## 8. Release Simulation (Local)

To simulate a release locally:

1. Update frontmatter `version` (and `release_date`/`release_notes` if needed).
2. Run `IPBES_DOI=<doi> make build-pdf` (or omit `IPBES_DOI` to use the placeholder).
3. Check `_site/assets/IPBES-Data-Management-Vision-latest.pdf` for the generated artifact.

## 9. Risks and Constraints

1. If Zenodo has no records for the `concept_doi`, the archive page shows no entries by design.
2. If frontmatter metadata is incomplete, rendered PDF citation/header content can degrade.
3. Quarto rebuilds `_site` from scratch; the `_site/assets/` copy must happen after render.
4. Zenodo draft is not auto-published; DOI minting requires a manual publish step on Zenodo.

## 10. Plan Change Log

- 2026-04-16: Updated to match current implemented architecture.
  - Removed outdated `releases/` local folder references.
  - Documented Zenodo live query approach for `older-releases.qmd`.
  - Aligned build flow with current `Makefile`, CI workflows, and README.
- 2026-03-18: Plan rewritten to match implemented single-source living-document architecture.
  - Removed YAML track-layer assumptions.
  - Documented frontmatter-driven PDF title pages.
