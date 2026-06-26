# -*- coding: utf-8 -*-
"""
============================================================
 AGODA HYBRID CRAWLER (direct-API curl_cffi + browser fallback)  v0.3
============================================================
MỤC TIÊU: phủ GIÁ CHÍNH XÁC NHIỀU NHẤT có thể (coverage không bao giờ thấp hơn notebook cũ).

KIẾN TRÚC:
  1) DIRECT-API (nhanh): warm 1 lần/KS (Playwright) bắt request room-grid thật → replay 6 tuần bằng curl_cffi.
  2) BROWSER FALLBACK (tin cậy): ô nào direct KHÔNG ra giá thật (NA hoặc SOLD OUT nghi ngờ) → crawl lại bằng
     ĐÚNG phương pháp browser cũ (port nguyên từ "crawl price AGODA - 1.ipynb"): 7 ngày/tuần + xoay context/
     fingerprint NAV_ATTEMPTS lần. Browser là NGUỒN TIN CẬY: giá thật > SOLD OUT > NA.
  3) VÒNG 3: KS còn ô NA (bị chặn) → cooldown dài rồi browser-retry (port từ notebook).

→ KS dễ (còn phòng nhiều): direct lo hết, rất nhanh, không cần browser.
→ KS khó (Hilton/Wyndham/Novotel...): rơi xuống browser = bằng coverage bản cũ.

PHỤ THUỘC:  pip install -r requirements.txt  &&  playwright install chromium
CLI:
  python agoda_direct.py capture --url "<url>" [--room "..."]   # bắt 1 request thật
  python agoda_direct.py replay [--room "..."]                  # kiểm tra replay
  python agoda_direct.py diag   --url "<url>" --room "..."       # chẩn đoán 1 KS (warm vs replay)
  python agoda_direct.py crawl  --input ../thy/agoda5/agoda5.csv # crawl hybrid (mặc định TẤT CẢ KS × 6 tuần)
"""
import argparse
import asyncio
import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

# ============================================================
# CONFIG
# ============================================================
ROOM_API_HINT = "/api/v1/property/room-grid"
CURRENCY = "VND"
PRICE_TYPE = "final"
CHECKIN_OFFSET = 5            # W1 = hôm nay + 5 ngày
NUM_WEEKS = 6
DAYS_PER_WEEK = 7            # ⭐ PORT từ notebook (thử tới 7 ngày/tuần để tìm ra giá) — quan trọng cho coverage
HEADLESS = True
PAGE_TIMEOUT = 45000
API_WAIT_TIMEOUT = 25         # giây chờ room-grid có phòng

# --- direct-API (curl_cffi) ---
MAX_CONCURRENCY = 3           # trần đồng thời khi replay (giữ thấp để né rate-limit theo IP)
QUERY_JITTER = (0.6, 1.6)

# --- nhịp độ chung (PORT từ notebook) ---
BETWEEN_HOTELS = (2.0, 5.0)
NAV_JITTER = (0.3, 1.2)
INTRA_WEEK_DELAY = (0.5, 1.5)
RETRY_BACKOFF = (1.0, 2.5)

# --- browser fallback (PORT từ notebook) ---
WEEKS_PARALLEL = 2            # ⭐ 6→2: nhiều tuần song song = dễ bị chặn
NAV_ATTEMPTS = 2             # ⭐ thử lại điều hướng bằng CONTEXT MỚI (xoay UA/viewport) khi bị chặn

# --- VÒNG 3: retry KS bị chặn sau cooldown dài (PORT từ notebook) ---
RETRY_BLOCKED_HOTELS = True
MAX_BLOCK_ROUNDS = 2
BLOCK_COOLDOWN_BASE = 60      # giây ×số vòng (60s, 120s)
BLOCK_COOLDOWN_BETWEEN = (8.0, 15.0)

# Warm profiles: (User-Agent, curl_cffi impersonate) KHỚP NHAU — xoay tới khi bắt được session CÓ PHÒNG.
WARM_PROFILES = [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "chrome131"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "chrome124"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "chrome120"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36", "chrome116"),
]
WARM_VIEWPORTS = [(1440, 900), (1536, 864), (1920, 1080), (1366, 768)]
WARM_ATTEMPTS = 4             # số profile thử khi warm
WARM_BACKOFF = (1.5, 3.5)

# UA/độ phân giải cho BROWSER FALLBACK (PORT nguyên từ notebook)
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]
SCREEN_RESOLUTIONS = [(1366, 768), (1440, 900), (1536, 864), (1600, 900), (1920, 1080), (1680, 1050)]

JUNK_URL_PARAMS = {"searchrequestid", "ds", "searchtoken", "flightsearchcriteria",
                   "showreviewsubmissionentry", "iscalendarcallout"}
