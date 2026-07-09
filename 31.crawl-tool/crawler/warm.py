# -*- coding: utf-8 -*-
"""Browser layer.

  warm_capture()      — WARM once per hotel with the anti-detect engine (Camoufox by default),
                        capturing the real room-API request + cookies + apiKey for direct replay.
  browser_crawl_day() — reliable fallback: a normal browser nav that intercepts the room-API
                        RESPONSE (no request capture needed). Always chromium + stealth with a
                        fresh rotated context per attempt (proven for parallel week crawling).

Engine split rationale: Camoufox (Firefox) gives the strongest stealth exactly where blocks
happen — the one warm nav per hotel. The fallback opens many parallel contexts, which
chromium does cheaply, so it stays on chromium regardless of the warm engine.
"""
import asyncio
import contextlib
import json
import os
import random

from .session import pick_impersonate

# --- optional cookies.json (same format the old notebook used) ---
_cookie_cache = {}


def load_cookie_file(cfg):
    """Parse cfg.cookies_file into a playwright cookie list. Cached per absolute path;
    missing/broken file -> []."""
    path = getattr(cfg, "cookies_file", "") or ""
    if not path or not os.path.exists(path):
        return []
    key = os.path.abspath(path)
    if key not in _cookie_cache:
        cookies = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for c in raw:
                ck = {"name": c.get("name", ""), "value": c.get("value", ""),
                      "domain": c.get("domain", ".agoda.com"), "path": c.get("path", "/")}
                for opt in ("expires", "httpOnly", "secure"):
                    if c.get(opt):
                        ck[opt] = c[opt]
                if c.get("sameSite") in ("Strict", "Lax", "None"):
                    ck["sameSite"] = c["sameSite"]
                cookies.append(ck)
        except Exception:
            cookies = []
        _cookie_cache[key] = cookies
    return _cookie_cache[key]


async def add_cookie_file(ctx, cfg):
    cookies = load_cookie_file(cfg)
    if cookies:
        with contextlib.suppress(Exception):
            await ctx.add_cookies(cookies)

# --- chromium warm profiles: (User-Agent, curl_cffi chrome impersonate) matched pairs ---
WARM_PROFILES = [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "chrome131"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "chrome124"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "chrome120"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36", "chrome116"),
]
WARM_VIEWPORTS = [(1440, 900), (1536, 864), (1920, 1080), (1366, 768)]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]
SCREEN_RESOLUTIONS = [(1366, 768), (1440, 900), (1536, 864), (1600, 900), (1920, 1080), (1680, 1050)]


def _import_stealth():
    try:
        from playwright_stealth import Stealth
        return Stealth()
    except Exception:
        return None


def _launch_args(cfg):
    a = ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
    if cfg.headless:
        a.insert(0, "--headless=new")
    return a


def make_block_route(cfg):
    async def _route(route):
        try:
            if route.request.resource_type in cfg.block_resource_types:
                await route.abort()
            else:
                await route.continue_()
        except Exception:
            with contextlib.suppress(Exception):
                await route.continue_()
    return _route


@contextlib.asynccontextmanager
async def open_chromium(cfg):
    """Long-lived chromium + stealth, reused for the whole run (warm-when-chromium + fallback)."""
    from playwright.async_api import async_playwright
    stealth = _import_stealth()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=cfg.headless, args=_launch_args(cfg))
        try:
            yield browser, stealth
        finally:
            with contextlib.suppress(Exception):
                await browser.close()


