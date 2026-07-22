# -*- coding: utf-8 -*-
"""Environment preflight — answers "does THIS interpreter have everything installed?".

Packages live per-interpreter, not per-folder: `.venv/bin/python` and the system python each
have their own site-packages, so "the package is installed" only means something relative to
the python that is actually running. This burned us once: camoufox's browser binary existed
on disk but the package was missing from `.venv`, the import error was swallowed, and every
hotel silently fell back to the slower chromium warm. This module makes that visible:

    python -m crawler doctor      # full ✅/⚠️/❌ report + exact install commands
    orchestrate.run(...)          # runs check() automatically: prints only problems and
                                  # aborts early when a REQUIRED package is missing
"""
import glob
import importlib.util
import os
import sys

# (import name, pip requirement, what it is for, required?)
PACKAGES = [
    ("curl_cffi",          "curl_cffi",         "direct replay (TLS impersonation)", True),
    ("playwright",         "playwright",        "browser warm + fallback",           True),
    ("pandas",             "pandas",            "CSV / Google-Sheet I/O",            True),
    ("camoufox",           "'camoufox[geoip]'", "anti-detect Firefox warm (Agoda)",  False),
    ("playwright_stealth", "playwright-stealth", "chromium stealth patches",         False),
    ("openpyxl",           "openpyxl",          ".xlsx hotel lists",                 False),
    ("nest_asyncio",       "nest-asyncio",      "running from Jupyter notebooks",    False),
]


def has(import_name):
    """True if `import_name` is importable by THIS interpreter. Uses find_spec, so nothing
    is actually imported and a heavy package costs nothing to probe."""
    try:
        return importlib.util.find_spec(import_name) is not None
    except Exception:
        return False


def version_of(import_name):
    try:
        from importlib.metadata import version, packages_distributions
        # metadata wants the DISTRIBUTION name (nest-asyncio), not the import name
        # (nest_asyncio); packages_distributions() maps between the two.
        dists = packages_distributions().get(import_name) or [import_name]
        return version(dists[0])
    except Exception:
        return "?"


def venv_hint():
    """Non-empty warning when a project .venv exists but THIS interpreter is not it —
    the classic way to 'have' a package yet not have it at runtime. Compares sys.prefix
    (which a venv interpreter reports as the venv dir) rather than sys.executable, whose
    realpath resolves through the venv symlink to the base python binary."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # .../31.crawl-tool
    venv = os.path.realpath(os.path.join(root, ".venv"))
    if os.path.isdir(venv) and os.path.realpath(sys.prefix) != venv:
        return (f"running {sys.executable}, not the project venv — packages are "
                f"per-interpreter; use {os.path.join(venv, 'bin', 'python')}")
    return ""


def camoufox_browser_ok():
    """The pip package and the ~300MB Firefox binary install separately; check both."""
    try:
        from camoufox.pkgman import installed_verstr
        return bool(installed_verstr())
    except Exception:
        return False


def chromium_browser_ok():
    """Best-effort: look for a chromium build in playwright's browser cache."""
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not root:
        if sys.platform == "darwin":
            root = os.path.expanduser("~/Library/Caches/ms-playwright")
        elif os.name == "nt":
            root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")
        else:
            root = os.path.expanduser("~/.cache/ms-playwright")
    return bool(glob.glob(os.path.join(root, "chromium*")))


def pip_hint(reqs):
    """The exact install command for THIS interpreter (never a bare `pip`, which may
    belong to a different python)."""
    return f"{sys.executable} -m pip install -U " + " ".join(reqs)


def check(verbose=True):
    """Report environment status. Returns the list of missing REQUIRED pip requirements
    (empty = safe to crawl). With verbose=False only problems are printed."""
    ok_lines, problems, missing_required = [], [], []
    for imp, pipname, why, required in PACKAGES:
        if has(imp):
            ok_lines.append(f"  ✅ {imp:<19}{version_of(imp):<11}— {why}")
            continue
        mark, sev = ("❌", "REQUIRED") if required else ("⚠️", "optional")
        problems.append(f"  {mark} {imp:<19}missing ({sev}) — {why} → pip install -U {pipname}")
        if required:
            missing_required.append(pipname)
    if has("camoufox") and not camoufox_browser_ok():
        problems.append("  ⚠️ camoufox browser binary missing → python -m camoufox fetch")
    if has("playwright") and not chromium_browser_ok():
        problems.append("  ⚠️ playwright chromium not found → python -m playwright install chromium")
    hint = venv_hint()
    if hint:
        problems.append(f"  ⚠️ {hint}")

    if verbose:
        print(f"🩺 interpreter: {sys.executable}", flush=True)
        for ln in ok_lines:
            print(ln, flush=True)
    if problems:
        if not verbose:
            print(f"🩺 env problems ({sys.executable}):", flush=True)
        for ln in problems:
            print(ln, flush=True)
    elif verbose:
        print("  🎉 all packages + browser binaries present", flush=True)
    return missing_required
