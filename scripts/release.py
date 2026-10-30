#!/usr/bin/env python3
"""Build and release the IPBES Data Management Vision (Python stdlib only).

  release.py build                                    render site + PDF as an unreleased draft
  release.py prepare --prerelease --notes           next release candidate, e.g. v1.1-rc.2: no DOI, no Zenodo
  release.py prepare --notes "a; b"                   release the latest candidate, e.g. v1.1-rc.2 -> v1.1:
                                                      reserve DOI, render, fill Zenodo draft (v1.1-test.<n> on sandbox)
  release.py publish build/release.json               publish (mint) the Zenodo draft from prepare

Version numbers follow the rules in admin.qmd and come from scripts/versions.py.
`prepare` writes build/release.json (tag, version, notes, DOI, Zenodo draft) for the workflows.

Zenodo is only contacted by `prepare` (release) and `publish`. The target comes from
ZENODO_TARGET (sandbox | production, required) with ZENODO_SANDBOX_TOKEN / ZENODO_TOKEN.
"""
import argparse
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import versions

QMD = "IPBES_Data_Vision.qmd"
PDF_PREFIX = "IPBES-Data-Management-Vision"
SITE = Path("_site")
BUILD = Path("build")
GENERATED = Path("_generated")
PUBLIC_SITE = "https://ipbes-data.github.io/IPBES_Data_Vision/"
REPOSITORY = "https://github.com/IPBES-Data/IPBES_Data_Vision"
NOTES_HEADING = "<h3>Release notes</h3>"
ZENODO = {
    "sandbox": ("https://sandbox.zenodo.org", "ZENODO_SANDBOX_TOKEN", "sandbox_concept_doi"),
    "production": ("https://zenodo.org", "ZENODO_TOKEN", "concept_doi"),
}


