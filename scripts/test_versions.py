#!/usr/bin/env python3
"""Check versions.py against the version rules in admin.qmd, in a throwaway git repository."""
import os
import subprocess
import tempfile

import versions as v


def run(*args):
    subprocess.run(args, check=True, capture_output=True)


def change(path="_content.md"):
    with open(path, "a") as f:
        f.write("x\n")
    run("git", "add", path)
    run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "change")


def tag(name):
    run("git", "tag", name)


def refused(fn, *args):
    try:
        fn(*args)
    except SystemExit as exc:
        return str(exc)
    raise AssertionError(f"{fn.__name__}{args} should have been refused")


os.chdir(tempfile.mkdtemp())
run("git", "init", "-q")
ts = lambda: v.tags(fetch=False)

change()                                                    # first change after 1.0 (on Zenodo)
assert v.beta_tag(ts()) == "v1.1-beta.1"; tag("v1.1-beta.1")
assert "no release candidate" in refused(v.release_tag, ts(), False)
change(); tag(v.beta_tag(ts()))                             # v1.1-beta.2
assert v.rc_tag(ts(), major=False) == "v1.1-rc.1"; tag("v1.1-rc.1")
assert "Nothing has changed" in refused(v.rc_tag, ts(), False)
assert v.based_on(ts()) == "1.1-rc.1"                       # rc wins over the beta on the same commit
change(); tag(v.beta_tag(ts()))                             # betas keep counting after an rc
assert "v1.1-beta.3" in [t[4] for t in ts()]
assert "changed since 1.1-rc.1" in refused(v.release_tag, ts(), False)
assert v.rc_tag(ts(), major=True) == "v1.1-rc.2"            # major only counts for the first rc
tag("v1.1-rc.2")
change("admin.qmd")                                         # not the text: the candidate can still be released
assert v.release_tag(ts(), test=True) == ("v1.1-test.1", "v1.1-rc.2")
tag("v1.1-test.1")
assert v.release_tag(ts(), test=False) == ("v1.1", "v1.1-rc.2")   # sandbox tests do not count
tag("v1.1")
assert v.latest_release(ts()) == (1, 1) and v.target(ts()) == (1, 2)
assert v.based_on(ts()) == "1.1"
assert "Nothing has changed since 1.1" in refused(v.rc_tag, ts(), False)

change(); tag(v.beta_tag(ts()))                             # next cycle: betas count against 1.2 ...
assert "v1.2-beta.1" in [t[4] for t in ts()]
assert v.rc_tag(ts(), major=True) == "v2.0-rc.1"            # ... until the first rc chooses major
tag("v2.0-rc.1")
assert v.target(ts()) == (2, 0) and v.beta_tag(ts()) == "v2.0-beta.1"
assert v.release_tag(ts(), test=False) == ("v2.0", "v2.0-rc.1")
print("version rules OK")
