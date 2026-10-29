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
```

CI (`pr-check.yml`) runs `test_versions.py` and checks that `release.py build` renders. `release.py prepare` without `--prerelease`, `release.py publish` and everything in `scripts/gdoc.py` except local conversion talk to Zenodo or Google; never run them against production Zenodo (`ZENODO_TARGET=production`) without being asked.

Requirements: Quarto (bundles Pandoc), TinyTeX (LuaLaTeX; `quarto install tinytex`), Python 3 (stdlib only; `gdoc.py` uses Google's REST APIs directly).

## Architecture

- The text lives in `_content.md`, included by `IPBES_Data_Vision.qmd`, whose frontmatter holds `title`, `produced_by`, `publisher`, `contact_email`, `editors` and a `zenodo:` block (`concept_doi`, `sandbox_concept_doi`, `access_right`, `license`). Version, release date, release notes and DOI are never stored; they come from the release form.
- `scripts/release.py` is the only build entry point. `render()` passes `version`, `release_date`, `release_year`, `doi`, `prerelease` as `-M key=value` to `templates/title.tex`, and `write_includes()` turns them (plus the frontmatter, read via Pandoc's `$meta-json$`) into `_generated/front.md` (website banner and version card, PDF metadata pages), `citation.md` and `concept.md`, which the `.qmd` files include. There is no R: the documents contain no code chunks. `prepare` writes `build/release.json` for the workflows.
- Versions are git tags only (rules in `admin.qmd`, logic in `scripts/versions.py`): `vX.Y-beta.N` per accepted text change (`beta.yml`, paths = `TEXT_PATHS`), `vX.Y-rc.N` per pre-release, where X.Y = `next_version` from the frontmatter if it is the next minor/major, else the next minor (`next_version` is chosen in the export form, travels as the Doc's *Version* row and comes back with the import), `vX.Y` = latest rc promoted only if `TEXT_PATHS` are unchanged since it, `vX.Y-test.N` for sandbox releases (ignored). No version is typed anywhere; workflows that read tags check out with `fetch-depth: 0`.
- All admin workflows are `workflow_dispatch` forms linked from `admin.qmd` (the admin panel: rendered standalone with `embed-resources` by `make admin` and deployed to `gh-pages:/admin/` by `admin-panel.yml` on every change to it on main; not part of the site render list; shows live status via the public GitHub API). `release.yml` builds and creates the GitHub release itself (a release created with `GITHUB_TOKEN` would not trigger another workflow); a release reserves a DOI via Zenodo `newversion` and attaches `site.tar.gz` + `release.json`; `publish.yml` mints the draft and deploys that site to the `gh-pages` root (production target only), carrying over `/admin/` and `/preview/` from the current `gh-pages`. Pre-releases deploy to `gh-pages:/preview/` and are archived only as GitHub release assets.
- Zenodo sandbox pre-reserves DOIs with the production prefix `10.5281`; `Zenodo.doi()` rewrites them to `10.5072`, which is what the sandbox mints.
- `scripts/gdoc.py`: import = Drive export as docx → Pandoc JSON AST (`--shift-heading-level-by=1`). Blocks before the first non-"contents" heading are front matter: a "Document information" table (rows in `FIELDS` → frontmatter keys) and an "Editors" table (`Name | Institution | ORCID`), validated with a clear error list; the rest goes back through Pandoc to Markdown, typed heading numbers stripped. Export uploads the same layout as a new Google Doc (Drive converts the .docx). Auth is OAuth as a user (`GOOGLE_OAUTH` = client id/secret + refresh token from `gdoc.py login`, loopback redirect), so files are owned by that user. Export → import round-trips `_content.md` and the frontmatter unchanged.
- Site chrome: `_quarto.yml` navbar (The Vision / All versions / Download PDF; `pdf-link.html` hides the PDF button where no PDF exists) and footer, `styles.css`. The Vision page shows, on the website only, a status banner (release / pre-release / draft) and an "About this version" card built in its first R chunk; the PDF keeps its Release Metadata page. `v1.0.qmd` is a static page for version 1.0 (text only on Zenodo); until 2.0 is published the main site's `index.html` is a copy of it.
- `older-releases.qmd` lists releases (Zenodo API) and pre-releases (GitHub API) client-side, so it stays current without re-rendering.
- Update `admin.qmd` and `README.md` when the workflow changes.