BLOCK_RESOURCE_TYPES = {"image", "media", "font"}
CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_capture")
HEADER_DROP = {"cookie", "content-length", "host", "accept-encoding",
               "connection", "te", "upgrade-insecure-requests"}

def _launch_args():
    a = ['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage']
    if HEADLESS:
        a.insert(0, '--headless=new')
    return a

# ============================================================
# PARSERS — COPY NGUYÊN VẸN TỪ NOTEBOOK (đã test với dữ liệu Agoda thật)
# ============================================================
def _to_int(s):
    n = re.sub(r'[^\d]', '', str(s) if s is not None else '')
    return int(n) if n else None

def parse_amount(text):
    if text is None:
        return None
    m = re.search(r'([\d][\d.,]{3,})', str(text))
    if not m:
        return None
    v = _to_int(m.group(1))
    return v if v and v >= 1000 else None

def fmt_price(v):
    return f"{v:,}"

def _norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', (s or '').lower()).strip()

def _tokens(s):
    return set(t for t in _norm(s).split() if t)

def _best_room(rooms, target):
    named = [(rm, (rm.get("name") or "").strip()) for rm in rooms]
    named = [(rm, n) for rm, n in named if n]
    if not named:
        return None
    tnorm = _norm(target)
    ttok = _tokens(target)
    for rm, n in named:
        if _norm(n) == tnorm:
            return rm
    tfirst = tnorm.split()[0] if tnorm else ""
    best, best_score = None, -1.0
    for rm, n in named:
        ntok = _tokens(n)
        if not ntok:
            continue
        score = len(ttok & ntok) / max(len(ttok | ntok), 1)
        nfirst = _norm(n).split()[0] if _norm(n) else ""
        if tfirst and tfirst == nfirst:
            score += 0.3
        if score > best_score:
            best_score, best = score, rm
    return best if best_score >= 0.5 else None

def agoda_offer_price(offer, ptype=PRICE_TYPE):
    pr = (offer or {}).get("price") or {}
    if ptype == "cashback":
        node = (pr.get("cashback") or {}).get("price") or {}
    else:
        node = pr.get(ptype) or {}
    v = node.get("amountNumber")
    if isinstance(v, (int, float)) and v >= 1000:
        return int(v)
    return parse_amount(node.get("amount") or node.get("text"))

def extract_from_agoda(rg, target_room, ptype=PRICE_TYPE):
    """found(price) | soldOut(thật) | blocked(rooms rỗng=bị chặn) | NA. rooms RỖNG = bị chặn, KHÔNG coi là SOLD OUT."""
    rg = rg or {}
    rooms = rg.get("rooms") or []
    if not rooms:
        if rg.get("isSoldOut") and rg.get("propertyName") and rg.get("searchCriteriaDescription"):
            return {"found": False, "soldOut": True, "fullSoldOut": True}
        return {"found": False, "soldOut": False, "blocked": True}
    rm = _best_room(rooms, target_room)
    if rm is not None:
        prices = [p for p in (agoda_offer_price(o, ptype) for o in (rm.get("offers") or [])) if p]
        if prices:
            return {"found": True, "price": fmt_price(min(prices)), "room": rm.get("name")}
        if rm.get("isSoldOut"):
            sp = parse_amount(rm.get("soldOutTitle"))
            if sp:
                return {"found": True, "price": fmt_price(sp), "room": rm.get("name"), "soldOutPrice": True}
            return {"found": False, "soldOut": True, "room": rm.get("name")}
        return {"found": False, "soldOut": False, "room": rm.get("name")}
    if rg.get("isSoldOut") and all(r.get("isSoldOut") for r in rooms):
        return {"found": False, "soldOut": True}
    return {"found": False, "soldOut": False, "rooms": [(r.get("name") or "") for r in rooms]}

def is_real(v):
    return v not in (None, "", "NA", "nan") and not str(v).startswith("SOLD OUT")

def update_url_checkin(url, checkin):
    ci = checkin.strftime("%Y-%m-%d")
    s = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
         if k.lower() not in JUNK_URL_PARAMS and k.lower() != "checkin"]
    q.append(("checkin", ci))
    low = {k.lower() for k, _ in q}
    if "los" not in low:
        q.append(("los", "1"))
    if "currencycode" not in low:
        q.append(("currencyCode", CURRENCY))
    if "finalpriceview" not in low:
        q.append(("finalPriceView", "1"))
    if "adults" not in low:
        q.append(("adults", "2"))
    if "rooms" not in low:
        q.append(("rooms", "1"))
    return urlunsplit((s.scheme, s.netloc, s.path, urlencode(q, safe=","), ""))

