#!/usr/bin/env python3
"""Version numbers of the Vision, derived from git tags only (rules: admin.qmd, "Version rules").

  vX.Y          release (citable, DOI)        vX.Y-rc.N     pre-release (release candidate)
  vX.Y-beta.N   accepted change to the text   vX.Y-test.N   Zenodo sandbox test release (not a version)

A cycle runs from one release to the next. Its target X.Y is chosen when exporting to Google Docs, travels
in the Doc's "Version" row and comes back with the import as `next_version` in the frontmatter; it must be
the next minor or next major version. Until one is chosen, the target is the next minor version.

  versions.py beta      print the tag for the change just merged (used by .github/workflows/beta.yml)
  versions.py status    print the current state
"""
import re
import subprocess
import sys
from pathlib import Path

TAG = re.compile(r"v(\d+)\.(\d+)(?:-(beta|rc|test)\.(\d+))?")
FIRST_RELEASE = (1, 0)  # 1.0 was published on Zenodo before this repository existed
# "The text": what a beta numbers and what must be unchanged between a release candidate and its release.
# Keep in sync with the paths in .github/workflows/beta.yml.
TEXT_PATHS = ["_content.md", "IPBES_Data_Vision.qmd", "media"]
QMD = Path("IPBES_Data_Vision.qmd")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def tags(fetch: bool = True) -> list:
    """[(major, minor, kind or None, n, name)] for all version tags."""
    if fetch:
        subprocess.run(["git", "fetch", "-q", "--tags", "--force", "origin"], capture_output=True)
    found = []
    for name in git("tag", "-l", "v*").split():
        m = TAG.fullmatch(name)
        if m:
            found.append((int(m[1]), int(m[2]), m[3], int(m[4] or 0), name))
    return found


def fmt(version: tuple) -> str:
    return f"{version[0]}.{version[1]}"


def latest_release(ts: list) -> tuple:
    return max([t[:2] for t in ts if t[2] is None], default=FIRST_RELEASE)


def allowed(ts: list) -> list:
    """Versions the next release may have: next minor, next major."""
    major, minor = latest_release(ts)
    return [(major, minor + 1), (major + 1, 0)]


def parse(text: str):
    m = re.fullmatch(r"\s*v?(\d+)\.(\d+)\s*", text or "")
    return (int(m[1]), int(m[2])) if m else None


def check(text: str, ts: list) -> tuple:
    """The version a user typed (e.g. "1.1"), or exit with the allowed choices."""
    version = parse(text)
    if version not in allowed(ts):
        minor, major = (fmt(v) for v in allowed(ts))
        sys.exit(f"The version must be {minor} (minor change) or {major} (major change), not {text!r}: "
                 f"the latest release is {fmt(latest_release(ts))}.")
    return version


def declared():
    """next_version from the frontmatter, if set."""
    m = re.search(r'^next_version:\s*"?([^"\n]*)"?\s*$', QMD.read_text(), re.M) if QMD.exists() else None
    return parse(m[1]) if m else None


def target(ts: list) -> tuple:
    """Version the current cycle works towards: next_version if still ahead, else the next minor."""
    version = declared()
    return version if version in allowed(ts) else allowed(ts)[0]


def latest(ts: list, version: tuple, kind: str):
    """Name of the highest-numbered tag of this kind for the version, or None."""
    same = [t for t in ts if t[:2] == version and t[2] == kind]
    return max(same, key=lambda t: t[3])[4] if same else None


def next_tag(ts: list, version: tuple, kind: str) -> str:
    n = max([t[3] for t in ts if t[:2] == version and t[2] == kind], default=0) + 1
    return f"v{fmt(version)}-{kind}.{n}"


def commit(ref: str) -> str:
    return git("rev-list", "-n", "1", ref)


def text_changed(since: str) -> bool:
    return subprocess.run(["git", "diff", "--quiet", since, "HEAD", "--", *TEXT_PATHS]).returncode != 0


def beta_tag(ts: list) -> str:
    return next_tag(ts, target(ts), "beta")


def rc_tag(ts: list) -> str:
    """Next release candidate."""
    released, version = latest_release(ts), target(ts)
    release_name = f"v{fmt(released)}"
    previous = latest(ts, version, "rc") or (release_name if release_name in [t[4] for t in ts] else None)
    if previous and commit(previous) == commit("HEAD"):
        sys.exit(f"Nothing has changed since {previous[1:]}; there is nothing new to pre-release.")
    return next_tag(ts, version, "rc")


def release_tag(ts: list, test: bool):
    """(tag, release candidate it promotes). The text must be exactly that of the latest candidate."""
    version = target(ts)
    candidate = latest(ts, version, "rc")
    if candidate is None:
        sys.exit(f"There is no release candidate for {fmt(version)} yet: make a pre-release first, then release it.")
    if text_changed(candidate):
        sys.exit(f"The text has changed since {candidate[1:]}. Make a new pre-release (release candidate), "
                 "check it, then release.")
    return (next_tag(ts, version, "test") if test else f"v{fmt(version)}"), candidate


def based_on(ts: list) -> str:
    """Version of the current text: the nearest tag, preferring release > rc > beta on the same commit."""
    try:
        nearest = git("describe", "--tags", "--abbrev=0", "--match", "v*", "--exclude", "*-test.*", "HEAD")
    except subprocess.CalledProcessError:
        return fmt(FIRST_RELEASE)
    rank = {None: 0, "rc": 1, "beta": 2}
    here = [t for t in ts if t[2] != "test" and commit(t[4]) == commit(nearest)]
    return min(here, key=lambda t: rank[t[2]])[4][1:] if here else nearest[1:]


if __name__ == "__main__":
    ts = tags()
    if sys.argv[1:] == ["beta"]:
        print(beta_tag(ts))
    elif sys.argv[1:] == ["status"]:
        version = target(ts)
        print(f"latest release {fmt(latest_release(ts))}; working towards {fmt(version)} "
              f"(latest pre-release {latest(ts, version, 'rc') or '-'}, latest beta {latest(ts, version, 'beta') or '-'}); "
              f"text is version {based_on(ts)}")
    else:
        sys.exit(__doc__)
