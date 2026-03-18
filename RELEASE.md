# RELEASE.md

## 1. Purpose

This document defines the release process for the **IPBES Data Management Vision**.

The process is designed to be automated as far as possible. The primary trigger is a **GitHub Release** event.

## 2. Branch and Approval Model

1. Changes are proposed from a `dev` branch or a fork via pull request to `main`.
2. Pull request checks must pass (`.github/workflows/pr-check.yml`).
3. `main` must be branch-protected in GitHub settings.
4. Merge requires owner approval from the `IPBES-Data` organization (configured in branch protection).
5. After merge, a GitHub release is published for the target tag.
6. The release event triggers publication automation.

Primary trigger:

```yaml
on:
  release:
    types: [published]
```

GitHub-side settings required (not stored in repository files):

1. Enable branch protection for `main`.
2. Require pull request before merge.
3. Require at least one approval.
4. Restrict who can push to `main`.
5. Require status check `PR Checks`.
6. Configure GitHub Pages to serve from branch `gh-pages` (root).

## 3. What Is Automated

When a GitHub release is published, automation should:

1. Validate release metadata.
2. Build website output for the released version (index, older releases page).
3. Build PDF for the released version.
4. Publish website files to the dedicated `gh-pages` branch.
5. Attach PDF to the GitHub release.
6. Expose visible metadata in outputs: version, release date, DOI (or DOI pending marker).

## 4. Minimal Manual Actions

Manual work should be limited to:

1. Ensure content is merged into `main`.
2. Create and publish GitHub release with the intended tag.
3. Verify final outputs after automation completes.

Everything else should be handled by CI/CD.

Local build convention:

1. Local and CI builds use Quarto's default `_site/` output.
2. Release deployment publishes `_site/` content to `gh-pages`.

## 5. Inputs and Required Metadata

Expected release inputs:

1. `tag_name` from GitHub release (e.g., `v1.0.0`).
2. `published_at` from release payload.
3. DOI information from Zenodo (immediate or delayed).

Required metadata fields in published output:

1. `version`
2. `release_date`
3. `doi`
4. `doi_url`
5. `release_notes`
6. `pdf_url`

## 6. Workflow Design

Recommended workflow file:
- `.github/workflows/release.yml`

Recommended jobs:

1. `prepare`
   - Checkout tagged commit.
   - Read `github.event.release.tag_name` and `github.event.release.published_at`.
   - Create build metadata object.

2. `build_site`
   - Build static HTML output (`index.html`, `older-releases.html`).
   - Inject version and date metadata.

3. `build_pdf`
   - Build PDF from the same tagged source.
   - Name artifact with version (example: `IPBES-Data-Management-Vision-v1.0.0.pdf`).

4. `deploy_gh_pages`
   - Push generated site files to `gh-pages` (Pages source branch).

5. `attach_assets`
   - Upload PDF (and optional checksum) to GitHub release assets.

6. `final_checks`
   - Verify URL availability and required metadata presence in rendered outputs.

## 7. DOI Handling (Zenodo)

Zenodo DOI minting may occur after the GitHub release is already published.

To keep automation robust:

1. Release workflow should complete even if DOI is not yet available.
2. If DOI is missing, mark DOI as `PENDING` in generated metadata.
3. Run a follow-up sync workflow to resolve pending DOIs and refresh published metadata.

Recommended follow-up workflow:
- `.github/workflows/doi-sync.yml`

Trigger options:
1. `workflow_dispatch` for manual retry.
2. `schedule` (e.g., hourly) to backfill pending DOI records.

## 8. Failure Policy

The release workflow should fail for:

1. Build failure (site or PDF).
2. Missing required non-DOI metadata.
3. `gh-pages` deployment failure.
4. Release asset upload failure.

The release workflow should not fail for:

1. Temporary DOI unavailability from Zenodo, if pending state is handled.

## 9. Security and Permissions

Use least-privilege permissions in workflows.

Minimum required permissions for `release.yml`:

```yaml
permissions:
  contents: write
```

Notes:
1. `contents: write` is needed for uploading release assets.
2. `contents: write` is also used to push generated site files to `gh-pages`.

## 10. Verification Checklist

After each release:

1. GitHub Action run is green.
2. Website is updated at:
   - https://ipbes-data.github.io/IPBES_Data_Vision/
3. PDF asset is attached to the release.
4. Version and date are visible in HTML and PDF.
5. DOI is visible, or explicitly marked pending.
6. Timeline/archive includes the new release.

## 11. Future Hardening

1. Add signed release tags.
2. Add artifact checksum and signature files.
3. Add link checker for release/archive entries.
4. Add end-to-end release test in a staging branch.

## 12. Change Log (This Document)

- 2026-03-04: Initial release-process specification added.
  - Defined release-triggered automation model.
  - Defined workflow jobs and failure policy.
  - Added DOI asynchronous handling strategy.