def save_backup_csv(all_week_prices, filename, num_weeks=NUM_WEEKS):
    """only-improve (không ghi NA đè giá thật) + atomic write."""
    import pandas as pd
    try:
        rows, written = [], set()
        if os.path.exists(filename):
            try:
                df_old = pd.read_csv(filename, keep_default_na=False, na_values=[])
                for _, row in df_old.iterrows():
                    k = (str(row.get("hotel_name", "")), str(row.get("room_type", "")))
                    written.add(k)
                    if k in all_week_prices:
                        nr = {"hotel_name": k[0], "room_type": k[1]}
                        for i in range(1, num_weeks + 1):
                            old = str(row.get(f"price_w{i}", "NA")).strip()
                            new = str(all_week_prices[k].get(f"Price W{i}", "NA")).strip()
                            if new in ("NA", "nan", "") and old not in ("NA", "nan", ""):
                                nr[f"price_w{i}"] = old
                            else:
                                nr[f"price_w{i}"] = new if new not in ("nan", "") else "NA"
                        rows.append(nr)
                    else:
                        rows.append(row.to_dict())
            except Exception:
                pass
        for (hotel, room), prices in all_week_prices.items():
            if (hotel, room) not in written:
                r = {"hotel_name": hotel, "room_type": room}
                for i in range(1, num_weeks + 1):
                    r[f"price_w{i}"] = prices.get(f"Price W{i}", "NA")
                rows.append(r)
        tmp = filename + ".tmp"
        pd.DataFrame(rows).to_csv(tmp, index=False, encoding="utf-8-sig")
        os.replace(tmp, filename)
    except Exception as e:
        print(f"❌ Error saving: {e}", flush=True)

def _resolve_input(path):
    if os.path.exists(path):
        return path
    import glob
    here = os.path.dirname(os.path.abspath(__file__))
    cands = glob.glob(os.path.join(here, "..", "**", os.path.basename(path)), recursive=True)
    return cands[0] if cands else path

def read_hotels_from_csv(file_path):
    import pandas as pd
    req = ['hotel_name', 'hotel_url', 'room_type']
    df = pd.read_csv(_resolve_input(file_path), encoding="utf-8-sig")
    if not all(c in df.columns for c in req):
        df.columns = req + list(df.columns[3:])
    df = df[df['hotel_url'].notna() & (df['hotel_url'] != '')]
    return [(r['hotel_name'], r['hotel_url'], r['room_type']) for _, r in df[req].iterrows()]

# ============================================================
# DIRECT REPLAY (curl_cffi)
# ============================================================
def _build_headers(cap_headers):
    h = {}
    for k, v in (cap_headers or {}).items():
        if k.lower() in HEADER_DROP or k.startswith(":"):
            continue
        h[k] = v
    return h

def _shift_dates(text, delta_days):
    """Dịch MỌI ngày YYYY-MM-DD đi delta_days (checkIn & checkOut dịch CÙNG nhau → giữ cửa sổ los)."""
    if not text or delta_days == 0:
        return text
    def repl(m):
        try:
            return (datetime.strptime(m.group(0), "%Y-%m-%d") + timedelta(days=delta_days)).strftime("%Y-%m-%d")
        except Exception:
            return m.group(0)
    return re.sub(r'\d{4}-\d{2}-\d{2}', repl, text)

def _parameterize(cap_req, orig_checkin, new_checkin):
    """⚠️ body Agoda chứa CẢ checkIn LẪN checkOut → phải dịch cả hai cùng delta, nếu không checkOut<checkIn → SOLD OUT giả."""
    try:
        delta = (datetime.strptime(new_checkin, "%Y-%m-%d") - datetime.strptime(orig_checkin, "%Y-%m-%d")).days
    except Exception:
        delta = 0
    method = cap_req["method"]
    url = _shift_dates(cap_req["url"], delta)
    headers = _build_headers(cap_req.get("headers"))
    data = _shift_dates(cap_req.get("post_data"), delta)
    return method, url, headers, data

def _make_session(impersonate=None):
    try:
        from curl_cffi import AsyncSession
    except Exception:
        from curl_cffi.requests import AsyncSession
    for target in (impersonate, "chrome"):
        if not target:
            continue
        try:
            return AsyncSession(impersonate=target)
        except Exception:
            continue
    return AsyncSession()

def _load_cookies(sess, cookies):
    for c in cookies or []:
        try:
            sess.cookies.set(c["name"], c["value"], domain=c.get("domain", ".agoda.com"), path=c.get("path", "/"))
        except Exception:
            pass

