# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
make preview   # quarto preview of IPBES_Data_Vision.qmd
make build     # python3 scripts/release.py build → _site/ + build/*-draft.pdf (version "draft", no DOI)
make admin     # admin panel → _site/admin/index.html (one self-contained file)
make clean
python3 scripts/release.py prepare --prerelease --notes "a; b"   # next release candidate build, no Zenodo
python3 scripts/versions.py status   # current version state from the tags
python3 scripts/test_versions.py     # checks the version rules (also run by CI)
python3 scripts/check_setup.py       # setup check (secrets/variables in env); the panel's Check setup button runs it
```

CI (`pr-check.yml`) runs `test_versions.py` and checks that `release.py build` renders. `release.py prepare` without `--prerelease`, `release.py publish` and everything in `scripts/gdoc.py` except local conversion talk to Zenodo or Google; never run them against production Zenodo (`ZENODO_TARGET=production`) without being asked.

Requirements: Quarto (bundles Pandoc), TinyTeX (LuaLaTeX; `quarto install tinytex`), Python 3 (stdlib only; `gdoc.py` uses Google's REST APIs directly).

## Architecture

- The text lives in `_content.md`, included by `IPBES_Data_Vision.qmd`, whose frontmatter holds `title`, `produced_by`, `publisher`, `contact_email`, `editors` and a `zenodo:` block (`concept_doi`, `sandbox_concept_doi`, `access_right`, `license`). Version, release date, release notes and DOI are never stored; they come from the release form.
- `scripts/release.py` is the only build entry point. `render()` passes `version`, `release_date`, `release_year`, `doi`, `prerelease` as `-M key=value` to `templates/title.tex`, and `write_includes()` turns them (plus the frontmatter, read via Pandoc's `$meta-json$`) into `_generated/front.md` (website banner and version card, PDF metadata pages), `citation.md` and `concept.md`, which the `.qmd` files include. There is no R: the documents contain no code chunks. `prepare` writes `build/release.json` for the workflows.
- Versions are git tags only (rules in `admin.qmd`, logic in `scripts/versions.py`): `vX.Y-beta.N` per accepted text change (`beta.yml`, paths = `TEXT_PATHS`), `vX.Y-rc.N` per pre-release, where X.Y = `next_version` from the frontmatter if it is the next minor/major, else the next minor (`next_version` is chosen in the export form, travels as the Doc's *Version* row and comes back with the import), `vX.Y` = latest rc promoted only if `TEXT_PATHS` are unchanged since it, `vX.Y-test.N` for sandbox releases (ignored). No version is typed anywhere; workflows that read tags check out with `fetch-depth: 0`.
- All admin workflows are `workflow_dispatch` forms linked from `admin.qmd` (the admin panel: rendered standalone with `embed-resources` by `make admin` and deployed to `gh-pages:/admin/` by `admin-panel.yml` on every change to it on main; not part of the site render list; shows live status via the public GitHub API). `release.yml` builds and creates the GitHub release itself (a release created with `GITHUB_TOKEN` would not trigger another workflow); a release reserves a DOI via Zenodo `newversion` and attaches `site.tar.gz` + `release.json`; `publish.yml` mints the draft and deploys that site to the `gh-pages` root (production target only), carrying over `/admin/` and `/versions/` from the current `gh-pages` (the preview is dropped) and adding the release's own copy at `versions/<version>/`. Pre-releases deploy to `gh-pages:/preview/` and to `gh-pages:/versions/<version>/` (permanent; linked from All versions and from the PDF watermark, which `render()` sets via `-M web_url`/`watermark`), and are archived as GitHub release assets.
- Zenodo sandbox pre-reserves DOIs with the production prefix `10.5281`; `Zenodo.doi()` rewrites them to `10.5072`, which is what the sandbox mints.
- `scripts/gdoc.py`: import = Drive export as docx → Pandoc JSON AST (`--shift-heading-level-by=1`). Blocks before the first non-"contents" heading are front matter: a "Document information" table (rows in `FIELDS` → frontmatter keys) and an "Editors" table (`Name | Institution | ORCID`), validated with a clear error list; the rest goes back through Pandoc to Markdown, typed heading numbers stripped. Export uploads the same layout as a new Google Doc (Drive converts the .docx) and `stamp()`s the previous export (`PREVIOUS_EXPORT`, from `gh-pages:admin/latest-export.json`): a highlighted notice inserted via the Docs API, then a Drive content-restriction lock, then `archive()` moves it into a sibling folder `archive` (created if missing; Drive API only, so it works even if the Docs API is off); the import workflow stamps the imported Doc the same way after opening the PR. Auth is OAuth as a user (`GOOGLE_OAUTH` = client id/secret + refresh token from `gdoc.py login`, loopback redirect), so files are owned by that user. Export → import round-trips `_content.md` and the frontmatter unchanged.
- Site chrome: `_quarto.yml` navbar (The Vision / All versions / Pre-release / Download PDF, pinned; `nav-links.html` hides the PDF and Pre-release buttons where their target does not exist) and footer, `styles.css`. The Vision page shows, on the website only, a status banner (release / pre-release / draft) and an "About this version" card from `_generated/front.md`; the PDF keeps its Release Metadata page. `v1.0.qmd` is the page for version 1.0; its text is `versions/v1.0.md`, converted from Appendix III of IPBES/9/INF/14 with the four wording differences to the Zenodo PDF applied (checked word by word against `IPBES_Data_Vision_org.pdf`); until 2.0 is published the main site's `index.html` is a copy of it.
- `older-releases.qmd` lists releases (Zenodo API) and pre-releases (GitHub API) client-side, so it stays current without re-rendering.
- Update `admin.qmd` and `README.md` when the workflow changes.
