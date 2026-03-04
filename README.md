# IPBES Data Management Vision

Living-document implementation for the **IPBES Data Management Vision** using git, GitHub, Quarto, and R.

## Repository

- Source repo: <https://github.com/IPBES-Data/IPBES_Data_Vision>
- Website: <https://ipbes-data.github.io/IPBES_Data_Vision/>

## Local Build

Requirements:

- R
- Quarto
- TinyTeX (for PDF builds)

Commands:

- HTML only:
  - `make build`
- HTML + PDF:
  - `make build-pdf`

Outputs are written to `html/`:

- `html/index.html`
- `html/timeline.html`
- `html/releases/<version>.pdf` (when PDF enabled)
- `html/assets/IPBES-Data-Management-Vision-latest.pdf` (copy of current release PDF)

## Release Workflow (GitHub)

1. Changes are proposed from `dev` branch or fork via PR to `main`.
2. PR checks run (`.github/workflows/pr-check.yml`).
3. `main` is protected and requires owner approval.
4. After merge, publish a GitHub release tag.
5. Release workflow (`.github/workflows/release.yml`) builds site + PDF, uploads versioned PDF to the release, and deploys website content to `gh-pages`.

## Key Documents

- `IMPLEMENTATION_PLAN.md`
- `RELEASE.md`
