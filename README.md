# IPBES Data Management Vision

Living-document implementation of the **IPBES Data Management Vision**, built with Quarto and R and published as a website and a versioned PDF with a Zenodo DOI per release.

- Source repo: <https://github.com/IPBES-Data/IPBES_Data_Vision>
- Website: <https://ipbes-data.github.io/IPBES_Data_Vision/>
- **Admin panel** (import/export Google Doc, pre-releases, releases): <https://ipbes-data.github.io/IPBES_Data_Vision/admin/>, source `admin.qmd` (`make admin` renders it locally), which also documents the one-time setup.

## Where things are

- `_content.md`: the text of the Vision. The Google Doc import overwrites it.
- `IPBES_Data_Vision.qmd`: frontmatter (title, editors, contact, Zenodo settings), release metadata, citation; includes `_content.md`.
- Version, release date, release notes and DOI are not stored in the source; they come from the release form and are added at build time.
- `scripts/release.py`: builds and releases (Zenodo). `scripts/gdoc.py`: Google Doc import/export. Both use the Python standard library only.

## Build locally

Requirements: R (`rmarkdown`, `knitr`), Quarto, TinyTeX, Python 3.

- `make preview`: live preview while editing
- `make build`: render the website into `_site/` and the PDF into `build/`, marked as an unreleased draft
- `make clean`: remove rendered output

## Workflows (all started from the admin panel)

| Workflow | Result |
|---|---|
| Import text from Google Doc | Pull request with the new text, title and editors |
| Export text to Google Doc | Creates a new Google Doc in your Drive with the current text and bibliographic tables |
| Number accepted text changes (beta) | Runs on every change to the text on `main`: tags the next beta, e.g. `v1.1-beta.3` |
| Make a release or pre-release | Pre-release: next release candidate, e.g. `v1.1-rc.2`, PDF on the GitHub pre-release, site at `/preview/`, no DOI. Release: the latest candidate unchanged becomes `v1.1`; DOI reserved, Zenodo draft filled, nothing public yet. Version rules: `admin.qmd` |
| Publish release | Zenodo draft published (DOI minted), site deployed |
| Check website and PDF build | Runs on every pull request; the rendered site and PDF are downloadable |
