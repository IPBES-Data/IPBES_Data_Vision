# IMPLEMENTATION_PLAN.md

## 1. Purpose and Scope

This document defines how the **IPBES Data Management Vision** is implemented as a living, versioned, and citable publication.

The implementation objective is to:

1. Track all document changes transparently.
2. Publish a website and downloadable PDF for each release.
3. Mint a DOI for each released version.
4. Keep the stack backend-agnostic and based on open standards/tools.

Authoritative repository:
- https://github.com/IPBES-Data/IPBES_Data_Vision

Public website:
- https://ipbes-data.github.io/IPBES_Data_Vision/

## 2. Guiding Principles (Design Decisions)

1. **Git as source of truth**
   - Decision: All edits, review history, and release snapshots are managed in git.
   - Rationale: Distributed, open source, robust audit trail.

2. **Markdown-first authoring**
   - Decision: Maintain content in plain text (`.md`) and lightweight metadata files.
   - Rationale: Tool-independent, easy diff/review, future portable.

3. **GitHub as collaboration and publication interface**
   - Decision: Use GitHub issues/PRs/releases/actions/pages.
   - Rationale: Strong workflow support and integration with Zenodo.

4. **Automated release artifacts**
   - Decision: Each release automatically produces website output + PDF artifact.
   - Rationale: Repeatability, reduced manual errors.

5. **DOI per release via Zenodo**
   - Decision: Use GitHub release integration with Zenodo to mint DOIs.
   - Rationale: Stable citation for each version.

6. **Visible release metadata in all published versions**
   - Decision: Every published document state must show Version, Release Date, DOI.
   - Rationale: Unambiguous citation and provenance.

7. **Timeline access to prior versions**
   - Decision: Website includes a timeline/archive linking historical releases.
   - Rationale: Traceability and historical transparency.

8. **Backend-agnostic architecture**
   - Decision: Avoid lock-in to proprietary authoring platforms; keep source and build process open.
   - Rationale: Long-term sustainability independent of large software vendors.

## 3. Target System Architecture

### 3.1 Components

1. **Git repository**
   - Stores source documents, metadata, workflow definitions, and built history references.

2. **GitHub repository**
   - Hosts collaboration (PRs, issues), release tags, release notes, and action pipelines.

3. **GitHub Actions CI/CD**
   - Builds HTML website and PDF on release events.
   - Deploys website files to the dedicated `gh-pages` branch for GitHub Pages.
   - Publishes/attaches release assets (PDF, optional checksums, manifests).

4. **GitHub Pages**
   - Serves current and historical release pages.

5. **Zenodo integration**
   - Mints DOI for each GitHub release and stores archive snapshot.

### 3.2 Data/Release Flow

1. Change proposed via branch + pull request.
2. Review + merge to default branch.
3. Release tag created (e.g., `v1.0.0`).
4. GitHub Action runs release pipeline.
5. Website and PDF generated from tagged source.
6. Website updated (current + timeline entry).
7. PDF attached to GitHub release.
8. Zenodo mints DOI for the release.
9. Release metadata (Version, Date, DOI) rendered in published outputs.

## 4. Repository and Content Model

### 4.1 Proposed Top-Level Structure

```text
/
  docs/                      # Source content (markdown)
  site/                      # Temporary release build output (not committed to main)
  scripts/                   # Build/deploy helper scripts
  .github/workflows/         # CI/CD pipelines
  releases/                  # Generated release metadata/index
  IMPLEMENTATION_PLAN.md     # This document
  CHANGELOG.md               # Human-readable release summary
  README.md                  # Project entry and contribution links
```

### 4.2 Required Release Metadata

For every released version, define at minimum:

1. `version` (string, tag-aligned)
2. `release_date` (ISO date: YYYY-MM-DD)
3. `doi` (full DOI string)
4. `doi_url` (resolver URL, e.g. `https://doi.org/...`)
5. `release_notes_url`
6. `pdf_url`

Recommended: maintain these in a machine-readable registry (e.g., `releases/index.json` or `releases/index.yml`) used by the timeline page.

## 5. Versioning and Release Policy

1. **Versioning scheme**
   - Preferred: semantic tags (`vMAJOR.MINOR.PATCH`) unless governance selects calendar versions.

2. **Release trigger**
   - Releases are created only from reviewed and merged default-branch commits.

3. **Release immutability**
   - Published release artifacts and metadata are never overwritten; corrections use a new version.

4. **Citation rule**
   - Citations must include document title, version, date, DOI.

