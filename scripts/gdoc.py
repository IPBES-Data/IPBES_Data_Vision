#!/usr/bin/env python3
"""Move the Vision text between Google Docs and this repository (Python stdlib + Pandoc).

  gdoc.py import <doc link or id>       Google Doc -> _content.md (+ media/) and the bibliographic fields in the .qmd
  gdoc.py export [folder] [version]     bibliographic fields + _content.md -> a new Google Doc (default folder:
                                        My Drive); version (e.g. 1.1, default: current target) goes into the Doc
  gdoc.py stamp-import <doc> <url>      put "IMPORTED into <url>" on top of the Doc and lock it (read-only)
  gdoc.py login <client.json>           one-time sign-in; prints the GOOGLE_OAUTH secret on stdout

An export also puts "NEW VERSION AVAILABLE: <link>" on top of the previous export (PREVIOUS_EXPORT, a link),
locks it and moves it into a folder "archive" next to it (its link stays the same). Locking uses Drive's content restriction (the Doc's owner can unlock it in Drive); the notice
needs the Google Docs API to be enabled in the Google Cloud project.

Google Doc layout (export writes it, import reads it). Everything before the first heading is front matter:
  - a "Document information" table, one row per field (FIELDS below), value in the second column;
  - an "Editors" table with the columns Name | Institution | ORCID, one row per editor;
  - anything else there (the "Current version" row, notes, table of contents) is ignored.
The text starts at the first Heading 1 that is not a table of contents.

Auth: GOOGLE_OAUTH holds {"client_id", "client_secret", "refresh_token"} from `login`, so import and
export act as the person who signed in: they can read that person's Docs and new Docs belong to them.
"""
import http.server
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
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

import versions

QMD = Path("IPBES_Data_Vision.qmd")
CONTENT = Path("_content.md")
MEDIA = Path("media")
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
GDOC = "application/vnd.google-apps.document"
FOLDER = "application/vnd.google-apps.folder"
ARCHIVE = "archive"  # superseded exports are moved into this folder, next to where they were
SCOPE = "https://www.googleapis.com/auth/drive"
TOKEN_URL = "https://oauth2.googleapis.com/token"
# Row label in the "Document information" table -> frontmatter key. All rows are required.
FIELDS = {"Title": "title", "Produced by": "produced_by", "Publisher": "publisher", "Contact e-mail": "contact_email",
          "Target version": "next_version"}
OLD_LABELS = {"version": "next_version"}  # label used by earlier exports
CURRENT = "Current version (information only)"
EDITOR_COLUMNS = ["Name", "Institution", "ORCID"]
ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
NOTE = ("Edit the two tables below to change the bibliographic information; add or delete rows in the Editors "
        "table as needed. Do not rename the tables' first column. Current version is the version of the text in "
        "this Doc. Target version is the version the edits work towards: the next minor (e.g. 1.1) for wording, corrections, references or editors, or the next major "
        "(e.g. 2.0) when aims, tracks, targets or the structure change; beta and release-candidate numbers are "
        "added automatically. The text of the Vision starts at the first heading; this part is not copied into it.")


def doc_id(link: str) -> str:
    match = re.search(r"/d/([\w-]+)", link)
    return match.group(1) if match else link.strip()


def access_token() -> str:
    """Short-lived access token from the stored refresh token."""
    auth = json.loads(os.environ["GOOGLE_OAUTH"])
    body = urllib.parse.urlencode(dict(grant_type="refresh_token", client_id=auth["client_id"],
                                       client_secret=auth["client_secret"], refresh_token=auth["refresh_token"]))
    return json.loads(call("POST", TOKEN_URL, body.encode(),
                           {"Content-Type": "application/x-www-form-urlencoded"}))["access_token"]


def call(method: str, url: str, data: bytes = None, headers: dict = None) -> bytes:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers or {})) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        if "invalid_grant" in detail:
            detail += "\nThe Google sign-in has expired or was revoked; run `scripts/gdoc.py login` again."
        elif "has not been used in project" in detail or "is disabled" in detail:
            detail += "\nEnable this API in the Google Cloud project (link above), wait a few minutes, then retry."
        elif exc.code in (403, 404):
            detail += "\nCan the account that signed in open this Google Doc or folder?"
        sys.exit(f"Google {method} {url.split('?')[0]} -> HTTP {exc.code}: {detail}")


def pandoc(*args: str, stdin: str = None) -> str:
    return subprocess.run(["quarto", "pandoc", *args], input=stdin, capture_output=True, text=True, check=True).stdout


