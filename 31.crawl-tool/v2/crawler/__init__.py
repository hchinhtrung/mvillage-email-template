# -*- coding: utf-8 -*-
"""
crawler — modern free direct-API price crawler for Agoda + Trip.com.

Architecture (see README.md):
  1) WARM once per hotel with an anti-detect browser (Camoufox, Firefox) to capture the
     real room-API request (method/url/headers/body) + cookies + apiKey.
  2) REPLAY every week x day directly via curl_cffi with TLS-fingerprint impersonation
     (Firefox target to match Camoufox) — ~1s/query instead of 30-60s of browser.
  3) BROWSER FALLBACK for any cell direct replay could not price (a soft-block is retried,
     never recorded as a price).

Public entry points:
  crawler.crawl(...)   -> synchronous wrapper (notebook friendly)
  crawler.arun(...)    -> async coroutine
  python -m crawler ... -> CLI (capture / replay / diag / crawl)
"""
import os as _os
import sys as _sys

# Keep Playwright's browser binaries OUT of ~/Library/Caches, which cache cleaners
# (e.g. `npx mac-cleaner-cli`) wipe — otherwise every clear forces a re-download and the
# "run playwright install" banner returns. setdefault semantics: an explicit
# PLAYWRIGHT_BROWSERS_PATH from the shell/launchd still wins. Playwright reads this at
# browser-launch time, so setting it here (before any warm.py import) is enough.
if not _os.environ.get("PLAYWRIGHT_BROWSERS_PATH") and _sys.platform == "darwin":
    _os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _os.path.expanduser(
        "~/Library/Application Support/ms-playwright")

from .config import Config

__version__ = "0.5.0-v2"  # hotels_parallel + speed knobs (see ../README.md)

__all__ = ["Config", "crawl", "arun", "__version__"]


def crawl(**kwargs):
    """Synchronous convenience wrapper around orchestrate.run().

    Usage from a notebook:
        import crawler
        crawler.crawl(site="agoda", input="agoda1.csv", weeks=6)
    """
    import asyncio
    from .orchestrate import run

    try:  # allow re-entrant loops inside Jupyter
        import nest_asyncio
        nest_asyncio.apply()
    except Exception:
        pass
    return asyncio.run(run(**kwargs))


async def arun(**kwargs):
    from .orchestrate import run
    return await run(**kwargs)
