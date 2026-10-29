# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make preview   # quarto preview of IPBES_Data_Vision.qmd
make build     # python3 scripts/release.py build → _site/ + build/*.pdf (version "<v>-draft", no DOI)
make clean
python3 scripts/release.py prepare --tag v1.2-rc.1 --prerelease   # pre-release build, no Zenodo
```

There is no test suite; CI (`pr-check.yml`) checks that `release.py build` renders. `release.py prepare` without `--prerelease` and `release.py publish` talk to Zenodo; never run them against production (`ZENODO_TARGET=production`) without being asked.

Requirements: R (`rmarkdown`, `knitr`; `jsonlite` comes with them), Quarto, TinyTeX (LuaLaTeX), Python 3 (stdlib only).

## Architecture

- `IPBES_Data_Vision.qmd` is the single source: content plus frontmatter metadata (`version`, `release_notes`, `editors`, `contact_email`, and a `zenodo:` block with `concept_doi`, `sandbox_concept_doi`, `access_right`, `license`). Release date and version DOI are never stored; they are injected at build time.
- `scripts/release.py` is the only build entry point. `render()` passes `version`, `release_date`, `release_year`, `doi`, `prerelease` twice: as `-M key=value` for Pandoc templates (`templates/title.tex`, `{{< meta >}}`) and as `IPBES_<KEY>` env vars for the R chunks, because `-M` does not reach `rmarkdown::metadata`.
- Releases are driven by GitHub releases (`release.yml`): a pre-release tag `v<version>-<suffix>` builds without DOI and deploys to `gh-pages:/preview/`; a release tag must equal `v<version>`, reserves a DOI via Zenodo `newversion` on the latest record of the concept, fills the draft (metadata + PDF) and attaches `site.tar.gz` + `release.json` to the release. `publish.yml` (manual) mints the draft and deploys that site to the `gh-pages` root (production target only).
- Zenodo sandbox pre-reserves DOIs with the production prefix `10.5281`; `Zenodo.doi()` rewrites them to `10.5072`, which is what the sandbox mints.
- `older-releases.qmd` lists releases (Zenodo records API) and pre-releases (GitHub Releases API, `prerelease: true`) client-side with browser `fetch`, so it is always current without re-rendering. Pre-releases are archived only as GitHub release assets, never on Zenodo.
- `admin.qmd` is the maintainer guide (published, unlinked). Update it and `README.md` when the workflow changes.