def text(node) -> str:
    """Plain text of a Pandoc JSON node (inline or block, or a list of them)."""
    if isinstance(node, list):
        return "".join(text(n) for n in node)
    if not isinstance(node, dict):
        return ""
    kind, content = node.get("t"), node.get("c")
    if kind == "Str":
        return content
    if kind in ("Space", "SoftBreak", "LineBreak"):
        return " "
    if kind in ("Para", "Plain"):
        return text(content) + " "
    if kind in ("Link", "Image", "Span", "Quoted", "Cite"):  # [attr or type, inlines, ...]
        return text(content[1])
    if kind == "Code":
        return content[1]
    return text(content) if isinstance(content, list) else ""


def table_rows(table: dict) -> list:
    """All rows of a Pandoc table as lists of cell texts (head rows included)."""
    _, _, _, head, bodies, _ = table["c"]
    rows = head[1] + [row for body in bodies for row in body[2] + body[3]]
    return [[" ".join(text(cell[4]).split()) for cell in row[1]] for row in rows]


def read_front_matter(blocks: list) -> dict:
    """Bibliographic fields and editors from the tables before the first heading; exits with a clear message."""
    problems, fields, editors = [], {}, None
    for table in (b for b in blocks if b["t"] == "Table"):
        rows = table_rows(table)
        if rows and [c.lower() for c in rows[0][:3]] == [c.lower() for c in EDITOR_COLUMNS]:
            editors = []
            for name, institution, orcid in ((r + ["", ""])[:3] for r in rows[1:] if r and r[0]):
                editor = {"name": name}
                if institution:
                    editor["institution"] = institution
                if orcid:
                    match = ORCID.search(orcid)
                    if not match:
                        problems.append(f"Editors table: ORCID of {name} must look like 0000-0002-1825-0097, got {orcid!r}.")
                    else:
                        editor["orcid"] = match.group(0)
                editors.append(editor)
        else:
            labels = {**OLD_LABELS, **{label.lower(): key for label, key in FIELDS.items()}}
            for row in rows:
                key = labels.get(row[0].rstrip(":").strip().lower()) if row else None
                if key:
                    fields[key] = row[1] if len(row) > 1 else ""
    for label, key in FIELDS.items():
        if not fields.get(key):
            problems.append(f"Document information table: the row '{label}' is missing or empty.")
    if fields.get("contact_email") and not EMAIL.fullmatch(fields["contact_email"]):
        problems.append(f"Document information table: 'Contact e-mail' is not an e-mail address: {fields['contact_email']!r}.")
    if not editors:
        problems.append("Editors table (columns Name | Institution | ORCID) is missing or has no editors.")
    if problems:
        sys.exit("The front matter of the Google Doc needs fixing:\n- " + "\n- ".join(problems))
    return dict(fields, editors=editors)


def clean_body(body: str) -> str:
    body = re.sub(r"\[\]\{#[^}]*\}", "", body)                              # empty bookmark anchors
    body = re.sub(r"^(#+ .*?)\s*\{[^}]*\}\s*$", r"\1", body, flags=re.M)     # heading ids from Google
    # Section numbers come from the templates, so drop typed ones ("I. Introduction", "2.1 Scope").
    return re.sub(r"^(#+ )(?:[IVXLC]+|\d+(?:\.\d+)*|[A-Z])[.)]?\s+(?=\S)", r"\1", body, flags=re.M)


def update_frontmatter(text_: str, meta: dict) -> str:
    head, sep, rest = text_.partition("\n---\n")
    for key in FIELDS.values():
        head = re.sub(rf"^{key}: .*$", lambda _: f"{key}: {json.dumps(meta[key])}", head, count=1, flags=re.M)
    block = "editors:\n" + "".join(
        f"  - name: {json.dumps(e['name'])}\n" + "".join(f"    {k}: {json.dumps(e[k])}\n"
                                                     for k in ("institution", "orcid") if e.get(k))
        for e in meta["editors"])
    head = re.sub(r"^editors:\n(?:  .*\n?)*", lambda _: block, head + "\n", count=1, flags=re.M).rstrip("\n")
    return head + sep + rest


def import_docx(docx: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "doc.docx")
        path.write_bytes(docx)
        shutil.rmtree(MEDIA, ignore_errors=True)
        doc = json.loads(pandoc(str(path), "-t", "json", "--shift-heading-level-by=1", "--track-changes=accept",
                                "--extract-media=."))
    blocks = doc["blocks"]
    toc = re.compile(r"(table of )?contents$", re.I)
    first = next((i for i, b in enumerate(blocks) if b["t"] == "Header" and not toc.match(text(b["c"][2]).strip())),
                 None)
    if first is None:
        sys.exit("No headings found in the Google Doc; section titles must use the Heading 1/2/3 styles.")
    meta = read_front_matter(blocks[:first])
    meta["next_version"] = versions.fmt(versions.check(meta["next_version"], versions.tags()))
    body = pandoc("-f", "json", "-t", "markdown-smart", "--wrap=none", stdin=json.dumps(dict(doc, blocks=blocks[first:])))
    CONTENT.write_text(clean_body(body).strip() + "\n")
    QMD.write_text(update_frontmatter(QMD.read_text(), meta))
    editors = "; ".join(e["name"] for e in meta["editors"])
    print(f"Imported {meta['title']!r}; editors: {editors}; "
          f"images: {len(list(MEDIA.glob('*'))) if MEDIA.exists() else 0}")