async def query_via_capture(sess, cap, checkin, timeout=30):
    method, url, headers, data = _parameterize(cap["req"], cap["checkin"], checkin.strftime("%Y-%m-%d"))
    try:
        if method.upper() == "POST":
            resp = await sess.post(url, headers=headers, data=data, timeout=timeout)
        else:
            resp = await sess.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        return None, {"_error": str(e)}
    try:
        j = resp.json()
    except Exception:
        j = None
    return resp.status_code, j

async def _direct_weeks(sess, cap, room_type, base_checkin, num_weeks, days):
    """Replay tất cả tuần bằng curl_cffi. Trả list {week, price}. SOLD OUT từ direct là 'nghi ngờ' (browser sẽ verify)."""
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    async def one_week(wn):
        week_start = base_checkin + timedelta(days=(wn - 1) * 7)
        sold = False
        for d in range(days):
            checkin = week_start + timedelta(days=d)
            async with sem:
                await asyncio.sleep(random.uniform(*QUERY_JITTER))
                st, j = await query_via_capture(sess, cap, checkin)
            res = extract_from_agoda(j or {}, room_type)
            if res.get("found"):
                return {"week": wn, "price": res["price"]}
            if res.get("soldOut"):
                sold = True
        return {"week": wn, "price": "SOLD OUT" if sold else "NA"}
    return await asyncio.gather(*[one_week(w) for w in range(1, num_weeks + 1)])

# ============================================================
# PLAYWRIGHT — WARM (cho direct) + BROWSER FALLBACK (PORT từ notebook)
# ============================================================
async def _block_route(route):
    try:
        if route.request.resource_type in BLOCK_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()
    except Exception:
        try:
            await route.continue_()
        except Exception:
            pass

async def _ctx_warm(browser, hotel_url, checkin, ua, viewport, stealth):
    """1 lần warm trên 1 context: navigate + bắt request room-grid thật + cookies + response."""
    url = update_url_checkin(hotel_url, checkin)
    cap = {"req": None, "resp_json": None, "checkin": checkin.strftime("%Y-%m-%d")}
    ctx = await browser.new_context(viewport={"width": viewport[0], "height": viewport[1]}, user_agent=ua,
                                    locale="en-GB", timezone_id="Asia/Ho_Chi_Minh")
    await ctx.route("**/*", _block_route)
    page = await ctx.new_page()

    def on_request(req):
        try:
            if ROOM_API_HINT in req.url:
                cap["req"] = {"method": req.method, "url": req.url,
                              "headers": dict(req.headers), "post_data": req.post_data}
        except Exception:
            pass

    async def on_response(resp):
        try:
            if ROOM_API_HINT in resp.url and resp.status == 200:
                j = await resp.json()
                if (j.get("rooms") or []) or cap["resp_json"] is None:
                    cap["resp_json"] = j
        except Exception:
            pass

    page.on("request", on_request)
    page.on("response", lambda r: asyncio.create_task(on_response(r)))
    try:
        if stealth is not None:
            await stealth.apply_stealth_async(page)
        await asyncio.sleep(random.uniform(0.3, 1.0))
        try:
            await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        except Exception:
            pass
        waited = 0.0
        while waited < API_WAIT_TIMEOUT:
            await asyncio.sleep(0.3)
            waited += 0.3
            try:
                await page.mouse.wheel(0, 1500)
            except Exception:
                pass
            if cap["req"] is not None and (cap["resp_json"] or {}).get("rooms"):
                await asyncio.sleep(0.5)
                break
        try:
            cap["apiKey"] = await page.evaluate(
                "() => (window.environment && window.environment.apiKey) || null")
        except Exception:
            cap["apiKey"] = None
        storage = await ctx.storage_state()
        cap["cookies"] = [c for c in storage.get("cookies", []) if "agoda" in (c.get("domain") or "")]
    finally:
        try:
            await ctx.close()
        except Exception:
            pass
    return cap

async def warm_capture_on_browser(browser, hotel_url, checkin, stealth, verbose=False, require_rooms=True):
    """Xoay WARM_PROFILES tới khi bắt được session TỐT (có request + response CÓ PHÒNG). Ghi lại profile thắng."""
    last = {"req": None, "resp_json": None, "checkin": checkin.strftime("%Y-%m-%d")}
    for attempt in range(min(WARM_ATTEMPTS, len(WARM_PROFILES))):
        ua, imp = WARM_PROFILES[attempt]
        viewport = WARM_VIEWPORTS[attempt % len(WARM_VIEWPORTS)]
        cap = await _ctx_warm(browser, hotel_url, checkin, ua, viewport, stealth)
        last = cap
        got_req = cap.get("req") is not None
        got_rooms = bool((cap.get("resp_json") or {}).get("rooms"))
        if got_req and (got_rooms or not require_rooms):
            cap["ua"], cap["impersonate"] = ua, imp
            if verbose:
                print(f"  ✅ warm OK (profile {imp}) | rooms={got_rooms}", flush=True)
            return cap
        if verbose:
            print(f"  ⟳ warm {imp}: req={got_req} rooms={got_rooms} → thử profile kế…", flush=True)
        await asyncio.sleep(random.uniform(*WARM_BACKOFF))
    last["ua"], last["impersonate"] = WARM_PROFILES[0]
    return last

