# IPBES Data Management Vision

Living-document implementation of the **IPBES Data Management Vision**, built with Quarto and R and published as a website and a versioned PDF with a Zenodo DOI per release.

- Source repo: <https://github.com/IPBES-Data/IPBES_Data_Vision>
- Website: <https://ipbes-data.github.io/IPBES_Data_Vision/>
- Maintainer guide (editing, pre-releases, releases, settings): `admin.qmd`, published as `admin.html`

## Source of truth

`IPBES_Data_Vision.qmd` holds the text and, in its YAML frontmatter, the metadata: `title`, `version`, `contact_email`, `release_notes`, `editors`, and the `zenodo` block (concept DOIs, access right, licence). The release date and the version DOI are not in the source; `scripts/release.py` adds them when a release is built.

## Build

Requirements: R (`rmarkdown`, `knitr`), Quarto, TinyTeX, Python 3.

- `make preview`: live preview while editing
- `make build`: render the website into `_site/` and the PDF into `build/`, marked as an unreleased draft
- `make clean`: remove rendered output

## Releases

| GitHub release | Tag | Result |
|---|---|---|
| Pre-release | `v1.2-rc.1` | PDF attached to the pre-release (archived there and listed on the All Releases page), site at `/preview/`, no DOI |
| Release | `v1.2` (must equal `v` + frontmatter `version`) | DOI reserved, Zenodo draft filled, PDF attached |
| *Publish release* workflow | `v1.2` | Zenodo draft published (DOI minted), site deployed |

Workflows: `.github/workflows/pr-check.yml`, `release.yml`, `publish.yml`. All build and Zenodo steps are in `scripts/release.py` (Python stdlib only). Details and required repository settings are in `admin.qmd`.
