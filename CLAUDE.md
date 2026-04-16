# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build Commands

```bash
make build-index          # Render IPBES_Data_Vision.qmd → _site/index.html
make build-older-release  # Render older-releases.qmd → _site/older-releases.html
make build-pdf            # Render versioned PDF → build/ and _site/assets/...-latest.pdf
make build                # Run all targets (HTML pages + PDF)
make clean                # Remove _site/, build/, and LaTeX temp files
```

PDF build accepts an optional injected DOI:
```bash
IPBES_DOI="10.5281/zenodo.XXXXXXX" make build-pdf
```

Local requirements: R, Quarto, TinyTeX.

## Architecture

### Single Source of Truth

`IPBES_Data_Vision.qmd` is the canonical source for both content and release metadata. Its YAML frontmatter drives everything — HTML subtitle, PDF title page, Zenodo DOI reservation, and the release workflow. Required frontmatter fields:

- `title`, `version`, `release_date`, `concept_doi`, `contact_email`, `release_notes`, `editors`

When `IPBES_DOI` env var is absent, outputs show `"Will be inserted upon release"` as a placeholder.

### PDF Title Page

`templates/title.tex` is a Pandoc template partial referenced from the frontmatter (`template-partials`). It reads metadata fields directly from frontmatter — nothing is hardcoded. The `pdf` format is only rendered when `IPBES_BUILD_PDF=true` is set (to avoid slow PDF builds during HTML-only development).

### Older Releases Page

`older-releases.qmd` queries Zenodo live using `concept_doi` from the main document's frontmatter. It does **not** read a local `releases/` folder or any committed PDFs.

### CI/CD Workflows

**`pr-check.yml`** — validates that HTML and PDF build cleanly; runs on PRs to `main`. Injects `IPBES_VERSION=pr-<#>`, `IPBES_BUILD_PDF=true`, `IPBES_DOI=PENDING`.

**`release.yml`** — triggered on GitHub Release published. Pipeline:
1. Resolves Zenodo target (`sandbox` vs `production`) via `ZENODO_TARGET` repo variable
2. Reads `version` and `concept_doi` from frontmatter via Rscript
3. Reserves a new Zenodo version DOI via the Zenodo API (Python/urllib, no third-party libraries)
4. Injects the reserved DOI as `IPBES_DOI` env var for the build
5. Appends the DOI to the GitHub release notes
6. Builds HTML website and PDF artifact
7. Uploads PDF to Zenodo draft (as draft — requires manual publish on Zenodo)
8. Uploads PDF to GitHub release assets
9. Deploys `_site/` to `gh-pages` branch

### Zenodo Environment Switching

Switch between sandbox and production by changing the `ZENODO_TARGET` repository variable (`sandbox` | `production`). Each target has its own API base URL variable and token secret:

| Target     | URL variable              | Token secret           |
|------------|---------------------------|------------------------|
| production | `ZENODO_API_BASE`         | `ZENODO_TOKEN`         |
| sandbox    | `ZENODO_SANDBOX_API_BASE` | `ZENODO_SANDBOX_TOKEN` |

### Governance Rules

- Metadata in outputs must always come from frontmatter, never hardcoded.
- `IMPLEMENTATION_PLAN.md` and `README.md` must be updated when architecture or workflow changes.
- All Zenodo API calls in CI use Python stdlib only (no `requests`, no extra dependencies).
