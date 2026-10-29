#!/usr/bin/env python3
"""Check that everything the admin panel needs is set up (read-only; changes nothing).

Run by .github/workflows/check-setup.yml with the repository's secrets and variables in the environment:
GOOGLE_OAUTH, ZENODO_TOKEN, ZENODO_SANDBOX_TOKEN, ZENODO_TARGET, GDOC_ID, GDRIVE_FOLDER_ID,
GITHUB_TOKEN, GITHUB_REPOSITORY. Prints a table (also to the run summary); exits 1 if something required fails.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gdoc  # noqa: E402
from release import ZENODO  # noqa: E402

SITE = "https://ipbes-data.github.io/IPBES_Data_Vision"
OK, WARN, FAIL = "✅", "⚠️", "❌"
results = []


def report(status: str, item: str, detail: str) -> None:
    results.append((status, item, detail))


def get(url: str, headers: dict = None):
    """(HTTP status, parsed JSON or text); network errors count as status 0."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {})) as r:
            body = r.read().decode()
            status = r.status
    except urllib.error.HTTPError as exc:
        body, status = exc.read().decode(errors="replace"), exc.code
    except urllib.error.URLError as exc:
        return 0, str(exc)
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body


def api_disabled(body) -> bool:
    return "has not been used in project" in str(body) or "is disabled" in str(body)


def check_google() -> None:
    if not os.environ.get("GOOGLE_OAUTH"):
        report(FAIL, "Google sign-in (secret GOOGLE_OAUTH)", "Missing. Run `python3 scripts/gdoc.py login client.json "
               "| gh secret set GOOGLE_OAUTH` (see One-time setup).")
        return
    try:
        token = gdoc.access_token()
    except SystemExit as exc:
        report(FAIL, "Google sign-in (secret GOOGLE_OAUTH)", f"Does not work: {str(exc)[:200]}")
        return
    auth = {"Authorization": f"Bearer {token}"}
    status, body = get("https://www.googleapis.com/drive/v3/about?fields=user", auth)
    if status == 200:
        report(OK, "Google sign-in and Drive API", f"Signed in as {body['user'].get('emailAddress', '?')}.")
    elif api_disabled(body):
        report(FAIL, "Google Drive API", "Not enabled in the Google Cloud project: enable it "
               "(APIs & Services → Library → Google Drive API).")
        return
    else:
        report(FAIL, "Google Drive API", f"HTTP {status}: {str(body)[:200]}")
        return

    _, latest = get(f"{SITE}/admin/latest-export.json")
    latest_doc = gdoc.doc_id(latest["url"]) if isinstance(latest, dict) and latest.get("url") else ""
    # With no Doc to look at, a made-up id still tells "API disabled" (403) apart from "enabled" (404).
    status, body = get(f"https://docs.googleapis.com/v1/documents/{latest_doc or 'setup-check'}?fields=title", auth)
    if api_disabled(body):
        report(WARN, "Google Docs API", "Not enabled: exports and imports work, but superseded Docs get no "
               "'NEW VERSION' / 'IMPORTED' notice. Enable it (APIs & Services → Library → Google Docs API).")
    elif status in (200, 404):
        report(OK, "Google Docs API", "Enabled.")
    else:
        report(WARN, "Google Docs API", f"Unexpected HTTP {status}: {str(body)[:200]}")

    if latest_doc:
        status, body = get(f"https://www.googleapis.com/drive/v3/files/{latest_doc}?fields=name&supportsAllDrives=true", auth)
        report(OK if status == 200 else FAIL, "Latest exported Doc",
               body["name"] if status == 200 else f"Not reachable (HTTP {status}); imports with an empty form would fail.")
    else:
        report(WARN, "Latest exported Doc", "None yet: run Export to Google Doc once.")
    for var, kind in (("GDOC_ID", "Doc"), ("GDRIVE_FOLDER_ID", "folder")):
        if os.environ.get(var):
            target = gdoc.doc_id(os.environ[var].replace("/folders/", "/d/"))
            status, body = get(f"https://www.googleapis.com/drive/v3/files/{target}?fields=name&supportsAllDrives=true", auth)
            report(OK if status == 200 else FAIL, f"Variable {var}",
                   f"{kind}: {body['name']}" if status == 200 else f"The {kind} is not reachable (HTTP {status}).")


