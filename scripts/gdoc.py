#!/usr/bin/env python3
"""Move the Vision text between Google Docs and this repository (Python stdlib + openssl + Pandoc).

  gdoc.py import <doc link or id>   Google Doc -> _content.md (+ media/), title and editors in the .qmd
  gdoc.py export <doc link or id>   _content.md + title/editors -> replaces the content of that Google Doc

Google Doc convention (export writes it, import reads it):
  - the document title uses the "Title" paragraph style;
  - before the first heading, a line "Editors: Name (Institution, ORCID); Name (Institution)"
    and optionally "Contact: someone@example.org";
  - everything before the first heading (title, editors, table of contents) is not imported.

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
ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")


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


def parse_editors(line: str) -> list:
    """'A B (Inst, 0000-0002-...); C D (Inst)' -> [{name, institution, orcid}]."""
    items = line.split(";") if ";" in line or "(" in line else line.split(",")
    editors = []
    for item in filter(None, (i.strip() for i in items)):
        name, _, details = item.partition("(")
        details = details.rstrip(")")
        orcid = ORCID.search(details)
        institution = ", ".join(p.strip() for p in ORCID.sub("", re.sub(r"https?://orcid\.org/", "", details)).split(",")
                                if p.strip())
        editor = {"name": name.strip()}
        if institution:
            editor["institution"] = institution
        if orcid:
            editor["orcid"] = orcid.group(0)
        editors.append(editor)
    return editors


def format_editors(editors: list) -> str:
    return "; ".join(e["name"] + (f" ({', '.join(filter(None, [e.get('institution'), e.get('orcid')]))})"
                                  if e.get("institution") or e.get("orcid") else "") for e in editors)


def split_doc(markdown: str):
    """Split converted Doc Markdown into (front-matter lines, body from the first heading)."""
    lines = markdown.splitlines()
    toc = re.compile(r"^## (table of )?contents\b", re.I)  # a contents heading is still front matter
    first = next((i for i, line in enumerate(lines) if line.startswith("## ") and not toc.match(line)), None)
    if first is None:
        sys.exit("No headings found in the Google Doc; section titles must use Heading 1/2/3 styles.")
    return lines[:first], "\n".join(lines[first:]).strip() + "\n"


def clean_body(body: str) -> str:
    body = re.sub(r"\[\]\{#[^}]*\}", "", body)                              # empty bookmark anchors
    body = re.sub(r"^(#+ .*?)\s*\{[^}]*\}\s*$", r"\1", body, flags=re.M)     # heading ids from Google
    # Section numbers come from the templates, so drop typed ones ("I. Introduction", "2.1 Scope").
    return re.sub(r"^(#+ )(?:[IVXLC]+|\d+(?:\.\d+)*|[A-Z])[.)]?\s+(?=\S)", r"\1", body, flags=re.M)


def update_frontmatter(text: str, title: str, editors: list, contact: str) -> str:
    head, sep, rest = text.partition("\n---\n")
    if title:
        head = re.sub(r"^title: .*$", f"title: {json.dumps(title)}", head, count=1, flags=re.M)
    if editors:
        block = "editors:\n" + "".join(
            f"  - name: {json.dumps(e['name'])}\n" + "".join(f"    {k}: {json.dumps(e[k])}\n"
                                                         for k in ("institution", "orcid") if e.get(k))
            for e in editors)
        head = re.sub(r"^editors:\n(?:  .*\n?)*", block, head + "\n", count=1, flags=re.M).rstrip("\n")
    if contact:
        head = re.sub(r"^contact_email: .*$", f"contact_email: {json.dumps(contact)}", head, count=1, flags=re.M)
    return head + sep + rest


def cmd_import(link: str) -> None:
    token = access_token()
    docx = http("GET", f"https://www.googleapis.com/drive/v3/files/{doc_id(link)}/export?mimeType={DOCX}",
                headers={"Authorization": f"Bearer {token}"})
    import_docx(docx)


def import_docx(docx: bytes) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "doc.docx")
        path.write_bytes(docx)
        Path(tmp, "title.txt").write_text("$title$")
        title = pandoc(str(path), "-t", "plain", "--template", str(Path(tmp, "title.txt"))).strip()
        shutil.rmtree(MEDIA, ignore_errors=True)
        markdown = pandoc(str(path), "-t", "markdown-smart", "--wrap=none", "--shift-heading-level-by=1",
                          "--track-changes=accept", "--extract-media=.")
    front, body = split_doc(markdown)
    plain = [re.sub(r"[*_\\]", "", line).strip() for line in front]
    editors_line = next((l.split(":", 1)[1] for l in plain if re.match(r"(?i)(editors?|authors?)\s*:", l)), "")
    contact_line = next((l.split(":", 1)[1].strip() for l in plain if re.match(r"(?i)contact\s*:", l)), "")
    contact = re.sub(r"^<|>$|^mailto:", "", contact_line)
    editors = parse_editors(editors_line)

    CONTENT.write_text(clean_body(body))
    QMD.write_text(update_frontmatter(QMD.read_text(), title, editors, contact))
    print(f"Imported: title {title!r}; editors: {format_editors(editors) or '(none found, unchanged)'}; "
          f"contact: {contact or '(unchanged)'}; images: {len(list(MEDIA.glob('*'))) if MEDIA.exists() else 0}")


def export_docx() -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "meta.txt").write_text("$meta-json$")
        meta = json.loads(pandoc(str(QMD), "-t", "plain", "--template", str(Path(tmp, "meta.txt"))))
        head = f"Editors: {format_editors(meta.get('editors', []))}\n\nContact: {meta.get('contact_email', '')}\n\n"
        out = Path(tmp, "doc.docx")
        pandoc("-f", "markdown", "-o", str(out), "--shift-heading-level-by=-1", "--resource-path=.", "--toc",
               "-M", f"title={meta['title']}", stdin=head + CONTENT.read_text())
        return out.read_bytes()


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