def frontmatter() -> dict:
    """The .qmd's YAML frontmatter, read by Pandoc (no YAML library in the stdlib)."""
    with tempfile.TemporaryDirectory() as tmp:
        template = Path(tmp, "meta.txt")
        template.write_text("$meta-json$")
        out = subprocess.run(["quarto", "pandoc", QMD, "-t", "plain", "--template", str(template)],
                             capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def write_includes(meta: dict, fm: dict) -> None:
    """Version-dependent parts of the pages, included by the .qmd files from _generated/:
    front.md (website banner and version card; PDF metadata pages), citation.md, concept.md."""
    e = html.escape
    version, notes = meta.get("version") or "draft", meta.get("release_notes") or "Not released yet."
    date, year = meta.get("release_date") or "unreleased", meta.get("release_year") or str(datetime.date.today().year)
    doi, pre, current = meta.get("doi", ""), bool(meta.get("prerelease")), meta.get("current_release") or "1.0"
    concept = fm["zenodo"]["concept_doi"]
    editors = ", ".join(x["name"] for x in fm.get("editors", []))
    doi_md = f"[{doi}](https://doi.org/{doi})" if doi else "None (pre-release)" if pre else "**Will be inserted upon release**"
    doi_html = f'<a href="https://doi.org/{doi}">{doi}</a>' if doi else "none (pre-release)" if pre else "none (draft)"
    current_link = f'<a href="https://doi.org/{concept}">version {current}</a>'
    if pre:
        label = "Beta" if "-beta." in version else "Pre-release"
        banner = ("prerelease", "exclamation-triangle", f"<b>{label} {version}</b> &middot; for review, not for "
                  f"citation &middot; the current released version is {current_link}")
    elif doi:
        banner = ("release", "check-circle", f"<b>Version {version}</b> &middot; released {date} &middot; "
                  f"cite it with DOI {doi_html}")
    else:
        banner = ("draft", "pencil", f"<b>Working draft</b> &middot; not released, no DOI &middot; the current "
                  f"released version is {current_link}")
    items = [line[2:] for line in notes.splitlines() if line.startswith("- ")]
    notes_html = "<ul>" + "".join(f"<li>{e(i)}</li>" for i in items) + "</ul>" if items else f"<p>{e(notes)}</p>"
    citation_md = f"IPBES ({year}): *{fm['title']}*, version {version}, {editors} (eds.). {fm['publisher']}. DOI: {doi_md}"
    citation_html = (f"IPBES ({year}): <i>{e(fm['title'])}</i>, version {e(version)}, {e(editors)} (eds.). "
                     f"{e(fm['publisher'])}. DOI: {doi_html}")

    web_line = ("" if version == "draft" else
                f'<p class="permalink">Permanent web version: <a href="{meta["web_url"]}">{meta["web_url"]}</a></p>')
    GENERATED.mkdir(exist_ok=True)
    (GENERATED / "front.md").write_text(f"""::: {{.content-visible when-format="html"}}
```{{=html}}
<div class="status-banner status-{banner[0]}"><i class="bi bi-{banner[1]}"></i><span>{banner[2]}</span></div>
<div class="version-card"><div class="facts">
<div><div class="label">Version</div>{e(version)}</div><div><div class="label">Date</div>{e(date)}</div>
<div><div class="label">DOI</div>{doi_html}</div><div><div class="label">Editors</div>{e(editors)}</div></div>
{web_line}<details><summary>Release notes</summary>{notes_html}</details>
<details><summary>How to cite</summary><p>{citation_html}</p></details></div>
<div class="vision-start"></div>
```
:::

::: {{.content-visible when-format="pdf"}}
\\newpage

## Release Metadata {{.unnumbered}}

- **Version:** {version}
- **Release date:** {date}
- **DOI:** {doi_md}
- **Latest-version DOI:** [{concept}](https://doi.org/{concept})
- **PDF:** Download the latest PDF from the website.

## Release Notes {{.unnumbered}}

{notes}

\\newpage
:::
""")
    (GENERATED / "citation.md").write_text(citation_md + "\n")
    (GENERATED / "concept.md").write_text(
        f"Citable versions with a DOI, read live from Zenodo. Concept DOI (always the latest version): "
        f"[{concept}](https://doi.org/{concept})\n\n"
        f'<div id="release-list" data-concept-doi="{concept}"><p>Loading releases from Zenodo&hellip;</p></div>\n')


def notes_markdown(notes: str) -> str:
    """'First change; second change' (from the release form) -> Markdown bullet list."""
    items = [item.strip() for item in re.split(r"[;\n]", notes or "") if item.strip()]
    return "\n".join(f"- {item}" for item in items) or "- No release notes given."


def render(meta: dict) -> Path:
    """Render the website and the PDF; meta goes to the templates (-M) and into _generated/ (write_includes)."""
    meta = {key: meta.get(key, "") for key in
            ("version", "release_date", "release_year", "doi", "prerelease", "release_notes",
             "current_release", "web_url", "watermark", "watermark_title")}
    meta["current_release"] = meta["current_release"] or versions.fmt(versions.latest_release(versions.tags()))
    # Every page of the PDF says where it comes from: the permanent web version of this version
    # (pre-releases and releases are kept at versions/<version>/), or the repository for drafts.
    if meta["version"] in ("", "draft"):
        meta["web_url"], meta["watermark_title"] = REPOSITORY, "Unpublished working draft"
        meta["watermark"] = f"Unpublished working draft after {versions.based_on(versions.tags())} · generated from"
    else:
        meta["web_url"], meta["watermark_title"] = f"{PUBLIC_SITE}versions/{meta['version']}/", f"Version {meta['version']}"
        meta["watermark"] = f"Version {meta['version']} · generated from"
    write_includes(meta, frontmatter())
    flags = [arg for key, value in meta.items() if value and key != "release_notes" for arg in ("-M", f"{key}={value}")]
    pdf = BUILD / f"{PDF_PREFIX}-{'draft' if meta['version'] == 'draft' else 'v' + meta['version']}.pdf"
    subprocess.run(["quarto", "render", "--to", "html", *flags], check=True)
    subprocess.run(["quarto", "render", QMD, "--to", "pdf", "--output", pdf.name, "--output-dir", str(BUILD), *flags],
                   check=True)
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    # The download keeps its versioned name (e.g. ...-v2.0-beta.1.pdf); ...-latest.pdf stays for older links.
    for name in (pdf.name, f"{PDF_PREFIX}-latest.pdf"):
        shutil.copy2(pdf, SITE / "assets" / name)
    latest = f"assets/{PDF_PREFIX}-latest.pdf"
    for page in SITE.rglob("*.html"):
        text = page.read_text()
        if latest in text:
            page.write_text(text.replace(latest, f"assets/{pdf.name}"))
    print(f"Built {SITE}/ and {pdf}")
    return pdf


class Zenodo:
    def __init__(self, target: str):
        if target not in ZENODO:
            sys.exit(f"ZENODO_TARGET must be 'sandbox' or 'production', got {target!r}.")
        self.target = target
        self.base, token_var, self.concept_key = ZENODO[target]
        self.token = os.environ.get(token_var, "")
        if not self.token:
            sys.exit(f"ZENODO_TARGET={target} needs the {token_var} secret.")

    def api(self, method: str, url: str, payload=None, data: bytes = None, ctype: str = None):
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if payload is not None:
            data, ctype = json.dumps(payload).encode(), "application/json"
        if ctype:
            headers["Content-Type"] = ctype
        request = urllib.request.Request(url if url.startswith("http") else self.base + url,
                                         data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            sys.exit(f"Zenodo {method} {request.full_url} -> HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}")
        return json.loads(body) if body.strip() else {}

    def doi(self, doi: str) -> str:
        # The sandbox pre-reserves DOIs with the production prefix but mints them under 10.5072.
        return doi.replace("10.5281/", "10.5072/", 1) if self.target == "sandbox" else doi

    def new_version(self, concept_doi: str) -> dict:
        """Create (or reuse) the draft of the next version; returns the draft deposition."""
        concept_id = re.search(r"(\d+)$", concept_doi).group(1)
        latest = self.api("GET", f"/api/records/{concept_id}")  # redirects to the latest version
        links = self.api("POST", f"/api/deposit/depositions/{latest['id']}/actions/newversion")["links"]
        return self.api("GET", links["latest_draft"])

    def fill_draft(self, draft: dict, fm: dict, version: str, date: str, notes: str, pdf: Path) -> None:
        settings = fm["zenodo"]
        notes = "".join(f"<li>{html.escape(line[2:])}</li>" for line in notes.splitlines())
        metadata = draft["metadata"]
        metadata.update(
            title=fm["title"],
            creators=[{"name": fm["produced_by"]}],
            version=version,
            publication_date=date,
            description=metadata.get("description", "").split(NOTES_HEADING)[0] + NOTES_HEADING + f"<ul>{notes}</ul>",
            access_right=settings["access_right"],
            contributors=[{"name": e["name"], "type": "Editor", "affiliation": e.get("institution", ""),
                           "orcid": e.get("orcid", "")} for e in fm.get("editors", [])],
        )
        if settings["access_right"] in ("open", "embargoed"):  # Zenodo only takes a licence for these
            metadata["license"] = settings["license"]
        else:
            metadata.pop("license", None)
        self.api("PUT", f"/api/deposit/depositions/{draft['id']}", {"metadata": metadata})
        for old in draft.get("files", []):  # a reused draft may still hold an earlier upload
            self.api("DELETE", f"/api/deposit/depositions/{draft['id']}/files/{old['id']}")
        self.api("PUT", f"{draft['links']['bucket']}/{urllib.parse.quote(pdf.name)}",
                 data=pdf.read_bytes(), ctype="application/octet-stream")


def cmd_includes(args) -> None:
    """Write the draft includes only, e.g. before `quarto preview`."""
    write_includes({}, frontmatter())


def cmd_build(args) -> None:
    render({"version": "draft", "release_date": "unreleased", "release_year": str(datetime.date.today().year)})


def cmd_prepare(args) -> None:
    fm, ts = frontmatter(), versions.tags()
    zenodo = None if args.prerelease else Zenodo(os.environ.get("ZENODO_TARGET", ""))
    if zenodo:
        tag, candidate = versions.release_tag(ts, test=zenodo.target == "sandbox")
    else:
        tag, candidate = versions.rc_tag(ts), None
    version, notes, today = tag[1:], notes_markdown(args.notes), datetime.date.today()
    meta = {"version": version, "release_date": today.isoformat(), "release_year": str(today.year),
            "release_notes": notes}
    record = {"tag": tag, "version": version, "prerelease": args.prerelease, "test": "-test." in tag,
              "candidate": candidate, "notes": notes}
    print(f"Preparing {tag}" + (f" from release candidate {candidate}" if candidate else ""))

    if not zenodo:
        render(dict(meta, prerelease="true"))
    else:
        draft = zenodo.new_version(fm["zenodo"][zenodo.concept_key])
        doi = zenodo.doi(draft["metadata"]["prereserve_doi"]["doi"])
        print(f"Reserved {doi} on Zenodo {zenodo.target} (draft {draft['id']})")
        pdf = render(dict(meta, doi=doi))
        zenodo.fill_draft(draft, fm, version, meta["release_date"], notes, pdf)
        record.update(doi=doi, draft_id=draft["id"], target=zenodo.target,
                      draft_url=f"{zenodo.base}/deposit/{draft['id']}")
        print(f"Zenodo draft ready for review: {record['draft_url']}")

    (BUILD / "release.json").write_text(json.dumps(record, indent=2) + "\n")


def cmd_publish(args) -> None:
    record = json.loads(Path(args.release_json).read_text())
    if record.get("prerelease") or not record.get("draft_id"):
        sys.exit(f"{record.get('tag')} is a pre-release; there is no Zenodo draft to publish.")
    zenodo = Zenodo(record["target"])
    zenodo.api("POST", f"/api/deposit/depositions/{record['draft_id']}/actions/publish")
    print(f"Published {record['doi']} on Zenodo {zenodo.target}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build").set_defaults(func=cmd_build)
    sub.add_parser("includes").set_defaults(func=cmd_includes)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--notes", default="", help="release notes, items separated by ';'")
    prepare.add_argument("--prerelease", action="store_true")
    prepare.set_defaults(func=cmd_prepare)
    publish = sub.add_parser("publish")
    publish.add_argument("release_json")
    publish.set_defaults(func=cmd_publish)
    args = parser.parse_args()
    BUILD.mkdir(exist_ok=True)
    args.func(args)


if __name__ == "__main__":
    main()