async def warm_and_capture(hotel_url, checkin, save=True, verbose=True):
    """Phiên bản tự mở browser — dùng cho lệnh capture / diag."""
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import Stealth
        stealth = Stealth()
    except Exception:
        stealth = None
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, args=_launch_args())
        try:
            cap = await warm_capture_on_browser(browser, hotel_url, checkin, stealth,
                                                verbose=verbose, require_rooms=False)
        finally:
            try:
                await browser.close()
            except Exception:
                pass
    if cap.get("req") is not None:
        if verbose:
            r = cap["req"]
            print(f"  ✅ Bắt được room-grid (profile {cap.get('impersonate')}): {r['method']} {r['url'][:80]}…", flush=True)
            print(f"     body POST: {'CÓ' if r['post_data'] else 'KHÔNG (GET)'} | #cookies: {len(cap.get('cookies', []))}"
                  f" | response có rooms: {bool((cap.get('resp_json') or {}).get('rooms'))}", flush=True)
        if save:
            os.makedirs(CAPTURE_DIR, exist_ok=True)
            with open(os.path.join(CAPTURE_DIR, "capture.json"), "w", encoding="utf-8") as f:
                json.dump(cap, f, ensure_ascii=False, indent=2)
            if verbose:
                print(f"     💾 Đã lưu {os.path.join(CAPTURE_DIR, 'capture.json')}", flush=True)
    elif verbose:
        print("  ❌ Mọi profile đều fail. Thử lại / đổi IP (4G) / HEADLESS=False.", flush=True)
    return cap

# --- BROWSER FALLBACK: crawl_day / crawl_week PORT nguyên từ notebook (đã kiểm chứng) ---
async def _make_ctx_browser(browser):
    res = random.choice(SCREEN_RESOLUTIONS)
    ctx = await browser.new_context(viewport={"width": res[0], "height": res[1]},
                                    user_agent=random.choice(USER_AGENTS),
                                    locale="en-GB", timezone_id="Asia/Ho_Chi_Minh")
    await ctx.route("**/*", _block_route)
    return ctx

async def browser_crawl_day(browser, hotel_url, room_type, checkin, stealth):
    """Mở 1 ngày, bắt response room-grid CÓ PHÒNG. Thử lại bằng CONTEXT MỚI (xoay UA/viewport) khi bị chặn."""
    url = update_url_checkin(hotel_url, checkin)
    last = {"found": False, "soldOut": False, "blocked": True}
    for attempt in range(NAV_ATTEMPTS):
        ctx = await _make_ctx_browser(browser)
        page = await ctx.new_page()
        cap = {}

        async def grab(resp):
            try:
                if ROOM_API_HINT in resp.url and resp.status == 200:
                    j = await resp.json()
                    if (j.get("rooms") or []) or "j" not in cap:
                        cap["j"] = j
            except Exception:
                pass

        page.on("response", lambda r: asyncio.create_task(grab(r)))
        try:
            if stealth is not None:
                await stealth.apply_stealth_async(page)
            await asyncio.sleep(random.uniform(*NAV_JITTER))
            try:
                await page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
            except Exception:
                pass
            waited = 0.0
            while waited < API_WAIT_TIMEOUT:
                await asyncio.sleep(0.3)
                waited += 0.3
                try:
                    await page.mouse.wheel(0, 1500)
                except Exception:
                    pass
                if (cap.get("j") or {}).get("rooms"):
                    await asyncio.sleep(0.6)
                    break
        finally:
            try:
                await page.close()
            except Exception:
                pass
            try:
                await ctx.close()
            except Exception:
                pass
        if "j" in cap:
            res = extract_from_agoda(cap["j"], room_type)
            last = res
            if not res.get("blocked"):
                return res
        if attempt < NAV_ATTEMPTS - 1:
            await asyncio.sleep(random.uniform(*RETRY_BACKOFF))
    return last

async def browser_crawl_week(browser, hotel_url, room_type, week_num, base_checkin, stealth, days=DAYS_PER_WEEK):
    week_start = base_checkin + timedelta(days=(week_num - 1) * 7)
    sold = False
    for d in range(days):
        checkin = week_start + timedelta(days=d)
        res = await browser_crawl_day(browser, hotel_url, room_type, checkin, stealth)
        if res.get("found"):
            return {"week": week_num, "price": res["price"]}
        if res.get("soldOut"):
            sold = True
        if d < days - 1:
            await asyncio.sleep(random.uniform(*INTRA_WEEK_DELAY))
    return {"week": week_num, "price": "SOLD OUT" if sold else "NA"}

