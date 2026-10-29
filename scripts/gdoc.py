#!/usr/bin/env python3
"""Move the Vision text between Google Docs and this repository (Python stdlib + openssl + Pandoc).

  gdoc.py import <doc link or id>   Google Doc -> _content.md (+ media/) and the bibliographic fields in the .qmd
  gdoc.py export <doc link or id>   bibliographic fields + _content.md -> replaces the content of that Google Doc

Google Doc layout (export writes it, import reads it). Everything before the first heading is front matter:
  - a "Document information" table, one row per field (FIELDS below), value in the second column;
  - an "Editors" table with the columns Name | Institution | ORCID, one row per editor;
  - anything else there (notes, table of contents) is ignored.
The text starts at the first Heading 1 that is not a table of contents.

Auth: GOOGLE_SERVICE_ACCOUNT_KEY holds the service account's JSON key; the Doc must be shared with
the service account's e-mail (Viewer for import, Editor for export).
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

QMD = Path("IPBES_Data_Vision.qmd")
CONTENT = Path("_content.md")
MEDIA = Path("media")
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# Row label in the "Document information" table -> frontmatter key. All rows are required.
FIELDS = {"Title": "title", "Produced by": "produced_by", "Publisher": "publisher", "Contact e-mail": "contact_email"}
EDITOR_COLUMNS = ["Name", "Institution", "ORCID"]
ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
NOTE = ("Edit the two tables below to change the bibliographic information; add or delete rows in the Editors "
        "table as needed. Do not rename the tables' first column. The text of the Vision starts at the first "
        "heading; this part is not copied into it.")


def doc_id(link: str) -> str:
    match = re.search(r"/d/([\w-]+)", link)
    return match.group(1) if match else link.strip()


def access_token() -> str:
    """OAuth token for the service account (JWT signed with openssl, no Google libraries)."""
    key = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"])
    b64 = lambda data: base64.urlsafe_b64encode(data).rstrip(b"=")
    now = int(time.time())
    claims = {"iss": key["client_email"], "scope": "https://www.googleapis.com/auth/drive",
              "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600}
    unsigned = b64(b'{"alg":"RS256","typ":"JWT"}') + b"." + b64(json.dumps(claims).encode())
    with tempfile.NamedTemporaryFile("w", suffix=".pem") as pem:
        pem.write(key["private_key"])
        pem.flush()
        signature = subprocess.run(["openssl", "dgst", "-sha256", "-sign", pem.name], input=unsigned,
                                   capture_output=True, check=True).stdout
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                   "assertion": (unsigned + b"." + b64(signature)).decode()}).encode()
    return json.loads(http("POST", "https://oauth2.googleapis.com/token", body,
                           {"Content-Type": "application/x-www-form-urlencoded"}))["access_token"]


def http(method: str, url: str, data: bytes = None, headers: dict = None) -> bytes:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers or {})) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        if exc.code in (403, 404):
            detail += ("\nIs the Google Doc shared with the service account "
                       f"({json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_KEY'])['client_email']})?")
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
            labels = {label.lower(): key for label, key in FIELDS.items()}
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
    body = pandoc("-f", "json", "-t", "markdown-smart", "--wrap=none", stdin=json.dumps(dict(doc, blocks=blocks[first:])))
    CONTENT.write_text(clean_body(body).strip() + "\n")
    QMD.write_text(update_frontmatter(QMD.read_text(), meta))
    editors = "; ".join(e["name"] for e in meta["editors"])
    print(f"Imported {meta['title']!r}; editors: {editors}; "
          f"images: {len(list(MEDIA.glob('*'))) if MEDIA.exists() else 0}")


def cell(value: str) -> str:
    return str(value or "").replace("|", "\\|")


def export_docx() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "meta.txt").write_text("$meta-json$")
        meta = json.loads(pandoc(str(QMD), "-t", "plain", "--template", str(Path(tmp, "meta.txt"))))
        front = [f"*{NOTE}*", "", "**Document information**", "", "| Field | Value |", "|---|---|"]
        front += [f"| {label} | {cell(meta.get(key))} |" for label, key in FIELDS.items()]
        front += ["", "**Editors**", "", "| " + " | ".join(EDITOR_COLUMNS) + " |", "|---|---|---|"]
        front += [f"| {cell(e.get('name'))} | {cell(e.get('institution'))} | {cell(e.get('orcid'))} |"
                  for e in meta.get("editors", [])]
        out = Path(tmp, "doc.docx")
        pandoc("-f", "markdown", "-o", str(out), "--shift-heading-level-by=-1", "--resource-path=.",
               stdin="\n".join(front) + "\n\n" + CONTENT.read_text())
        return out.read_bytes()


def cmd_import(link: str) -> None:
    token = access_token()
    import_docx(http("GET", f"https://www.googleapis.com/drive/v3/files/{doc_id(link)}/export?mimeType={DOCX}",
                     headers={"Authorization": f"Bearer {token}"}))


def cmd_export(link: str) -> None:
    target = doc_id(link)
    if target == doc_id(os.environ.get("GDOC_ID", "")):
        sys.exit("Refusing to overwrite the editing Google Doc (GDOC_ID). Export goes to the separate export Doc.")
    token = access_token()
    http("PATCH", f"https://www.googleapis.com/upload/drive/v3/files/{target}?uploadType=media&supportsAllDrives=true",
         export_docx(), {"Authorization": f"Bearer {token}", "Content-Type": DOCX})
    print(f"Exported to https://docs.google.com/document/d/{target}/edit")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("import", "export"):
        sys.exit(__doc__)
    {"import": cmd_import, "export": cmd_export}[sys.argv[1]](sys.argv[2])