def concept_dois() -> dict:
    text = Path("IPBES_Data_Vision.qmd").read_text()
    return {key: m[1] for key in ("concept_doi", "sandbox_concept_doi")
            if (m := re.search(rf'^\s+{key}:\s*"([^"]+)"', text, re.M))}


def check_zenodo() -> None:
    target = os.environ.get("ZENODO_TARGET", "")
    if target == "production":
        report(OK, "Variable ZENODO_TARGET", "production: releases get real DOIs.")
    elif target == "sandbox":
        report(WARN, "Variable ZENODO_TARGET", "sandbox: releases are test releases on sandbox.zenodo.org. "
               "Set it to production for the real release.")
    else:
        report(FAIL, "Variable ZENODO_TARGET", f"Must be sandbox or production, is {target!r}.")
    dois = concept_dois()
    for name, (base, token_var, concept_key) in ZENODO.items():
        token = os.environ.get(token_var, "")
        required = name == target
        if not token:
            report(FAIL if required else WARN, f"Secret {token_var}",
                   f"Missing{' (needed: ZENODO_TARGET is ' + name + ')' if required else ''}.")
            continue
        auth = {"Authorization": f"Bearer {token}"}
        status, body = get(f"{base}/api/deposit/depositions?size=1", auth)
        if status != 200:
            report(FAIL if required else WARN, f"Secret {token_var}", f"Not accepted by {base} (HTTP {status}).")
            continue
        concept = dois.get(concept_key, "")
        status, record = get(f"{base}/api/records/{concept.rsplit('.', 1)[-1]}") if concept else (0, None)
        if status != 200:
            report(FAIL if required else WARN, f"Zenodo {name} record", f"Concept DOI {concept!r} not found on {base}.")
            continue
        status, _ = get(f"{base}/api/deposit/depositions/{record['id']}", auth)
        report(OK if status == 200 else FAIL if required else WARN, f"Zenodo {name}",
               f"Token accepted; its account can make new versions of {concept}." if status == 200 else
               f"Token accepted, but its account does not own {concept} (HTTP {status}): releases would fail.")


def check_github() -> None:
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    if not repo:
        return
    auth = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    status, body = get(f"https://api.github.com/repos/{repo}/pages", auth)
    if status == 200:
        source = body.get("source") or {}
        good = source.get("branch") == "gh-pages"
        report(OK if good else WARN, "GitHub Pages", f"Serves branch {source.get('branch')!r}"
               + ("." if good else "; it should serve gh-pages."))
    else:
        report(WARN, "GitHub Pages", f"Could not check (HTTP {status}).")
    status, body = get(f"https://api.github.com/repos/{repo}/actions/permissions/workflow", auth)
    if status == 200:
        allowed = body.get("can_approve_pull_request_reviews")
        report(OK if allowed else FAIL, "Workflows may open pull requests",
               "Yes." if allowed else "No: the import cannot open its review page. Settings → Actions → General → "
               "tick 'Allow GitHub Actions to create and approve pull requests'.")
    else:
        report(WARN, "Workflows may open pull requests", "Could not check with the workflow's token; see Settings → "
               "Actions → General → 'Allow GitHub Actions to create and approve pull requests'.")


def main() -> int:
    check_google()
    check_zenodo()
    check_github()
    table = "| | Item | Result |\n|---|---|---|\n" + "".join(f"| {s} | {i} | {d} |\n" for s, i, d in results)
    failed = sum(s == FAIL for s, _, _ in results)
    summary = f"### Setup check: {'all required items OK' if not failed else f'{failed} problem(s) to fix'}\n\n{table}"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(summary)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
