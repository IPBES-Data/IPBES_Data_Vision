#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

PDF_PREFIX = "IPBES-Data-Management-Vision"
LATEST_PDF_NAME = "IPBES-Data-Management-Vision-latest.pdf"
DEFAULT_STATE_FILE = ".release-state.env"
DEFAULT_QMD = "IPBES_Data_Vision.qmd"


class HTTPRequestError(Exception):
    def __init__(self, code: int, url: str, details: str):
        super().__init__(f"HTTP {code} on {url}: {details}")
        self.code = code
        self.url = url
        self.details = details


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def compact(text: str, limit: int = 280) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "..."


def append_gha_var(path: str, key: str, value: str) -> None:
    if not path:
        return
    value = "" if value is None else str(value)
    with open(path, "a", encoding="utf-8") as fh:
        if "\n" in value:
            marker = f"EOF_{key}_{uuid.uuid4().hex[:8]}"
            fh.write(f"{key}<<{marker}\n{value}\n{marker}\n")
        else:
            fh.write(f"{key}={value}\n")


def append_summary(message: str) -> None:
    path = os.getenv("GITHUB_STEP_SUMMARY", "")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(message.rstrip() + "\n")


def request_raw(method: str, url: str, payload: bytes = None, headers: dict = None):
    req = urllib.request.Request(url, data=payload, method=method)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8"), resp.status
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise HTTPRequestError(exc.code, url, compact(details))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Connection error on {url}: {exc}")


def request_json(method: str, url: str, payload: dict = None, headers: dict = None):
    body = None
    merged_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        merged_headers["Content-Type"] = "application/json"
    text, _status = request_raw(method, url, payload=body, headers=merged_headers)
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"Failed to decode JSON from {url}: {compact(text)}")