async def _capture_on_context(adapter, ctx, hotel_url, checkin, cfg, stealth):
    """Navigate one context, capture the room-API request + a room-bearing response +
    cookies + apiKey + all xhr URLs. Returns a capture dict."""
    url = adapter.update_url_checkin(hotel_url, checkin)
    cap = {"req": None, "resp_json": None, "checkin": checkin.strftime("%Y-%m-%d"), "xhr_urls": []}
    page = await ctx.new_page()
    with contextlib.suppress(Exception):  # block heavy resources on either engine
        await page.route("**/*", make_block_route(cfg))

    def on_request(req):
        try:
            if adapter.api_hint in req.url:
                cap["req"] = {"method": req.method, "url": req.url,
                              "headers": dict(req.headers), "post_data": req.post_data}
            if req.resource_type in ("xhr", "fetch") and len(cap["xhr_urls"]) < 200:
                cap["xhr_urls"].append(req.url)
        except Exception:
            pass

    async def on_response(resp):
        try:
            if adapter.api_hint in resp.url and resp.status == 200:
                j = await resp.json()
                if adapter.response_has_rooms(j) or cap["resp_json"] is None:
                    cap["resp_json"] = j
        except Exception:
            pass

    _tasks = set()

    def _spawn(coro):
        t = asyncio.create_task(coro)
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)

    page.on("request", on_request)
    page.on("response", lambda r: _spawn(on_response(r)))
    try:
        if stealth is not None:
            with contextlib.suppress(Exception):
                await stealth.apply_stealth_async(page)
        await asyncio.sleep(random.uniform(0.3, 1.0))
        with contextlib.suppress(Exception):
            await page.goto(url, timeout=cfg.page_timeout_ms, wait_until="domcontentloaded")
        waited = 0.0
        while waited < cfg.api_wait_timeout_s:
            await asyncio.sleep(0.3)
            waited += 0.3
            with contextlib.suppress(Exception):
                await page.mouse.wheel(0, 1800)
            # definitive covers rooms AND genuine full-sold-out: a sold-out day would
            # otherwise burn the whole api_wait_timeout_s for a verdict we already hold
            if cap["req"] is not None and adapter.response_is_definitive(cap["resp_json"]):
                await asyncio.sleep(0.5)
                break
        with contextlib.suppress(Exception):
            cap["apiKey"] = await page.evaluate(
                "() => (window.environment && window.environment.apiKey) || null")
        with contextlib.suppress(Exception):
            storage = await ctx.storage_state()
            cap["cookies"] = [c for c in storage.get("cookies", [])
                              if adapter.name in (c.get("domain") or "")]
        with contextlib.suppress(Exception):
            cap["ua"] = await page.evaluate("() => navigator.userAgent")
    finally:
        with contextlib.suppress(Exception):
            await page.close()
    return cap


async def _new_camoufox_context(browser):
    """Camoufox may run a persistent context; prefer new_context, fall back to the existing one."""
    try:
        ctx = await browser.new_context(locale="en-GB", timezone_id="Asia/Ho_Chi_Minh")
        return ctx, True
    except Exception:
        try:
            ctxs = browser.contexts
            if ctxs:
                return ctxs[0], False
        except Exception:
            pass
        raise


@contextlib.asynccontextmanager
async def open_camoufox(cfg):
    """Long-lived Camoufox for a whole run — ONE browser launch instead of one per hotel
    (a Camoufox launch costs 5-10 s; across ~90 hotels that alone was ~10 minutes).
    Yields None when Camoufox is unavailable or crashes at startup; callers then downgrade
    to the chromium warm."""
    cm = browser = None
    try:
        from camoufox.async_api import AsyncCamoufox
        cm = AsyncCamoufox(headless=cfg.headless)
        browser = await cm.__aenter__()
    except Exception as e:
        print(f"  ⚠️ Camoufox unavailable ({type(e).__name__}: {e}) — chromium warm this run.",
              flush=True)
        cm = None
    try:
        yield browser
    finally:
        if cm is not None:
            with contextlib.suppress(Exception):
                await cm.__aexit__(None, None, None)


async def _warm_camoufox_on(adapter, browser, hotel_url, checkin, cfg, verbose):
    """Warm attempts on an already-running Camoufox browser (fresh context per attempt)."""
    stealth = None  # Camoufox is stealthy by itself
    cap = {"req": None, "resp_json": None, "checkin": checkin.strftime("%Y-%m-%d"), "xhr_urls": []}
    for attempt in range(2):
        ctx, own = await _new_camoufox_context(browser)
        try:
            cap = await _capture_on_context(adapter, ctx, hotel_url, checkin, cfg, stealth)
        finally:
            if own:
                with contextlib.suppress(Exception):
                    await ctx.close()
            else:
                with contextlib.suppress(Exception):
                    await ctx.clear_cookies()
        got_req = cap.get("req") is not None
        got_def = adapter.response_is_definitive(cap.get("resp_json"))
        if got_req and got_def:          # rooms OR genuine full-sold-out: capture is replayable
            cap["engine"] = "camoufox"
            cap["impersonate"] = pick_impersonate(cap.get("ua"), "camoufox", cfg.impersonate)
            if verbose:
                print(f"  ✅ warm OK (camoufox) | impersonate={cap['impersonate']}", flush=True)
            return cap
        if verbose:
            print(f"  ⟳ camoufox warm: req={got_req} definitive={got_def} → retry…", flush=True)
        await asyncio.sleep(random.uniform(*cfg.warm_backoff))
    cap["engine"] = "camoufox"
    cap["impersonate"] = pick_impersonate(cap.get("ua"), "camoufox", cfg.impersonate)
    return cap


