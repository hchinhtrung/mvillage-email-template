# -*- coding: utf-8 -*-
"""
============================================================
 AGODA DIRECT-API CRAWLER — PROTOTYPE (curl_cffi)  v0.2
============================================================
Hướng đi MỚI so với notebook hiện tại:
  • Notebook cũ: mở 1 trình duyệt Chromium THẬT cho TỪNG query → chậm (~30–60s/giá), dễ bị bắt bot lúc điều hướng.
  • Prototype này: dùng Playwright 1 LẦN/khách sạn để "mồi" (warm) session room-grid thật (method + headers + body + cookies + apiKey),
    rồi REPLAY thẳng request đó bằng curl_cffi (giả vân tay TLS/JA3 + HTTP2 của Chrome thật) cho 6 tuần → mỗi query ~1s.

Tái sử dụng NGUYÊN VẸN các parser đã kiểm chứng từ "crawl price AGODA - 1.ipynb":
  parse_amount, fmt_price, _best_room, agoda_offer_price, extract_from_agoda, is_real, update_url_checkin, save_backup_csv.
  → Giữ y nguyên logic phân biệt blocked-vs-SOLD-OUT (rooms rỗng + thiếu propertyName = bị chặn, KHÔNG ghi SOLD OUT).

CÁC GATE (chạy theo thứ tự để tự kiểm chứng TRƯỚC khi nhân rộng):
  python agoda_direct.py capture --url "<agoda hotel url>" [--room "Narra Double"]   # Gate 0: warm + bắt 1 request room-grid thật
  python agoda_direct.py replay                                                      # Gate 1: replay verbatim + replay đổi ngày
  python agoda_direct.py crawl  --input ../agoda/agoda1/agoda1.csv --max 5 --weeks 2  # Gate 2: crawl thử nhỏ, đo tốc độ + độ chính xác

PHỤ THUỘC:  pip install -r requirements.txt  &&  playwright install chromium

⚠️ Gate 0 PHẢI chạy trên máy/IP của bạn (Akamai buộc cookie _abck theo TLS+IP; session warm ở IP khác sẽ vô dụng).
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
# CONFIG  (đồng bộ với notebook; có thể override qua CLI)
# ============================================================
ROOM_API_HINT = "/api/v1/property/room-grid"
CURRENCY = "VND"
PRICE_TYPE = "final"            # final (all-in) | original | cashback
CHECKIN_OFFSET = 5             # W1 = hôm nay + 5 ngày
NUM_WEEKS = 6
DAYS_PER_WEEK = 3             # số ngày thử/tuần (dừng khi có giá) — prototype để nhỏ
NUM_WEEKS_DEFAULT_PROTO = 2   # Gate 2 mặc định 2 tuần cho nhanh

# Nhịp độ AN TOÀN — GIỮ Ở MỨC ≤ notebook hiện tại. Tốc độ đến từ replay ~1s/query, KHÔNG phải bắn nhiều hơn.
MAX_CONCURRENCY = 3           # asyncio.Semaphore — trần đồng thời (đừng tăng để "nhanh hơn")
QUERY_JITTER = (0.6, 1.6)     # nghỉ ngẫu nhiên giữa các query trên cùng 1 session
BETWEEN_HOTELS = (2.0, 5.0)   # nghỉ giữa các khách sạn (giống notebook)
REWARM_ON_BLOCK_STREAK = 3    # cảnh báo/đề xuất warm lại nếu gặp N lần liên tiếp non-200/empty

# Warm profiles: mỗi profile = (User-Agent, curl_cffi impersonate target) KHỚP NHAU.
#   Warm sẽ thử lần lượt cho tới khi bắt được request (xoay fingerprint để né block),
#   và GHI LẠI profile thắng → replay dùng đúng impersonate đó (TLS phải khớp UA đã mint cookie).
WARM_PROFILES = [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36", "chrome131"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "chrome124"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "chrome120"),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36", "chrome116"),
]
WARM_VIEWPORTS = [(1440, 900), (1536, 864), (1920, 1080), (1366, 768)]
WARM_ATTEMPTS = 3             # số profile thử tối đa khi warm bị chặn
HEADLESS = True
PAGE_TIMEOUT = 45000
API_WAIT_TIMEOUT = 25         # giây chờ room-grid xuất hiện khi warm
WARM_BACKOFF = (1.5, 3.5)     # nghỉ giữa các lần warm lại

JUNK_URL_PARAMS = {"searchrequestid", "ds", "searchtoken", "flightsearchcriteria",
                   "showreviewsubmissionentry", "iscalendarcallout"}
BLOCK_RESOURCE_TYPES = {"image", "media", "font"}

CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_capture")
HEADER_DROP = {"cookie", "content-length", "host", "accept-encoding",
               "connection", "te", "upgrade-insecure-requests"}

# ============================================================
# PARSERS — COPY NGUYÊN VẸN TỪ "crawl price AGODA - 1.ipynb" (đã test với dữ liệu Agoda thật)
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
    return f"{v:,}"                     # Agoda format: số thuần, KHÔNG prefix "VND" (khớp dữ liệu cũ)

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
    for rm, n in named:                                  # 1) khớp chính xác
        if _norm(n) == tnorm:
            return rm
    tfirst = tnorm.split()[0] if tnorm else ""
    best, best_score = None, -1.0                        # 2) Jaccard + bonus trùng từ đầu
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
        node = pr.get(ptype) or {}                       # "final" | "original"
    v = node.get("amountNumber")
    if isinstance(v, (int, float)) and v >= 1000:
        return int(v)
    return parse_amount(node.get("amount") or node.get("text"))

def extract_from_agoda(rg, target_room, ptype=PRICE_TYPE):
    """Trả 1 trong: found(price) | soldOut(thật) | blocked(rooms rỗng=bị chặn) | NA.
    ⚠️ rooms RỖNG = bị chặn/lỗi tải, KHÔNG BAO GIỜ coi là SOLD OUT (trừ khi có propertyName + searchCriteriaDescription)."""
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
    return {"found": False, "soldOut": False,
            "rooms": [(r.get("name") or "") for r in rooms]}

def is_real(v):
    return v not in (None, "", "NA", "nan") and not str(v).startswith("SOLD OUT")

def update_url_checkin(url, checkin):
    """Làm sạch URL + chuẩn hoá checkin/los/currency/finalPriceView/occupancy (giống notebook)."""
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
    """Lưu CSV — only-improve (không ghi NA đè giá thật) + atomic write. (rút gọn từ notebook)"""
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
        pd.DataFrame(rows).to_csv(tmp, index=False)
        os.replace(tmp, filename)
    except Exception as e:
        print(f"❌ Error saving: {e}", flush=True)

def _resolve_input(path):
    """Tìm file input: dùng path nếu tồn tại, ngược lại dò trong cây 31.crawl-tool."""
    if os.path.exists(path):
        return path
    import glob
    here = os.path.dirname(os.path.abspath(__file__))
    cands = glob.glob(os.path.join(here, "..", "**", os.path.basename(path)), recursive=True)
    return cands[0] if cands else path

def read_hotels_from_csv(file_path):
    import pandas as pd
    req = ['hotel_name', 'hotel_url', 'room_type']
    df = pd.read_csv(_resolve_input(file_path))
    if not all(c in df.columns for c in req):
        df.columns = req + list(df.columns[3:])
    df = df[df['hotel_url'].notna() & (df['hotel_url'] != '')]
    return [(r['hotel_name'], r['hotel_url'], r['room_type']) for _, r in df[req].iterrows()]

# ============================================================
# GATE 0 — WARM + CAPTURE (Playwright): bắt request room-grid THẬT
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

async def _warm_once(p, hotel_url, checkin, ua, viewport, stealth):
    """1 lần warm với 1 profile (ua) cụ thể. Trả cap (req/resp_json/cookies/...) hoặc req=None nếu fail."""
    url = update_url_checkin(hotel_url, checkin)
    cap = {"req": None, "resp_json": None, "checkin": checkin.strftime("%Y-%m-%d")}
    launch_args = ['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-dev-shm-usage']
    if HEADLESS:
        launch_args.insert(0, '--headless=new')
    browser = await p.chromium.launch(headless=HEADLESS, args=launch_args)
    ctx = await browser.new_context(
        viewport={"width": viewport[0], "height": viewport[1]}, user_agent=ua,
        locale="en-GB", timezone_id="Asia/Ho_Chi_Minh",
    )
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
                "() => (window.environment && window.environment.apiKey) "
                "|| (window.__INITIAL_STATE__ && window.__INITIAL_STATE__.apiKey) || null")
        except Exception:
            cap["apiKey"] = None
        storage = await ctx.storage_state()
        cap["cookies"] = [c for c in storage.get("cookies", []) if "agoda" in (c.get("domain") or "")]
    finally:
        try:
            await ctx.close()
        except Exception:
            pass
        try:
            await browser.close()
        except Exception:
            pass
    return cap

async def warm_and_capture(hotel_url, checkin, save=True, verbose=True):
    """Thử lần lượt WARM_PROFILES tới khi bắt được request room-grid. Ghi lại profile (ua, impersonate) đã thắng.
    Make-or-break: nếu mọi profile đều fail → direct-API chưa khả thi cho IP/KS này → fallback hybrid."""
    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import Stealth
        stealth = Stealth()
    except Exception:
        stealth = None

    async with async_playwright() as p:
        for attempt in range(min(WARM_ATTEMPTS, len(WARM_PROFILES))):
            ua, imp = WARM_PROFILES[attempt]
            viewport = WARM_VIEWPORTS[attempt % len(WARM_VIEWPORTS)]
            cap = await _warm_once(p, hotel_url, checkin, ua, viewport, stealth)
            if cap.get("req") is not None:
                cap["ua"], cap["impersonate"] = ua, imp
                if verbose:
                    r = cap["req"]
                    print(f"  ✅ Bắt được room-grid (profile {imp}): {r['method']} {r['url'][:88]}…", flush=True)
                    print(f"     body POST: {'CÓ' if r['post_data'] else 'KHÔNG (GET)'} | #cookies agoda: {len(cap.get('cookies', []))}"
                          f" | apiKey: {'có' if cap.get('apiKey') else 'nằm trong header/body'}", flush=True)
                    print(f"     response có rooms: {bool((cap.get('resp_json') or {}).get('rooms'))}", flush=True)
                if save:
                    os.makedirs(CAPTURE_DIR, exist_ok=True)
                    with open(os.path.join(CAPTURE_DIR, "capture.json"), "w", encoding="utf-8") as f:
                        json.dump(cap, f, ensure_ascii=False, indent=2)
                    if verbose:
                        print(f"     💾 Đã lưu {os.path.join(CAPTURE_DIR, 'capture.json')}", flush=True)
                return cap
            if verbose:
                print(f"  ⟳ profile {imp} bị chặn (chưa bắt được room-grid), thử profile kế…", flush=True)
            await asyncio.sleep(random.uniform(*WARM_BACKOFF))
    if verbose:
        print("  ❌ Mọi profile đều fail. Thử lại / đổi IP (4G) / HEADLESS=False.", flush=True)
    return {"req": None, "resp_json": None, "checkin": checkin.strftime("%Y-%m-%d")}

# ============================================================
# REPLAY (curl_cffi): tái dựng request từ capture, đổi checkin
# ============================================================
def _build_headers(cap_headers):
    h = {}
    for k, v in (cap_headers or {}).items():
        if k.lower() in HEADER_DROP or k.startswith(":"):
            continue
        h[k] = v
    return h

def _parameterize(cap_req, orig_checkin, new_checkin):
    """Tái dựng (method, url, headers, data) từ capture: thay checkin cũ→mới ở cả URL và body JSON."""
    method = cap_req["method"]
    url = re.sub(r'(checkin=)\d{4}-\d{2}-\d{2}', r'\g<1>' + new_checkin, cap_req["url"], flags=re.I)
    headers = _build_headers(cap_req.get("headers"))
    data = cap_req.get("post_data")
    if data:
        try:
            body = json.loads(data)
            def walk(o):
                if isinstance(o, dict):
                    return {k: walk(v) for k, v in o.items()}
                if isinstance(o, list):
                    return [walk(x) for x in o]
                if isinstance(o, str) and o == orig_checkin:
                    return new_checkin
                return o
            data = json.dumps(walk(body), separators=(",", ":"))
        except Exception:
            data = data.replace(orig_checkin, new_checkin)  # body không phải JSON
    return method, url, headers, data

def _make_session(impersonate=None):
    """curl_cffi session giả Chrome (TLS/JA3 + HTTP2). impersonate phải khớp UA đã mint cookie."""
    try:
        from curl_cffi import AsyncSession
    except Exception:
        from curl_cffi.requests import AsyncSession  # fallback tên cũ
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
    """Gọi thẳng room-grid bằng curl_cffi dựa trên capture, cho ngày checkin mới. Trả (status, json|None)."""
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

# ============================================================
# GATE RUNNERS
# ============================================================
async def gate0_capture(args):
    bc = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=CHECKIN_OFFSET)
    print(f"🔥 GATE 0 — warm + capture (checkin={bc.strftime('%Y-%m-%d')})", flush=True)
    cap = await warm_and_capture(args.url, bc, save=True)
    if cap.get("req") is not None and args.room:
        res = extract_from_agoda(cap.get("resp_json") or {}, args.room)
        print(f"  🔎 Sanity giá phòng '{args.room}': {res}", flush=True)

async def gate1_replay(args):
    """Chứng minh: (a) replay verbatim ra đúng giá, (b) ĐỔI CHECKIN vẫn ra dữ liệu → đủ điều kiện fan-out direct."""
    path = os.path.join(CAPTURE_DIR, "capture.json")
    if not os.path.exists(path):
        print("❌ chưa có capture.json — chạy 'capture' trước.", flush=True); return
    with open(path, encoding="utf-8") as f:
        cap = json.load(f)
    sess = _make_session(cap.get("impersonate"))
    _load_cookies(sess, cap.get("cookies"))
    try:
        bc = datetime.strptime(cap["checkin"], "%Y-%m-%d")
        print(f"🧪 GATE 1a — replay VERBATIM (impersonate={cap.get('impersonate')}, cùng ngày capture):", flush=True)
        st, j = await query_via_capture(sess, cap, bc)
        print(f"     status={st} | rooms={bool((j or {}).get('rooms'))} | keys={list((j or {}).keys())[:6]}", flush=True)
        if args.room:
            print(f"     giá '{args.room}': {extract_from_agoda(j or {}, args.room)}", flush=True)

        bc2 = bc + timedelta(days=14)
        print(f"🧪 GATE 1b — replay ĐỔI CHECKIN sang {bc2.strftime('%Y-%m-%d')}:", flush=True)
        st2, j2 = await query_via_capture(sess, cap, bc2)
        print(f"     status={st2} | rooms={bool((j2 or {}).get('rooms'))}", flush=True)

        ok_a = st == 200 and bool((j or {}).get("rooms"))
        ok_b = st2 == 200 and bool((j2 or {}).get("rooms"))
        print("\n  ── KẾT LUẬN GATE 1 ──", flush=True)
        print(f"     1a verbatim : {'PASS ✅' if ok_a else 'FAIL ❌'}", flush=True)
        print(f"     1b đổi ngày : {'PASS ✅ → fan-out direct khả thi' if ok_b else 'FAIL ❌ → dùng warm theo từng KS (mặc định Gate 2)'}", flush=True)
        if not ok_a:
            print("     ⇒ replay verbatim fail: cookie/TLS/IP không khớp (warm & replay phải CÙNG IP) hoặc thiếu apiKey trong header.", flush=True)
    finally:
        try:
            await sess.close()
        except Exception:
            pass

async def crawl_one_hotel(cap, hotel_name, room_type, base_checkin, num_weeks, days_per_week):
    """Crawl 1 khách sạn dùng curl_cffi: dò từng tuần (nhiều ngày) tới khi có giá. cap = warm của CHÍNH KS này."""
    sess = _make_session(cap.get("impersonate"))
    _load_cookies(sess, cap.get("cookies"))
    prices = {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    block_streak = {"n": 0}

    async def one_week(wn):
        week_start = base_checkin + timedelta(days=(wn - 1) * 7)
        sold = False
        for d in range(days_per_week):
            checkin = week_start + timedelta(days=d)
            async with sem:
                await asyncio.sleep(random.uniform(*QUERY_JITTER))
                st, j = await query_via_capture(sess, cap, checkin)
            res = extract_from_agoda(j or {}, room_type)
            if st == 200 and not res.get("blocked"):
                block_streak["n"] = 0
            elif st in (403, 429, 503) or res.get("blocked"):
                block_streak["n"] += 1                     # soft-block → KHÔNG ghi NA/SOLD OUT, để retry
            if res.get("found"):
                return {"week": wn, "price": res["price"]}
            if res.get("soldOut"):
                sold = True
        return {"week": wn, "price": "SOLD OUT" if sold else "NA"}

    results = await asyncio.gather(*[one_week(w) for w in range(1, num_weeks + 1)])
    try:
        await sess.close()
    except Exception:
        pass
    for r in results:
        prices[f"Price W{r['week']}"] = r["price"]
    return prices, block_streak["n"]

async def gate2_crawl(args):
    t0 = time.time()
    num_weeks = args.weeks or NUM_WEEKS_DEFAULT_PROTO
    hotels = read_hotels_from_csv(args.input)
    if args.max:
        hotels = hotels[:args.max]
    bc = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=CHECKIN_OFFSET)
    out = f"DIRECT_{datetime.today().strftime('%Y%m%d')}.csv"
    temp = "TEMP_DIRECT_" + os.path.basename(args.input)
    print(f"🚀 GATE 2 — direct-API crawl | {len(hotels)} KS × {num_weeks} tuần × ≤{DAYS_PER_WEEK} ngày | W1={bc.strftime('%Y-%m-%d')}", flush=True)
    print("   (per-hotel warm: 1 page-load/KS rồi replay các tuần qua curl_cffi)", flush=True)
    awp = {}
    for idx, (hn, hu, rt) in enumerate(hotels, 1):
        print(f"\n🏨 {idx}/{len(hotels)} {hn} | {rt}", flush=True)
        cap = await warm_and_capture(hu, bc, save=False, verbose=False)   # warm THEO KHÁCH SẠN
        if cap.get("req") is None:
            print("   ⚠️ warm fail → NA toàn bộ (fallback: dùng notebook Playwright cho KS này)", flush=True)
            awp[(hn, rt)] = {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
            save_backup_csv(awp, temp, num_weeks)
            continue
        prices, blk = await crawl_one_hotel(cap, hn, rt, bc, num_weeks, DAYS_PER_WEEK)
        awp[(hn, rt)] = prices
        got = sum(1 for i in range(1, num_weeks + 1) if is_real(prices[f"Price W{i}"]))
        note = f" | ⚠️ block_streak={blk} (cân nhắc warm lại)" if blk >= REWARM_ON_BLOCK_STREAK else ""
        print(f"   {'✅' if got == num_weeks else '⚠️'} {got}/{num_weeks} tuần có giá{note}", flush=True)
        save_backup_csv(awp, temp, num_weeks)
        await asyncio.sleep(random.uniform(*BETWEEN_HOTELS))
    save_backup_csv(awp, out, num_weeks)
    tc = len(awp) * num_weeks
    na = sum(1 for pp in awp.values() for i in range(1, num_weeks + 1) if pp.get(f"Price W{i}", "NA") == "NA")
    so = sum(1 for pp in awp.values() for i in range(1, num_weeks + 1) if str(pp.get(f"Price W{i}", "")).startswith("SOLD OUT"))
    tt = time.time() - t0
    print(f"\n{'='*60}", flush=True)
    print(f"✅ {out} | giá {tc-na-so}/{tc} ({(tc-na-so)/max(tc,1):.1%}) | 🚫 {so} SO | ❌ {na} NA", flush=True)
    print(f"⏱️ {int(tt//60)}m {int(tt%60)}s cho {len(awp)} KS × {num_weeks} tuần (≈ {tt/max(len(awp),1):.1f}s/KS)", flush=True)
    print(f"{'='*60}", flush=True)

def main():
    ap = argparse.ArgumentParser(description="Agoda direct-API crawler prototype (curl_cffi)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture", help="Gate 0: warm + bắt 1 request room-grid thật")
    c.add_argument("--url", required=True, help="URL trang khách sạn Agoda")
    c.add_argument("--room", default="", help="(tuỳ chọn) tên phòng để sanity-check giá ngay")
    r = sub.add_parser("replay", help="Gate 1: replay verbatim + đổi checkin để chứng minh khả thi")
    r.add_argument("--room", default="", help="(tuỳ chọn) tên phòng để in giá khi replay")
    g = sub.add_parser("crawl", help="Gate 2: crawl thử nhỏ rồi đo tốc độ + độ chính xác")
    g.add_argument("--input", default="agoda1.csv", help="CSV input (Hotel,URL,Room,...) — tự dò trong 31.crawl-tool nếu không thấy")
    g.add_argument("--max", type=int, default=5, help="số khách sạn tối đa (prototype)")
    g.add_argument("--weeks", type=int, default=0, help="số tuần (mặc định 2 cho prototype)")
    args = ap.parse_args()
    asyncio.run({"capture": gate0_capture, "replay": gate1_replay, "crawl": gate2_crawl}[args.cmd](args))

if __name__ == "__main__":
    main()