# ============================================================
# HYBRID PER-HOTEL
# ============================================================
async def crawl_hotel_hybrid(browser, stealth, hotel_name, url, room_type, base_checkin, num_weeks,
                             weeks_wanted=None):
    """1) direct-API replay; 2) browser fallback cho ô CHƯA có giá thật (NA + SOLD OUT nghi ngờ).
    Trả (prices, direct_got, fallback_count, still_blocked_weeks)."""
    prices = {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
    want = weeks_wanted or list(range(1, num_weeks + 1))

    # PHASE A+B: warm + direct replay (chỉ khi cần nhiều tuần — warm theo W1)
    cap = await warm_capture_on_browser(browser, url, base_checkin, stealth, verbose=False, require_rooms=True)
    direct_got = 0
    if cap.get("req") is not None:
        sess = _make_session(cap.get("impersonate"))
        _load_cookies(sess, cap.get("cookies"))
        try:
            direct = await _direct_weeks(sess, cap, room_type, base_checkin, num_weeks, DAYS_PER_WEEK)
        finally:
            try:
                await sess.close()
            except Exception:
                pass
        for r in direct:
            if r["week"] not in want:
                continue
            if is_real(r["price"]):
                prices[f"Price W{r['week']}"] = r["price"]
                direct_got += 1
            elif str(r["price"]).startswith("SOLD OUT"):
                prices[f"Price W{r['week']}"] = r["price"]   # tạm ghi, browser sẽ verify

    # PHASE C: browser fallback cho ô CHƯA có GIÁ THẬT (browser = nguồn tin cậy)
    need = [w for w in want if not is_real(prices[f"Price W{w}"])]
    fallback_count = len(need)
    still_blocked = []
    if need:
        sem = asyncio.Semaphore(WEEKS_PARALLEL)
        async def one(wn):
            async with sem:
                return await browser_crawl_week(browser, url, room_type, wn, base_checkin, stealth, days=DAYS_PER_WEEK)
        res = await asyncio.gather(*[one(w) for w in need])
        for r in res:
            wn, new = r["week"], r["price"]
            old = prices[f"Price W{wn}"]
            if is_real(new):
                prices[f"Price W{wn}"] = new                 # giá thật
            elif str(new).startswith("SOLD OUT"):
                prices[f"Price W{wn}"] = "SOLD OUT"          # browser xác nhận sold-out thật
            else:
                still_blocked.append(wn)                      # browser vẫn NA → bị chặn → để VÒNG 3
                if not str(old).startswith("SOLD OUT"):
                    prices[f"Price W{wn}"] = "NA"
    return prices, direct_got, fallback_count, still_blocked

# ============================================================
# GATE RUNNERS
# ============================================================
async def gate0_capture(args):
    bc = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=CHECKIN_OFFSET)
    print(f"🔥 GATE 0 — warm + capture (checkin={bc.strftime('%Y-%m-%d')})", flush=True)
    cap = await warm_and_capture(args.url, bc, save=True)
    if cap.get("req") is not None and args.room:
        print(f"  🔎 Sanity giá '{args.room}': {extract_from_agoda(cap.get('resp_json') or {}, args.room)}", flush=True)

async def gate1_replay(args):
    path = os.path.join(CAPTURE_DIR, "capture.json")
    if not os.path.exists(path):
        print("❌ chưa có capture.json — chạy 'capture' trước.", flush=True); return
    with open(path, encoding="utf-8") as f:
        cap = json.load(f)
    sess = _make_session(cap.get("impersonate"))
    _load_cookies(sess, cap.get("cookies"))
    try:
        bc = datetime.strptime(cap["checkin"], "%Y-%m-%d")
        print(f"🧪 GATE 1a — replay VERBATIM (impersonate={cap.get('impersonate')}):", flush=True)
        st, j = await query_via_capture(sess, cap, bc)
        print(f"     status={st} | rooms={bool((j or {}).get('rooms'))}", flush=True)
        if args.room:
            print(f"     giá '{args.room}': {extract_from_agoda(j or {}, args.room)}", flush=True)
        bc2 = bc + timedelta(days=14)
        print(f"🧪 GATE 1b — replay ĐỔI CHECKIN {bc2.strftime('%Y-%m-%d')}:", flush=True)
        st2, j2 = await query_via_capture(sess, cap, bc2)
        print(f"     status={st2} | rooms={bool((j2 or {}).get('rooms'))}", flush=True)
    finally:
        try:
            await sess.close()
        except Exception:
            pass