## 6. Governance and Change Control

1. All substantive edits via pull request.
2. At least one reviewer required before merge.
3. Document decisions in PR description and/or linked issue.
4. Tag maintainers responsible for release approval.
5. This `IMPLEMENTATION_PLAN.md` is itself a living governance artifact and must be updated whenever architecture/process decisions change.

## 7. CI/CD and Publication Requirements

### 7.1 Release Pipeline (minimum)

1. Validate source consistency.
2. Build website output.
3. Build PDF output.
4. Inject/render release metadata (version/date/DOI).
5. Deploy website files to the `gh-pages` branch.
6. Attach PDF to GitHub release.
7. Emit/update timeline data entry.

### 7.2 Quality Gates

1. Build fails on missing release metadata.
2. Build fails if PDF generation fails.
3. Build fails if timeline metadata entry is invalid.
4. Optional checksum creation for PDF artifacts.

## 8. Website Requirements

1. Home page for current **IPBES Data Management Vision** version.
2. Timeline/archive page listing all releases.
3. Each release entry includes:
   - Version
   - Release date
   - DOI link
   - HTML view link
   - PDF download link
4. Clear distinction between “current version” and “archived versions”.

## 9. DOI / Zenodo Requirements

1. Configure Zenodo-GitHub integration for `IPBES_Data_Vision`.
2. Ensure GitHub releases are used (not only tags), so metadata and assets are explicit.
3. Ensure citation metadata is complete and consistent across:
   - GitHub release notes
   - Zenodo record
   - Published document headers/footers
4. Keep project-level concept DOI and version-specific DOIs clearly distinguished where applicable.

## 10. Security, Portability, and Sustainability

1. Keep source in open text formats.
2. Keep automation definitions in repository (`.github/workflows`).
3. Avoid proprietary dependencies where open alternatives exist.
4. Consider periodic mirror of repository to an additional forge for continuity.

## 11. Operational Runbook (Release Checklist)

Pre-release:
1. Confirm all planned changes are merged.
2. Confirm metadata for new version is prepared.
3. Confirm changelog entry exists.

Release:
1. Create release tag/version.
2. Publish GitHub release with notes.
3. Verify CI workflow success.
4. Verify website update and PDF artifact availability.
5. Verify Zenodo DOI minting and DOI resolution.

Post-release:
1. Verify timeline entry correctness.
2. Verify document header/footer metadata.
3. Communicate release links (site + DOI + PDF).

## 12. Risks and Mitigations

1. **CI pipeline drift**
   - Mitigation: keep workflow files versioned and periodically tested.

2. **DOI minting failure**
   - Mitigation: release checklist step for Zenodo verification and retry process.

3. **Metadata inconsistency across outputs**
   - Mitigation: single metadata source consumed by all renderers.

4. **Platform dependency concerns**
   - Mitigation: plain-text sources + portable build scripts + optional mirror strategy.

## 13. Open Decisions (To Be Confirmed)

1. Final versioning convention (`vMAJOR.MINOR.PATCH` vs calendar-based).
2. Exact static site and PDF toolchain.
3. Required reviewer count and governance roles.
4. Whether to include signed release tags.

## 14. Change Log for This Plan

- 2026-03-04: Initial draft created.
  - Established architecture and governance baseline.
  - Defined release metadata requirements.
  - Defined release workflow and timeline requirements.
  - Added risks, mitigations, and open decisions.
- 2026-03-04: Initial automation scaffolding implemented.
  - Added Quarto source file `IPBES_Data_Vision.qmd`.
  - Added pull-request checks workflow (`.github/workflows/pr-check.yml`).
  - Added release publish workflow (`.github/workflows/release.yml`).
  - Added R build script (`scripts/build.R`) and timeline page (`timeline.qmd`).
- 2026-03-04: Deployment strategy updated.
  - Switched release deployment to dedicated `gh-pages` branch.
  - Clarified that `site/` is temporary build output, not main-branch content.

---

## Appendix A: Minimal Metadata Example

```yaml
version: v1.0.0
release_date: 2026-03-04
doi: 10.5281/zenodo.1234567
doi_url: https://doi.org/10.5281/zenodo.1234567
release_notes_url: https://github.com/IPBES-Data/IPBES_Data_Vision/releases/tag/v1.0.0
pdf_url: https://github.com/IPBES-Data/IPBES_Data_Vision/releases/download/v1.0.0/IPBES-Data-Management-Vision-v1.0.0.pdf
```