def cell(value: str) -> str:
    return str(value or "").replace("|", "\\|")


def export_docx(version: str = "") -> bytes:
    """The Doc as .docx; `version` (e.g. "1.1") is what the text is prepared as, default: the current target."""
    ts = versions.tags()
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "meta.txt").write_text("$meta-json$")
        meta = json.loads(pandoc(str(QMD), "-t", "plain", "--template", str(Path(tmp, "meta.txt"))))
        meta["next_version"] = versions.fmt(versions.check(version, ts) if version.strip() else versions.target(ts))
        based_on = versions.based_on(ts)
        front = [f"*{NOTE}*", "", "**Document information**", "", "| Field | Value |", "|---|---|"]
        front += [f"| {label} | {cell(meta.get(key))} |" for label, key in FIELDS.items()]
        front.insert(-1, f"| {CURRENT} | {based_on} |")
        front += ["", "**Editors**", "", "| " + " | ".join(EDITOR_COLUMNS) + " |", "|---|---|---|"]
        front += [f"| {cell(e.get('name'))} | {cell(e.get('institution'))} | {cell(e.get('orcid'))} |"
                  for e in meta.get("editors", [])]
        out = Path(tmp, "doc.docx")
        pandoc("-f", "markdown", "-o", str(out), "--shift-heading-level-by=-1", "--resource-path=.",
               stdin="\n".join(front) + "\n\n" + CONTENT.read_text())
        return out.read_bytes()


def stamp(doc: str, before: str, link_text: str, url: str, after: str = "") -> None:
    """Put a highlighted notice with a link at the top of a Google Doc, then lock the Doc (read-only)."""
    target, token = doc_id(doc), access_token()
    file_url = f"https://www.googleapis.com/drive/v3/files/{target}?supportsAllDrives=true"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    lock = lambda read_only: call("PATCH", file_url, json.dumps({"contentRestrictions": [
        {"readOnly": read_only, **({"reason": before.strip()} if read_only else {})}]}).encode(), headers)
    units = lambda s: len(s.encode("utf-16-le")) // 2  # Docs indexes count UTF-16 code units
    text = f"{before} {link_text}{after}\n"
    link_start = 1 + units(before) + 1
    style = {"bold": True, "fontSize": {"magnitude": 14, "unit": "PT"},
             "foregroundColor": {"color": {"rgbColor": {"red": 0.6, "green": 0.1, "blue": 0.1}}},
             "backgroundColor": {"color": {"rgbColor": {"red": 1.0, "green": 0.93, "blue": 0.6}}}}
    requests = [
        {"insertText": {"location": {"index": 1}, "text": text}},
        {"updateTextStyle": {"range": {"startIndex": 1, "endIndex": units(text)}, "textStyle": style,
                             "fields": ",".join(style)}},
        {"updateTextStyle": {"range": {"startIndex": link_start, "endIndex": link_start + units(link_text)},
                             "textStyle": {"link": {"url": url}}, "fields": "link"}},
    ]
    lock(False)  # a Doc locked earlier (e.g. after an import) must be unlocked to take the notice
    call("POST", f"https://docs.googleapis.com/v1/documents/{target}:batchUpdate", json.dumps({"requests": requests}).encode(),
         headers)
    lock(True)


def archive(doc: str) -> str:
    """Move a Doc into the folder ARCHIVE next to it (created if missing); its link stays the same."""
    target, token = doc_id(doc), access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    drive = "https://www.googleapis.com/drive/v3/files"
    parent = json.loads(call("GET", f"{drive}/{target}?fields=parents&supportsAllDrives=true", headers=headers))["parents"][0]
    query = urllib.parse.quote(f"name = '{ARCHIVE}' and '{parent}' in parents and mimeType = '{FOLDER}' and trashed = false")
    found = json.loads(call("GET", f"{drive}?q={query}&fields=files(id)&supportsAllDrives=true&includeItemsFromAllDrives=true",
                            headers=headers))["files"]
    folder = found[0]["id"] if found else json.loads(call(
        "POST", f"{drive}?supportsAllDrives=true", json.dumps({"name": ARCHIVE, "mimeType": FOLDER, "parents": [parent]}).encode(),
        headers))["id"]
    call("PATCH", f"{drive}/{target}?addParents={folder}&removeParents={parent}&supportsAllDrives=true", b"{}", headers)
    return f"https://drive.google.com/drive/folders/{folder}"