async def _warm_camoufox(adapter, hotel_url, checkin, cfg, verbose):
    """Legacy one-shot warm (used by the CLI gates): launch Camoufox just for this capture."""
    try:
        from camoufox.async_api import AsyncCamoufox
    except Exception as e:
        if verbose:
            print(f"  ⚠️ Camoufox unavailable ({e}); falling back to chromium warm.", flush=True)
        return None
    async with AsyncCamoufox(headless=cfg.headless) as browser:
        return await _warm_camoufox_on(adapter, browser, hotel_url, checkin, cfg, verbose)


async def _warm_chromium(adapter, browser, hotel_url, checkin, cfg, stealth, verbose):
    last = {"req": None, "resp_json": None, "checkin": checkin.strftime("%Y-%m-%d"), "xhr_urls": []}
    n = min(cfg.warm_attempts, len(WARM_PROFILES))
    for attempt in range(n):
        ua, imp = WARM_PROFILES[attempt]
        vp = WARM_VIEWPORTS[attempt % len(WARM_VIEWPORTS)]
        ctx = await browser.new_context(viewport={"width": vp[0], "height": vp[1]}, user_agent=ua,
                                        locale="en-GB", timezone_id="Asia/Ho_Chi_Minh")
        await add_cookie_file(ctx, cfg)
        try:
            cap = await _capture_on_context(adapter, ctx, hotel_url, checkin, cfg, stealth)
        finally:
            with contextlib.suppress(Exception):
                await ctx.close()
        last = cap
        got_req = cap.get("req") is not None
        got_def = adapter.response_is_definitive(cap.get("resp_json"))
        if got_req and got_def:          # rooms OR genuine full-sold-out: capture is replayable
            cap["engine"] = "chromium"
            cap["ua"] = cap.get("ua") or ua
            cap["impersonate"] = pick_impersonate(cap.get("ua"), "chromium", cfg.impersonate) or imp
            if verbose:
                print(f"  ✅ warm OK (chromium {imp})", flush=True)
            return cap
        if verbose:
            print(f"  ⟳ chromium warm {imp}: req={got_req} definitive={got_def} → next profile…", flush=True)
        await asyncio.sleep(random.uniform(*cfg.warm_backoff))
    last["engine"] = "chromium"
    last["ua"] = last.get("ua") or WARM_PROFILES[0][0]
    last["impersonate"] = pick_impersonate(last.get("ua"), "chromium", cfg.impersonate) or WARM_PROFILES[0][1]
    return last


async def warm_capture(adapter, hotel_url, checkin, cfg, chromium=None, stealth=None,
                       camoufox_browser=None, verbose=False):
    """Warm once and return a capture dict {req, resp_json, checkin, apiKey, cookies, ua,
    impersonate, engine, xhr_urls}. Uses Camoufox when cfg.engine=='camoufox' (a long-lived
    browser via `camoufox_browser` when the caller has one, else a one-shot launch), else
    chromium."""
    if cfg.engine == "camoufox":
        try:
            if camoufox_browser is not None:
                cap = await _warm_camoufox_on(adapter, camoufox_browser, hotel_url, checkin,
                                              cfg, verbose)
            else:
                cap = await _warm_camoufox(adapter, hotel_url, checkin, cfg, verbose)
        except Exception as e:
            # Camoufox installed but crashed at runtime (e.g. Playwright<->Firefox version
            # mismatch). Degrade to the chromium warm instead of aborting the whole crawl.
            if verbose:
                print(f"  ⚠️ Camoufox runtime error ({type(e).__name__}: {e}); "
                      f"falling back to chromium warm.", flush=True)
            cap = None
        if cap is not None:
            return cap
        # Camoufox unavailable/failed -> chromium fallback below.
    if chromium is not None:
        return await _warm_chromium(adapter, chromium, hotel_url, checkin, cfg, stealth, verbose)
    async with open_chromium(cfg) as (browser, st):
        return await _warm_chromium(adapter, browser, hotel_url, checkin, cfg, st, verbose)


