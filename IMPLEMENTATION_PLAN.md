# IMPLEMENTATION_PLAN.md

## 1. Purpose

This repository implements the **IPBES Data Management Vision** as a single-source living document with reproducible HTML/PDF publishing.

Implementation goals:

1. Keep one authoritative source document.
2. Keep release metadata in one place (frontmatter).
3. Publish website pages + PDF outputs consistently.
4. Preserve older PDF releases for traceability.

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

5. **Persistent local PDF archive**
   - Versioned PDFs are generated into `releases/`.
   - Website publishing copy is synced to `_site/releases/`.
   - Latest alias is `_site/assets/IPBES-Data-Management-Vision-latest.pdf`.

## 3. Repository Structure

```text
/
  IPBES_Data_Vision.qmd          # Living document source + release metadata
  older-releases.qmd             # Archive page
  templates/title.tex            # PDF title-page partial (frontmatter-driven)
  _quarto.yml                    # Quarto website configuration
  Makefile                       # Local build commands
  releases/                      # Persistent local archive of versioned PDFs
  .github/workflows/             # CI/CD workflows
  README.md
  RELEASE.md
  IMPLEMENTATION_PLAN.md
```

## 4. Required Frontmatter Metadata

Required in `IPBES_Data_Vision.qmd`:

1. `title`
2. `version`
3. `release_date`
4. `doi`
5. `contact_email`
6. `release_notes`
7. `editors` (list with name/institution/orcid)

## 5. Build and Publication Flow

### 5.1 Local

1. `make build`
   - Render website HTML into `_site/`.
   - Sync existing archive PDFs from `releases/` to `_site/releases/`.

2. `make build-pdf`
   - Read `version` from frontmatter.
   - Build `releases/IPBES-Data-Management-Vision-v<version>.pdf`.
   - Render website HTML to `_site/`.
   - Sync `releases/*.pdf` to `_site/releases/`.
   - Copy current release to `_site/assets/IPBES-Data-Management-Vision-latest.pdf`.

### 5.2 CI/CD

1. PR checks workflow validates buildability and artifact presence.
2. Release workflow builds website + PDF artifact and deploys `_site/` to `gh-pages`.
3. Release workflow uploads the versioned PDF to GitHub release assets.

## 6. Older Releases Behavior

1. `older-releases.qmd` reads archive files from `releases/`.
2. It lists PDFs matching `IPBES-Data-Management-Vision-v*.pdf`.
3. The currently active version is excluded from the table.
4. Result: if only one version exists, “No older released PDFs available yet.” is expected.

## 7. Governance Rules

1. All source updates are made through git commits.
2. Metadata shown in outputs must come from frontmatter, not hardcoded PDF strings.
3. Website and PDF outputs must remain reproducible from repository state.
4. `IMPLEMENTATION_PLAN.md` and `README.md` must be updated when architecture or workflow changes.

## 8. Release Simulation (Local)

To simulate sequential releases locally:

1. Update frontmatter `version` (and date/notes if needed).
2. Run `make build-pdf`.
3. Repeat with a new version.
4. Check `older-releases.html` for accumulated previous versions.

## 9. Risks and Constraints

1. If `releases/` is empty, archive page has no entries by design.
2. If frontmatter metadata is incomplete, rendered PDF citation/header content can degrade.
3. Quarto rebuilds `_site` from scratch; archive copies into `_site/releases/` must happen after render.

## 10. Plan Change Log

- 2026-03-18: Plan rewritten to match implemented single-source living-document architecture.
  - Removed YAML track-layer assumptions.
  - Documented frontmatter-driven PDF title pages.
  - Documented persistent `releases/` archive and `_site` publication sync.
  - Aligned build flow with current `Makefile` and Quarto website rendering.