def parse_state_file(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            data[key] = value
    return data


def write_state_file(path: Path, data: dict) -> None:
    lines = [f"{key}={value}" for key, value in sorted(data.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


class StateContext:
    def __init__(self, path: str):
        self.path = Path(path)
        self.state = parse_state_file(self.path)

    def get(self, key: str, default: str = "") -> str:
        if key in os.environ and os.environ[key] != "":
            return os.environ[key]
        if key in self.state and self.state[key] != "":
            return self.state[key]
        return default

    def set(self, key: str, value: str, export_env: bool = False, export_output: bool = False, output_key: str = None) -> None:
        value = "" if value is None else str(value)
        self.state[key] = value
        write_state_file(self.path, self.state)
        if export_env:
            append_gha_var(os.getenv("GITHUB_ENV", ""), key, value)
            os.environ[key] = value
        if export_output:
            append_gha_var(os.getenv("GITHUB_OUTPUT", ""), output_key or key, value)


def strip_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            end_idx = i
            break
    if end_idx is None:
        return {}

    block = lines[1:end_idx]
    out = {}
    i = 0
    while i < len(block):
        line = block[i]
        m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            i += 1
            continue

        indent = len(m.group(1))
        key = m.group(2)
        raw = m.group(3).rstrip()

        if raw.strip() in ("|", "|-", "|+", ">", ">-", ">+"):
            literal_lines = []
            i += 1
            while i < len(block):
                nxt = block[i]
                if not nxt.strip():
                    literal_lines.append("")
                    i += 1
                    continue
                next_indent = len(nxt) - len(nxt.lstrip(" "))
                if next_indent <= indent:
                    break
                literal_lines.append(nxt[next_indent:])
                i += 1
            out[key] = "\n".join(literal_lines).strip()
            continue

        value = re.sub(r"\s+#.*$", "", raw).strip()
        out[key] = strip_quotes(value)
        i += 1

    return out


def validate_target_vs_concept_doi(target: str, concept_doi: str) -> None:
    target = (target or "").strip().lower()
    concept_doi = (concept_doi or "").strip()
    if not target or not concept_doi:
        return

    expected_prefix = {
        "sandbox": "10.5072/zenodo.",
        "production": "10.5281/zenodo.",
    }.get(target)
    if not expected_prefix:
        return

    doi_norm = concept_doi.lower()
    if not doi_norm.startswith(expected_prefix):
        fail(
            f"ZENODO_TARGET={target} but concept_doi='{concept_doi}' does not match expected prefix '{expected_prefix}'."
        )


def derive_conceptrecid(concept_doi: str) -> str:
    m = re.search(r"(?:zenodo\.|/)([0-9]+)$", concept_doi or "")
    return m.group(1) if m else ""


def run_cmd(cmd: list, env: dict = None) -> None:
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        fail(f"Command failed ({result.returncode}): {' '.join(cmd)}")


def cmd_resolve_target(args, ctx: StateContext) -> None:
    raw_target = ctx.get("ZENODO_TARGET", "").strip().lower()
    target = raw_target if raw_target in ("sandbox", "production") else "production"
    if raw_target and raw_target not in ("sandbox", "production"):
        print(f"Warning: invalid ZENODO_TARGET={raw_target!r}; defaulting to production.", file=sys.stderr)

    if target == "sandbox":
        base_var = "ZENODO_SANDBOX_API_BASE"
        token_var = "ZENODO_SANDBOX_TOKEN"
    else:
        base_var = "ZENODO_API_BASE"
        token_var = "ZENODO_TOKEN"

    base = ctx.get(base_var, "").strip().rstrip("/")
    token = ctx.get(token_var, "").strip()

    if not base:
        fail(f"ZENODO_TARGET={target}: missing required setting `{base_var}`.")
    if not token:
        fail(f"ZENODO_TARGET={target}: missing required setting `{token_var}`.")

    ctx.set("ACTIVE_ZENODO_TARGET", target, export_env=True)
    ctx.set("ACTIVE_ZENODO_API_BASE", base, export_env=True)
    ctx.set("ACTIVE_ZENODO_TOKEN", token, export_env=True)

    append_summary(f"Zenodo target selected: `{target}`")
    append_summary(f"Zenodo API base source: `{base_var}`")
    append_summary("Zenodo token source selected successfully.")


def cmd_read_frontmatter(args, ctx: StateContext) -> None:
    qmd_path = Path(args.qmd)
    if not qmd_path.exists():
        fail(f"Frontmatter source file not found: {qmd_path}")

    meta = parse_frontmatter(qmd_path)
    version = str(meta.get("version", "")).strip()
    concept_doi = str(meta.get("concept_doi", "")).strip()
    release_notes = str(meta.get("release_notes", "")).strip()

    if not version:
        fail(f"Missing `version` in YAML frontmatter of {qmd_path}.")
    if not concept_doi:
        fail(f"Missing `concept_doi` in YAML frontmatter of {qmd_path}.")

    conceptrecid = derive_conceptrecid(concept_doi)
    if not conceptrecid:
        fail(f"Could not derive Zenodo concept record id from concept_doi `{concept_doi}`.")

    target = ctx.get("ACTIVE_ZENODO_TARGET", "").strip().lower()
    validate_target_vs_concept_doi(target, concept_doi)

    ctx.set("IPBES_VERSION", version, export_env=True)
    ctx.set("IPBES_CONCEPT_DOI", concept_doi, export_env=True)
    ctx.set("ZENODO_CONCEPTRECID", conceptrecid, export_env=True)
    if release_notes:
        append_gha_var(os.getenv("GITHUB_ENV", ""), "IPBES_RELEASE_NOTES_FALLBACK", release_notes)

    ctx.set("frontmatter_version", version, export_output=True)
    ctx.set("frontmatter_concept_doi", concept_doi, export_output=True)
    ctx.set("frontmatter_conceptrecid", conceptrecid, export_output=True)


def cmd_reserve_doi(args, ctx: StateContext) -> None:
    target = ctx.get("ACTIVE_ZENODO_TARGET", "").strip() or "production"
    base = ctx.get("ACTIVE_ZENODO_API_BASE", "").strip().rstrip("/")
    token = ctx.get("ACTIVE_ZENODO_TOKEN", "").strip()
    conceptrecid = ctx.get("ZENODO_CONCEPTRECID", "").strip()
    concept_doi = ctx.get("IPBES_CONCEPT_DOI", "").strip()

    if not token:
        fail(f"ZENODO_TARGET={target}: missing ACTIVE_ZENODO_TOKEN from resolve step.")
    if not base:
        fail(f"ZENODO_TARGET={target}: missing ACTIVE_ZENODO_API_BASE from resolve step.")
    if not conceptrecid:
        fail(f"ZENODO_TARGET={target}: missing ZENODO_CONCEPTRECID derived from frontmatter concept_doi.")
    if not concept_doi:
        fail("Missing IPBES_CONCEPT_DOI from frontmatter step.")

    validate_target_vs_concept_doi(target, concept_doi)

    token_q = urllib.parse.quote(token, safe="")
    stats = {}

    def search_depositions(query_value: str, label: str):
        query = urllib.parse.quote(query_value, safe="")
        url = f"{base}/api/deposit/depositions?access_token={token_q}&q={query}&sort=mostrecent"
        payload = request_json("GET", url)
        if not isinstance(payload, list):
            payload = []
        stats[label] = len(payload)
        return payload

    def search_records(query_value: str, label: str):
        # Public records endpoint enforces size <= 25 unless auth is accepted.
        # Use safe pagination at size=25 to avoid 400 errors across environments.
        page = 1
        size = 25
        all_hits = []
        while True:
            query = urllib.parse.quote(query_value, safe="")
            url = (
                f"{base}/api/records?"
                f"q={query}&all_versions=true&sort=mostrecent&page={page}&size={size}"
            )
            headers = {"Accept": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            payload = request_json("GET", url, headers=headers)
            hits = (payload.get("hits") or {}).get("hits") if isinstance(payload, dict) else []
            if not isinstance(hits, list) or len(hits) == 0:
                break
            all_hits.extend(hits)
            if len(hits) < size:
                break
            page += 1
        stats[label] = len(all_hits)
        return all_hits

    candidates = []
    seen = set()

    def add_candidate(candidate_id, source: str):
        cid = str(candidate_id or "").strip()
        if not cid or cid in seen:
            return
        seen.add(cid)
        candidates.append((cid, source))

    try:
        for dep in search_depositions(f"conceptrecid:{conceptrecid}", "depositions_conceptrecid"):
            add_candidate(dep.get("id"), "depositions:conceptrecid")

        for dep in search_depositions(f'conceptdoi:"{concept_doi}"', "depositions_conceptdoi"):
            add_candidate(dep.get("id"), "depositions:conceptdoi")

        for rec in search_records(f'conceptdoi:"{concept_doi}"', "records_conceptdoi"):
            add_candidate(rec.get("id"), "records:conceptdoi")
    except HTTPRequestError as exc:
        fail(f"Zenodo API error ({exc.code}) on {exc.url}: {exc.details}")
    except RuntimeError as exc:
        fail(str(exc))

    if not candidates:
        fail(
            "No Zenodo candidates found for DOI reservation. "
            f"target={target}, concept_doi={concept_doi}, conceptrecid={conceptrecid}, "
            f"counts={stats}"
        )

    attempt_errors = []
    reserved = None

    for candidate_id, source in candidates:
        new_version_url = (
            f"{base}/api/deposit/depositions/{candidate_id}/actions/newversion?access_token={token_q}"
        )
        try:
            new_version_resp = request_json("POST", new_version_url)
        except HTTPRequestError as exc:
            attempt_errors.append((candidate_id, source, exc.code, exc.details))
            continue
        except RuntimeError as exc:
            attempt_errors.append((candidate_id, source, 0, str(exc)))
            continue

        draft_url = (new_version_resp.get("links") or {}).get("latest_draft")
        if not draft_url:
            attempt_errors.append((candidate_id, source, 0, "newversion response missing latest_draft"))
            continue
        if "access_token=" not in draft_url:
            separator = "&" if "?" in draft_url else "?"
            draft_url = f"{draft_url}{separator}access_token={token_q}"

        try:
            draft_resp = request_json("GET", draft_url)
        except HTTPRequestError as exc:
            attempt_errors.append((candidate_id, source, exc.code, exc.details))
            continue
        except RuntimeError as exc:
            attempt_errors.append((candidate_id, source, 0, str(exc)))
            continue

        draft_id = draft_resp.get("id")
        if draft_id is None:
            attempt_errors.append((candidate_id, source, 0, "draft response missing deposition id"))
            continue

        metadata = draft_resp.get("metadata") or {}
        prereserve = metadata.get("prereserve_doi") or {}
        doi = str((prereserve.get("doi") or draft_resp.get("doi") or "")).strip()
        if not doi:
            attempt_errors.append((candidate_id, source, 0, "reserved DOI missing in draft response"))
            continue

        draft_links = draft_resp.get("links") or {}
        draft_html_url = draft_links.get("latest_draft_html") or draft_links.get("html") or ""
        reserved = {
            "doi": doi,
            "draft_id": str(draft_id),
            "draft_html_url": draft_html_url,
            "source": source,
            "candidate_id": candidate_id,
        }
        break

    if reserved is None:
        unauthorized = [a for a in attempt_errors if a[2] in (401, 403)]
        notfound = [a for a in attempt_errors if a[2] == 404]
        attempts = [f"{cid}@{src}: {code} {compact(msg, 120)}" for cid, src, code, msg in attempt_errors[:8]]
        if unauthorized:
            fail(
                "Zenodo candidates found but token is not authorized to create a new version. "
                f"target={target}, concept_doi={concept_doi}, attempts={attempts}"
            )
        if notfound and len(notfound) == len(attempt_errors):
            fail(
                "Zenodo candidates were found but were invalid/not found for newversion. "
                f"target={target}, concept_doi={concept_doi}, attempts={attempts}"
            )
        fail(
            "Failed to reserve Zenodo DOI after trying all candidates. "
            f"target={target}, concept_doi={concept_doi}, counts={stats}, attempts={attempts}"
        )

    doi = reserved["doi"]
    doi_url = f"https://doi.org/{doi}"

    ctx.set("IPBES_DOI", doi, export_env=True)
    ctx.set("IPBES_DOI_URL", doi_url, export_env=True)
    ctx.set("ZENODO_DRAFT_ID", reserved["draft_id"], export_env=True)

    ctx.set("reserved_doi", doi, export_output=True)
    ctx.set("draft_deposition_id", reserved["draft_id"], export_output=True)
    if reserved["draft_html_url"]:
        ctx.set("draft_html_url", reserved["draft_html_url"], export_output=True)

    print(f"Reserved Zenodo DOI: {doi}")
    append_summary(f"Reserved Zenodo DOI: `{doi}`")
    append_summary(
        f"Reservation candidate source: `{reserved['source']}` (id `{reserved['candidate_id']}`)"
    )


def cmd_append_github_release_doi(args, ctx: StateContext) -> None:
    doi = (ctx.get("IPBES_DOI", "").strip() or ctx.get("reserved_doi", "").strip() or os.getenv("RESERVED_DOI", "").strip())
    if not doi:
        fail("Missing reserved DOI for GitHub release note append step.")

    github_token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    release_id = os.getenv("RELEASE_ID", "").strip()

    if not github_token:
        fail("Missing GITHUB_TOKEN for append-github-release-doi.")
    if not repo:
        fail("Missing GITHUB_REPOSITORY for append-github-release-doi.")
    if not release_id:
        fail("Missing RELEASE_ID for append-github-release-doi.")

    url = f"https://api.github.com/repos/{repo}/releases/{release_id}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        release = request_json("GET", url, headers=headers)
    except HTTPRequestError as exc:
        fail(f"GitHub API error ({exc.code}) on {exc.url}: {exc.details}")

    doi_line = f"Version DOI: https://doi.org/{doi}"
    body = str(release.get("body") or "")

    pattern = re.compile(r"^Version DOI:\s+https://doi\.org/\S+\s*$", flags=re.MULTILINE)
    if pattern.search(body):
        next_body = pattern.sub(doi_line, body)
    else:
        next_body = f"{body.rstrip()}\n\n{doi_line}" if body.strip() else doi_line

    if next_body == body:
        print("Release notes already contain the current version DOI line.")
        return

    try:
        request_json("PATCH", url, payload={"body": next_body}, headers=headers)
    except HTTPRequestError as exc:
        fail(f"GitHub API error ({exc.code}) on {exc.url}: {exc.details}")

    print("Version DOI line appended to release notes.")
    append_summary("Version DOI line appended/updated in GitHub release notes.")


def sanitize_version(version: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", str(version))


def cmd_build_artifacts(args, ctx: StateContext) -> None:
    qmd = args.qmd
    output_dir = args.output_dir or ctx.get("IPBES_OUTPUT_DIR", "_site")
    build_dir = args.build_dir

    version = ctx.get("IPBES_VERSION", "").strip()
    if not version:
        fail("Missing IPBES_VERSION in state/environment. Run read-frontmatter first.")

    safe_version = sanitize_version(version)
    pdf_name = f"{PDF_PREFIX}-{safe_version}.pdf"
    pdf_path = str(Path(build_dir) / pdf_name)
    latest_pdf = str(Path(output_dir) / "assets" / LATEST_PDF_NAME)

    os.makedirs(build_dir, exist_ok=True)

    run_env = os.environ.copy()
    run_env["IPBES_BUILD_PDF"] = "true"
    run_env["IPBES_OUTPUT_DIR"] = output_dir

    doi = ctx.get("IPBES_DOI", "").strip()
    if doi:
        run_env["IPBES_DOI"] = doi

    run_cmd(["quarto", "render", ".", "--to", "html"], env=run_env)

    pdf_cmd = [
        "quarto",
        "render",
        qmd,
        "--to",
        "pdf",
        "--output",
        pdf_name,
        "--output-dir",
        build_dir,
    ]
    if doi:
        pdf_cmd.extend(["-M", f"doi={doi}"])

    run_cmd(pdf_cmd, env=run_env)

    if not Path(pdf_path).exists():
        fail(f"Expected PDF output not found: {pdf_path}")

    os.makedirs(Path(output_dir) / "assets", exist_ok=True)
    shutil.copy2(pdf_path, latest_pdf)

    ctx.set("PDF_NAME", pdf_name, export_env=True)
    ctx.set("PDF_PATH", pdf_path, export_env=True)
    ctx.set("LATEST_PDF", latest_pdf, export_env=True)

    ctx.set("pdf_name", pdf_name, export_output=True)
    ctx.set("pdf_path", pdf_path, export_output=True)
    ctx.set("latest_pdf", latest_pdf, export_output=True)

    append_summary(f"Built website + PDF: `{pdf_path}`")
    append_summary(f"Updated latest PDF alias: `{latest_pdf}`")


def fetch_release_notes(ctx: StateContext) -> str:
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    release_id = os.getenv("RELEASE_ID", "").strip()
    github_token = os.getenv("GITHUB_TOKEN", "").strip()

    if repo and release_id and github_token:
        url = f"https://api.github.com/repos/{repo}/releases/{release_id}"
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            gh_release = request_json("GET", url, headers=headers)
            body = str(gh_release.get("body") or "").strip()
            if body:
                return body
        except Exception:
            pass

    for key in ("IPBES_RELEASE_NOTES",):
        notes = ctx.get(key, "").strip()
        if notes:
            return notes

    try:
        frontmatter = parse_frontmatter(Path(DEFAULT_QMD))
        notes = str(frontmatter.get("release_notes", "")).strip()
        if notes:
            return notes
    except Exception:
        pass

    return "Release notes not provided."


def cmd_upload_zenodo_draft(args, ctx: StateContext) -> None:
    target = ctx.get("ACTIVE_ZENODO_TARGET", "").strip() or "production"
    base = ctx.get("ACTIVE_ZENODO_API_BASE", "").strip().rstrip("/")
    token = ctx.get("ACTIVE_ZENODO_TOKEN", "").strip()
    draft_id = ctx.get("ZENODO_DRAFT_ID", "").strip() or ctx.get("draft_deposition_id", "").strip()
    pdf_file = (args.pdf_file or ctx.get("PDF_PATH", "").strip())

    if not token:
        fail(f"ZENODO_TARGET={target}: missing ACTIVE_ZENODO_TOKEN from resolve step.")
    if not base:
        fail(f"ZENODO_TARGET={target}: missing ACTIVE_ZENODO_API_BASE from resolve step.")
    if not draft_id:
        fail("Missing Zenodo draft deposition id from reserve step.")
    if not pdf_file or not Path(pdf_file).exists():
        fail(f"PDF file not found: {pdf_file}")

    token_q = urllib.parse.quote(token, safe="")
    draft_url = f"{base}/api/deposit/depositions/{draft_id}?access_token={token_q}"

    try:
        draft = request_json("GET", draft_url)
    except HTTPRequestError as exc:
        fail(f"Zenodo API error ({exc.code}) on {exc.url}: {exc.details}")

    links = draft.get("links") or {}
    bucket_url = links.get("bucket") or ""

    release_notes = fetch_release_notes(ctx)
    metadata = draft.get("metadata") or {}
    metadata["description"] = f"<pre>{html.escape(release_notes)}</pre>"

    try:
        request_json("PUT", draft_url, payload={"metadata": metadata})
    except HTTPRequestError as exc:
        fail(f"Zenodo API error ({exc.code}) on {exc.url}: {exc.details}")

    filename = Path(pdf_file).name
    pdf_data = Path(pdf_file).read_bytes()
    files = draft.get("files") or []

    deleted_count = 0
    upload_mode = ""
    try:
        for file_entry in files:
            file_id = file_entry.get("id")
            if not file_id:
                continue
            delete_url = f"{base}/api/deposit/depositions/{draft_id}/files/{file_id}?access_token={token_q}"
            try:
                request_raw("DELETE", delete_url)
                deleted_count += 1
            except HTTPRequestError as exc:
                if exc.code != 404:
                    raise

        if bucket_url:
            upload_url = f"{bucket_url.rstrip('/')}/{urllib.parse.quote(filename)}"
            upload_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
            }
            try:
                request_raw("PUT", upload_url, payload=pdf_data, headers=upload_headers)
            except HTTPRequestError as exc:
                # Compatibility fallback for Zenodo variants that accept PDF-specific content type.
                if exc.code != 415:
                    raise
                upload_headers["Content-Type"] = "application/pdf"
                request_raw("PUT", upload_url, payload=pdf_data, headers=upload_headers)
            upload_mode = "bucket-put"
        else:
            boundary = f"----codex{uuid.uuid4().hex}"
            preamble = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="name"\r\n\r\n'
                f"{filename}\r\n"
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f"Content-Type: application/pdf\r\n\r\n"
            ).encode("utf-8")
            epilogue = f"\r\n--{boundary}--\r\n".encode("utf-8")
            multipart_body = preamble + pdf_data + epilogue
            multipart_headers = {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            }
            upload_url = f"{base}/api/deposit/depositions/{draft_id}/files?access_token={token_q}"
            request_raw("POST", upload_url, payload=multipart_body, headers=multipart_headers)
            upload_mode = "legacy-multipart-post"
    except HTTPRequestError as exc:
        fail(f"Zenodo API error ({exc.code}) on {exc.url}: {exc.details}")

    try:
        draft_after_upload = request_json("GET", draft_url)
    except HTTPRequestError as exc:
        fail(f"Zenodo API error ({exc.code}) on {exc.url}: {exc.details}")

    if bool(draft_after_upload.get("submitted")):
        fail(
            "Zenodo deposition is marked submitted/published after upload. "
            "Workflow must leave Zenodo in draft state."
        )

    draft_links = draft_after_upload.get("links") or {}
    draft_html_url = (
        draft_links.get("latest_draft_html")
        or draft_links.get("html")
        or f"{base}/deposit/{draft_id}"
    )

    ctx.set("zenodo_draft_html_url", draft_html_url, export_output=True)
    append_summary(f"Zenodo draft updated: {draft_html_url}")
    append_summary(f"Upload mode: {upload_mode}")
    append_summary(f"Removed existing draft files: {deleted_count}")
    append_summary("PDF uploaded and release notes copied to metadata description.")
    append_summary("Zenodo draft state verified: submitted=false.")
    append_summary("Draft was not published; DOI minting remains a manual step.")


def build_parser():
    parser = argparse.ArgumentParser(description="Shared release pipeline for local and CI runs.")
    parser.add_argument("--state-file", default=DEFAULT_STATE_FILE, help="State env file path.")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("resolve-target", help="Resolve active Zenodo target/base/token.")

    p_front = sub.add_parser("read-frontmatter", help="Read version and concept DOI from frontmatter.")
    p_front.add_argument("--qmd", default=DEFAULT_QMD, help="Path to main qmd file.")

    sub.add_parser("reserve-doi", help="Reserve Zenodo DOI using robust candidate discovery.")

    p_build = sub.add_parser("build-artifacts", help="Build website and PDF artifacts.")
    p_build.add_argument("--qmd", default=DEFAULT_QMD, help="Path to main qmd file.")
    p_build.add_argument("--output-dir", default="", help="Site output directory.")
    p_build.add_argument("--build-dir", default="build", help="PDF build directory.")

    p_upload = sub.add_parser("upload-zenodo-draft", help="Upload PDF and notes to Zenodo draft.")
    p_upload.add_argument("--pdf-file", default="", help="PDF file path; defaults to PDF_PATH from state.")

    sub.add_parser("append-github-release-doi", help="Append reserved DOI line to GitHub release notes.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    ctx = StateContext(args.state_file)

    if args.command == "resolve-target":
        cmd_resolve_target(args, ctx)
    elif args.command == "read-frontmatter":
        cmd_read_frontmatter(args, ctx)
    elif args.command == "reserve-doi":
        cmd_reserve_doi(args, ctx)
    elif args.command == "append-github-release-doi":
        cmd_append_github_release_doi(args, ctx)
    elif args.command == "build-artifacts":
        cmd_build_artifacts(args, ctx)
    elif args.command == "upload-zenodo-draft":
        cmd_upload_zenodo_draft(args, ctx)
    else:
        fail(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
