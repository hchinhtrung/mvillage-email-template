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
from .config import Config

__version__ = "0.4.0"

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