def _summarize_resp(tag, j):
    j = j or {}
    rooms = j.get("rooms") or []
    print(f"  [{tag}] #rooms={len(rooms)} | isSoldOut={j.get('isSoldOut')} | hasPropertyName={bool(j.get('propertyName'))}"
          f" | hasSearchCrit={bool(j.get('searchCriteriaDescription'))} | keys={list(j.keys())[:7]}", flush=True)
    if rooms:
        print(f"        tên phòng (mẫu): {[(r.get('name') or '')[:38] for r in rooms[:8]]}", flush=True)

async def gate_diag(args):
    """So warm-response (browser) vs curl_cffi replay cùng ngày → tìm nguyên nhân SOLD OUT/NA."""
    bc = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=CHECKIN_OFFSET)
    print(f"🔬 DIAG | {args.url[:70]}…\n   room='{args.room}' | checkin warm={bc.strftime('%Y-%m-%d')}", flush=True)
    cap = await warm_and_capture(args.url, bc, save=False, verbose=True)
    if cap.get("req") is None:
        print("⛔ warm fail toàn bộ profile.", flush=True); return
    print("\n── (1) RESPONSE BROWSER NHẬN LÚC WARM ──", flush=True)
    _summarize_resp("warm", cap.get("resp_json"))
    print(f"  extract '{args.room}': {extract_from_agoda(cap.get('resp_json') or {}, args.room)}", flush=True)
    sess = _make_session(cap.get("impersonate"))
    _load_cookies(sess, cap.get("cookies"))
    try:
        print("\n── (2) RESPONSE curl_cffi REPLAY ──", flush=True)
        for label, dd in [("replay W1 (cùng ngày)", 0), ("replay W3 (+14d)", 14)]:
            st, j = await query_via_capture(sess, cap, bc + timedelta(days=dd))
            print(f"\n  ▶ {label}: HTTP {st}", flush=True)
            _summarize_resp(label, j)
            print(f"     extract '{args.room}': {extract_from_agoda(j or {}, args.room)}", flush=True)
    finally:
        try:
            await sess.close()
        except Exception:
            pass