# --- per-hotel circuit breaker (ported from the notebook's BLOCK_CIRCUIT_LIMIT) ---
def new_breaker():
    """Shared per-hotel state: consecutive fully-blocked days trip it -> remaining days answer
    NA instantly instead of burning nav+wait timeouts. A hotel that responded once never trips."""
    return {"streak": 0, "ok": False, "tripped": False}


def breaker_note_ok(breaker):
    if breaker is not None:
        breaker["streak"], breaker["ok"] = 0, True


def breaker_note_block(breaker, limit, tag=""):
    """Returns True if this block tripped the breaker."""
    if breaker is None or breaker.get("ok"):
        return False
    breaker["streak"] = breaker.get("streak", 0) + 1
    if breaker["streak"] >= limit and not breaker.get("tripped"):
        breaker["tripped"] = True
        print(f"      ⛔ {tag}: blocked {breaker['streak']}× in a row → skip rest of hotel "
              f"(fast NA; cooldown rounds retry later)", flush=True)
        return True
    return False


# --- browser fallback (chromium, response-only) ---
async def _make_fallback_ctx(browser, cfg):
    res = random.choice(SCREEN_RESOLUTIONS)
    ctx = await browser.new_context(viewport={"width": res[0], "height": res[1]},
                                    user_agent=random.choice(USER_AGENTS),
                                    locale="en-GB", timezone_id="Asia/Ho_Chi_Minh")
    await ctx.route("**/*", make_block_route(cfg))
    await add_cookie_file(ctx, cfg)
    return ctx


async def browser_crawl_day(adapter, browser, hotel_url, room_type, checkin, cfg, stealth,
                            breaker=None, tag=""):
    """One check-in via a real browser nav. Fresh rotated context per attempt; retries only on
    a soft-block. Returns an extract verdict."""
    if breaker is not None and breaker.get("tripped"):   # hotel hard-blocked -> NA instantly
        return {"found": False, "soldOut": False, "blocked": True, "skipped": True}
    url = adapter.update_url_checkin(hotel_url, checkin)
    last = {"found": False, "soldOut": False, "blocked": True}
    for attempt in range(cfg.nav_attempts):
        ctx = await _make_fallback_ctx(browser, cfg)
        page = await ctx.new_page()
        cap = {}

        async def grab(resp):
            try:
                if adapter.api_hint in resp.url and resp.status == 200:
                    j = await resp.json()
                    if adapter.response_has_rooms(j) or "j" not in cap:
                        cap["j"] = j
            except Exception:
                pass

        _tasks = set()

        def _spawn(coro):
            t = asyncio.create_task(coro)
            _tasks.add(t)
            t.add_done_callback(_tasks.discard)

        page.on("response", lambda r: _spawn(grab(r)))
        try:
            if stealth is not None:
                with contextlib.suppress(Exception):
                    await stealth.apply_stealth_async(page)
            await asyncio.sleep(random.uniform(*cfg.nav_jitter))
            with contextlib.suppress(Exception):
                await page.goto(url, timeout=cfg.page_timeout_ms, wait_until="domcontentloaded")
            waited = 0.0
            while waited < cfg.api_wait_timeout_s:
                await asyncio.sleep(0.3)
                waited += 0.3
                with contextlib.suppress(Exception):
                    await page.mouse.wheel(0, 2200)
                if adapter.response_is_definitive(cap.get("j")):
                    await asyncio.sleep(0.6)
                    break
        finally:
            with contextlib.suppress(Exception):
                await page.close()
            with contextlib.suppress(Exception):
                await ctx.close()
        if "j" in cap:
            res = adapter.extract(cap["j"], room_type)
            last = res
            if not res.get("blocked"):
                breaker_note_ok(breaker)
                return res
        if attempt < cfg.nav_attempts - 1:
            if tag:
                print(f"      ⟳ {tag}: soft-blocked (empty rooms) — retry "
                      f"{attempt + 2}/{cfg.nav_attempts}…", flush=True)
            await asyncio.sleep(random.uniform(*cfg.retry_backoff))
    if last.get("blocked"):
        breaker_note_block(breaker, cfg.block_circuit_limit,
                           tag=tag or checkin.strftime("%Y-%m-%d"))
    return last
