# -*- coding: utf-8 -*-
"""curl_cffi replay session: TLS-fingerprint impersonation + cookie jar + header hygiene.

TLS PAIRING (load-bearing): Akamai binds the `_abck` cookie to the TLS fingerprint that
created it. Camoufox is Firefox, so replay must impersonate Firefox. Chromium warm pairs
with a Chrome target. `pick_impersonate` derives the right target from the captured UA.
"""
import re

# Headers that must NOT be replayed verbatim (curl recomputes / owns them).
HEADER_DROP = {"cookie", "content-length", "host", "accept-encoding",
               "connection", "te", "upgrade-insecure-requests"}

# curl_cffi impersonate targets, newest first, per family.
_FIREFOX_TARGETS = [(147, "firefox147"), (144, "firefox144"),
                    (135, "firefox135"), (133, "firefox133")]
_CHROME_TARGETS = [(146, "chrome146"), (142, "chrome142"), (136, "chrome136"),
                   (133, "chrome133a"), (131, "chrome131"), (124, "chrome124"),
                   (120, "chrome120"), (116, "chrome116")]


def pick_impersonate(ua, engine="camoufox", override=""):
    """Choose the curl_cffi impersonate target matching the warm browser.

    Prefer an explicit override, else map the captured UA's browser major to the closest
    available target of the right family. Falls back to the generic family name (latest).
    """
    if override:
        return override
    ua = ua or ""
    is_firefox = engine == "camoufox" or ("Firefox" in ua and "Chrome" not in ua)
    if is_firefox:
        m = re.search(r"Firefox/(\d+)", ua)
        major = int(m.group(1)) if m else 0
        for v, t in _FIREFOX_TARGETS:
            if major >= v:
                return t
        return "firefox"
    m = re.search(r"Chrome/(\d+)", ua)
    major = int(m.group(1)) if m else 0
    for v, t in _CHROME_TARGETS:
        if major >= v:
            return t
    return "chrome"


def _fallback_chain(target):
    """Ordered impersonate targets to try if the preferred one is unavailable in the
    installed curl_cffi build."""
    fam = "firefox" if str(target).startswith("firefox") else "chrome"
    return [target, fam, "chrome" if fam == "firefox" else "firefox"]


def make_session(impersonate=None):
    try:
        from curl_cffi import AsyncSession
    except Exception:
        from curl_cffi.requests import AsyncSession
    for target in _fallback_chain(impersonate):
        if not target:
            continue
        try:
            return AsyncSession(impersonate=target)
        except Exception:
            continue
    return AsyncSession()


def load_cookies(sess, cookies, default_domain=".agoda.com"):
    for c in cookies or []:
        try:
            sess.cookies.set(c["name"], c["value"],
                             domain=c.get("domain", default_domain), path=c.get("path", "/"))
        except Exception:
            pass


def build_headers(cap_headers):
    """Drop HTTP/2 pseudo-headers (:authority, ...) and the headers curl owns."""
    h = {}
    for k, v in (cap_headers or {}).items():
        if k.lower() in HEADER_DROP or k.startswith(":"):
            continue
        h[k] = v
    return h