async def gate2_crawl(args):
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import Stealth
        stealth = Stealth()
    except Exception:
        stealth = None
    t0 = time.time()
    num_weeks = args.weeks or NUM_WEEKS
    hotels = read_hotels_from_csv(args.input)
    if args.max:
        hotels = hotels[:args.max]
    bc = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=CHECKIN_OFFSET)
    out = f"DIRECT_{datetime.today().strftime('%Y%m%d')}.csv"
    temp = "TEMP_DIRECT_" + os.path.basename(args.input)

    # resume: nạp kết quả cũ (only-improve sẽ giữ giá thật)
    awp, prev = {}, {}
    if os.path.exists(temp):
        try:
            import pandas as pd
            dp = pd.read_csv(temp, keep_default_na=False, na_values=[])
            for _, row in dp.iterrows():
                k = (str(row.get("hotel_name", "")), str(row.get("room_type", "")))
                p = {f"Price W{i}": (str(row.get(f"price_w{i}", "NA")).strip() or "NA") for i in range(1, num_weeks + 1)}
                prev[k] = p; awp[k] = dict(p)
            print(f"📂 Resume: nạp {len(prev)} dòng từ {temp}", flush=True)
        except Exception:
            pass

    print(f"🚀 HYBRID crawl | {len(hotels)} KS × {num_weeks} tuần | direct trước, browser fallback | W1={bc.strftime('%Y-%m-%d')}", flush=True)
    blocked_keys = set()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, args=_launch_args())
        try:
            for idx, (hn, hu, rt) in enumerate(hotels, 1):
                key = (hn, rt)
                # bỏ qua nếu đã đủ giá thật mọi tuần
                if key in prev and all(is_real(prev[key].get(f"Price W{i}", "NA")) for i in range(1, num_weeks + 1)):
                    print(f"✔️  {idx}/{len(hotels)} {hn} — đã đủ, bỏ qua", flush=True)
                    continue
                want = [i for i in range(1, num_weeks + 1) if not (key in prev and is_real(prev[key].get(f"Price W{i}", "NA")))]
                print(f"\n🏨 {idx}/{len(hotels)} {hn} | {rt} | cần: {want}", flush=True)
                try:
                    prices, dgot, nfb, blk = await crawl_hotel_hybrid(browser, stealth, hn, hu, rt, bc, num_weeks, want)
                except Exception as e:
                    print(f"   ❌ {e}", flush=True)
                    prices = awp.get(key) or {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
                    dgot, nfb, blk = 0, 0, want
                # merge only-improve vào awp
                cur = awp.get(key) or {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
                for i in range(1, num_weeks + 1):
                    new = prices.get(f"Price W{i}", "NA")
                    if is_real(new) or (str(new).startswith("SOLD OUT") and not is_real(cur.get(f"Price W{i}", "NA"))):
                        cur[f"Price W{i}"] = new
                awp[key] = cur
                if blk:
                    blocked_keys.add(key)
                got = sum(1 for i in range(1, num_weeks + 1) if is_real(cur[f"Price W{i}"]))
                print(f"   {'✅' if got == num_weeks else '⚠️'} {got}/{num_weeks} có giá (direct {dgot} ô, browser fallback {nfb} ô)", flush=True)
                save_backup_csv(awp, temp, num_weeks)
                await asyncio.sleep(random.uniform(*BETWEEN_HOTELS))

            # ----- VÒNG 3: retry KS còn bị chặn sau COOLDOWN dài (browser, KHÔNG bỏ cuộc) -----
            if RETRY_BLOCKED_HOTELS and blocked_keys:
                ki = {(h, r): (h, u, r) for (h, u, r) in hotels}
                for rnd in range(1, MAX_BLOCK_ROUNDS + 1):
                    still = {k: [i for i in range(1, num_weeks + 1) if not is_real(awp[k].get(f"Price W{i}", "NA"))]
                             for k in blocked_keys if k in ki}
                    still = {k: v for k, v in still.items() if v}
                    if not still:
                        break
                    cd = BLOCK_COOLDOWN_BASE * rnd
                    print(f"\n🧊 VÒNG 3.{rnd}/{MAX_BLOCK_ROUNDS}: {len(still)} KS bị chặn — nghỉ {cd}s rồi browser-retry…", flush=True)
                    await asyncio.sleep(cd)
                    for k, weeks in still.items():
                        hn, hu, rt = ki[k]
                        sem = asyncio.Semaphore(WEEKS_PARALLEL)
                        async def one(wn):
                            async with sem:
                                return await browser_crawl_week(browser, hu, rt, wn, bc, stealth, days=DAYS_PER_WEEK)
                        res = await asyncio.gather(*[one(w) for w in weeks])
                        for r in res:
                            new = r["price"]; old = awp[k].get(f"Price W{r['week']}", "NA")
                            if is_real(new) or (str(new).startswith("SOLD OUT") and not is_real(old)):
                                awp[k][f"Price W{r['week']}"] = new
                        save_backup_csv(awp, temp, num_weeks)
                        await asyncio.sleep(random.uniform(*BLOCK_COOLDOWN_BETWEEN))
        finally:
            try:
                await browser.close()
            except Exception:
                pass

    save_backup_csv(awp, out, num_weeks)
    tc = len(awp) * num_weeks
    na = sum(1 for pp in awp.values() for i in range(1, num_weeks + 1) if pp.get(f"Price W{i}", "NA") == "NA")
    so = sum(1 for pp in awp.values() for i in range(1, num_weeks + 1) if str(pp.get(f"Price W{i}", "")).startswith("SOLD OUT"))
    tt = time.time() - t0
    print(f"\n{'='*60}", flush=True)
    print(f"✅ {out} | giá {tc-na-so}/{tc} ({(tc-na-so)/max(tc,1):.1%}) | 🚫 {so} SO | ❌ {na} NA", flush=True)
    print(f"⏱️ {int(tt//60)}m {int(tt%60)}s cho {len(awp)} KS × {num_weeks} tuần", flush=True)
    print(f"{'='*60}", flush=True)

def main():
    ap = argparse.ArgumentParser(description="Agoda hybrid crawler (curl_cffi direct + browser fallback)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture", help="warm + bắt 1 request room-grid thật")
    c.add_argument("--url", required=True)
    c.add_argument("--room", default="")
    r = sub.add_parser("replay", help="kiểm tra replay verbatim + đổi ngày")
    r.add_argument("--room", default="")
    dg = sub.add_parser("diag", help="chẩn đoán 1 KS: warm-response vs curl_cffi replay")
    dg.add_argument("--url", required=True)
    dg.add_argument("--room", required=True)
    g = sub.add_parser("crawl", help="crawl hybrid (direct + browser fallback)")
    g.add_argument("--input", default="agoda1.csv", help="CSV input (tự dò trong 31.crawl-tool)")
    g.add_argument("--max", type=int, default=0, help="số KS tối đa (0 = tất cả)")
    g.add_argument("--weeks", type=int, default=0, help="số tuần (0 = 6)")
    args = ap.parse_args()
    asyncio.run({"capture": gate0_capture, "replay": gate1_replay,
                 "diag": gate_diag, "crawl": gate2_crawl}[args.cmd](args))

if __name__ == "__main__":
    main()