def cmd_stamp_import(doc: str, url: str) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stamp(doc, f"IMPORTED on {today} into", url, url, " (version number follows when accepted). This Doc is now read-only.")
    print(f"Marked {doc} as imported and locked it.")


def cmd_import(link: str) -> None:
    token = access_token()
    import_docx(call("GET", f"https://www.googleapis.com/drive/v3/files/{doc_id(link)}/export?mimeType={DOCX}",
                     headers={"Authorization": f"Bearer {token}"}))


def cmd_export(folder: str = "", version: str = "") -> None:
    """Upload the export as a new Google Doc (Drive converts the .docx); record it in build/latest-export.json."""
    ts = versions.tags()
    version = versions.fmt(versions.check(version, ts) if version.strip() else versions.target(ts))
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    metadata = {"name": f"IPBES Data Management Vision {version} - export {created_at}", "mimeType": GDOC}
    if folder:
        metadata["parents"] = [doc_id(folder.replace("/folders/", "/d/"))]
    boundary = "vision-export-boundary"
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\nContent-Type: {DOCX}\r\n\r\n").encode() + export_docx(version) + f"\r\n--{boundary}--\r\n".encode()
    token = access_token()
    created = json.loads(call("POST", "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                                      "&supportsAllDrives=true", body,
                              {"Authorization": f"Bearer {token}", "Content-Type": f"multipart/related; boundary={boundary}"}))
    record = {"name": metadata["name"], "url": f"https://docs.google.com/document/d/{created['id']}/edit",
              "version": version, "created": created_at}
    Path("build").mkdir(exist_ok=True)
    Path("build/latest-export.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Created {record['name']!r}: {record['url']}")
    previous = os.environ.get("PREVIOUS_EXPORT", "")
    if previous and doc_id(previous) != created["id"]:
        try:
            stamp(previous, "NEW VERSION AVAILABLE - this Doc is outdated and read-only. Continue in:", record["name"],
                  record["url"])
            print(f"Marked the previous export {previous} as outdated and locked it.")
        except SystemExit as exc:  # the new Doc exists; a failed notice on the old one must not hide that
            print(f"Warning: could not mark the previous export {previous}: {exc}", file=sys.stderr)
        try:
            print(f"Moved the previous export into {archive(previous)}.")
        except SystemExit as exc:
            print(f"Warning: could not move the previous export {previous} into '{ARCHIVE}': {exc}", file=sys.stderr)


def cmd_login(client_file: str) -> None:
    """One-time: sign in in the browser and print the GOOGLE_OAUTH secret (instructions go to stderr)."""
    client = next(iter(json.loads(Path(client_file).read_text()).values()))  # {"installed": {...}}
    received = {}

    class Callback(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            received.update(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Signed in. You can close this tab and return to the terminal.".encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Callback)
    redirect = f"http://127.0.0.1:{server.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(dict(
        client_id=client["client_id"], redirect_uri=redirect, response_type="code", scope=SCOPE,
        access_type="offline", prompt="consent"))
    print(f"Opening the Google sign-in page. If it does not open, visit:\n{url}\n", file=sys.stderr)
    webbrowser.open(url)
    while "code" not in received and "error" not in received:
        server.handle_request()
    if "error" in received:
        sys.exit(f"Sign-in failed: {received['error']}")
    tokens = json.loads(call("POST", TOKEN_URL, urllib.parse.urlencode(dict(
        grant_type="authorization_code", code=received["code"], client_id=client["client_id"],
        client_secret=client["client_secret"], redirect_uri=redirect)).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"}))
    print(json.dumps({"client_id": client["client_id"], "client_secret": client["client_secret"],
                      "refresh_token": tokens["refresh_token"]}))
    print("\nDone. Store the line above as the GitHub secret GOOGLE_OAUTH, e.g.\n"
          "  python3 scripts/gdoc.py login client.json | gh secret set GOOGLE_OAUTH", file=sys.stderr)


if __name__ == "__main__":
    command, args = (sys.argv[1:2] or [""])[0], sys.argv[2:]
    if command == "export" and len(args) <= 2:
        cmd_export(*args)
    elif command in ("import", "login") and len(args) == 1:
        {"import": cmd_import, "login": cmd_login}[command](args[0])
    elif command == "stamp-import" and len(args) == 2:
        cmd_stamp_import(*args)
    else:
        sys.exit(__doc__)
