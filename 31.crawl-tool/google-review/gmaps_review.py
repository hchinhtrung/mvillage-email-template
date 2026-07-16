# -*- coding: utf-8 -*-
"""Google Maps hotel review & rating crawler — direct API, không cần browser.

Tận dụng stack của crawler agoda (curl_cffi + capture/replay + TEMP/FINAL resume),
nhưng Google không cần warm browser: mọi thứ replay được từ template đã capture 1 lần.

Pipeline mỗi hotel URL:
  1. RESOLVE  — maps.app.goo.gl chỉ trả 302 sạch cho agent "không phải browser",
                nên bước này dùng session KHÔNG impersonate → URL đầy đủ chứa
                ftid (0x..:0x..), id /g/.., toạ độ, tên.
  2. SUMMARY  — GET /maps/preview/place với pb template capture sẵn (swap ftid +
                toạ độ + /g/ id) → rating chính thức [6][4][7], tổng review
                [6][37][1], tên [6][11], địa chỉ [6][39].
  3. REVIEWS  — POST batchexecute rpc `ocp93e` của Google Travel. Entity token
                TỰ DỰNG từ cid + /g/ id (protobuf, đã verify Google chấp nhận),
                10 review/trang, token trang kế nằm ở inner[0][5] ("…:offset").
                Reviews gồm cả nguồn OTA (Google/Tripadvisor/Booking/Trip.com…)
                — có cột `source` để lọc.

Lưu ý: Maps desktop ẩn hẳn mục review của HOTEL với user ẩn danh ("limited view"),
listugcposts trả rỗng — vì vậy reviews phải đi qua mặt Travel như trên.

Output trong OUTDIR:
  TEMP_gmaps_hotels.csv  — checkpoint theo hotel (resume: status=ok thì bỏ qua)
  TEMP_gmaps_reviews.csv — checkpoint dòng review
  FINAL_hotels_<YYYYMMDD>.csv / FINAL_reviews_<YYYYMMDD>.csv
"""
import base64
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

from curl_cffi import requests as cq

# cho phép import helper đọc Google Sheet của package crawler (cùng repo)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)                      # .../31.crawl-tool
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

BLOCK_HTTP = {403, 429, 503}
PAGE_SLEEP = (0.5, 1.3)          # nghỉ giữa các trang review của 1 hotel
HOTEL_SLEEP = (1.5, 3.5)         # nghỉ giữa 2 hotel
BLOCK_COOLDOWN = (30, 75)        # nghỉ khi dính 403/429 rồi thử lại 1 lần

# pb template của /maps/preview/place — capture 1 lần từ browser thật (2026-07).
# Chỉ swap 4 chỗ: ftid, lat, lng, /g/ id. Session token cuối chấp nhận giá trị bất kỳ.
_PLACE_PB = (
    "!1m16!1s{ftid}!3m8!1m3!1d3919.4515556915844!2d{lng}!3d{lat}!3m2!1i1024!2i768"
    "!4f13.1!4m2!3d{lat}!4d{lng}!15m2!1m1!4s{gid}!12m4!2m3!1i360!2i120!4i8!13m57"
    "!2m2!1i203!2i100!3m2!2i4!5b1!6m6!1m2!1i86!2i86!1m2!1i408!2i240!7m33!1m3!1e1"
    "!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3"
    "!1m3!1e10!2b1!3e2!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!9b0!15m8!1m7!1m2!1m1"
    "!1e2!2m2!1i195!2i195!3i20!14m3!1s0ntYapLiJcyNseMPiL6ssQg!7e81!15i10112"
    "!15m108!1m26!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1!18m15!3b1!4b1!5b1"
    "!6b1!13b1!14b1!17b1!21b1!22b1!30b1!32b1!33m1!1b1!34b1!36e2!10m1!8e3!11m1!3e1"
    "!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1!30m1!2b1!36b1!37b1!39m3!2m2!2i1"
    "!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1!61m2!1m1!1e1!65m5!3m4!1m3!1m2!1i224"
    "!2i298!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1!8m10!1m6!4m1!1e1!4m1"
    "!1e3!4m1!1e4!3sother_user_google_review_posts__and__hotel_and_vr_partner_"
    "review_posts!6m1!1e1!9b1!89b1!90m2!1m1!1e2!98m3!1b1!2b1!3b1!103b1!113b1"
    "!114m3!1b1!2m1!1b1!117b1!122m1!1b1!126b1!127b1!128m1!1b0!21m0!22m1!1e81"
    "!30m8!3b1!6m2!1b1!2b1!7m2!1e3!2b1!9b1!34m5!7b1!10b1!14b1!15m1!1b0!37i786")

_SUBRATING_LABELS = {1: "Rooms", 4: "Service", 5: "Location"}


class Blocked(Exception):
    pass


# --------------------------------------------------------------------------- sessions
def make_sessions():
    """(plain, browser): plain để resolve short-link (goo.gl 302 cho curl-like agent),
    browser (impersonate chrome) cho preview/place + batchexecute."""
    plain = cq.Session()
    sess = cq.Session(impersonate="chrome")
    sess.headers.update({"Accept-Language": "en-US,en;q=0.9,vi;q=0.8"})
    return plain, sess


def _check_block(r):
    if r.status_code in BLOCK_HTTP or "unusual traffic" in (r.text or "")[:4000]:
        raise Blocked(f"HTTP {r.status_code}")


# --------------------------------------------------------------------------- input
def read_links(input_spec, sheet_name="", gid=""):
    """Đọc list URL hotel: Google Sheet (URL docs.google.com) / CSV / XLSX / TXT.
    Cột đầu tiên chứa URL; cột 2 (nếu có) là tên tuỳ chọn. Trả về [(url, name|"")]."""
    import pandas as pd
    from crawler.hotels_io import _gsheet_url, is_gsheet   # tái dụng helper agoda

    spec = str(input_spec)
    if is_gsheet(spec):
        df = pd.read_csv(_gsheet_url(spec, sheet_name, gid))
    elif spec.endswith(".xlsx"):
        df = pd.read_excel(spec)
    elif spec.endswith(".txt"):
        rows = [ln.strip() for ln in open(spec, encoding="utf-8") if ln.strip()]
        df = pd.DataFrame({"url": rows})
    else:
        df = pd.read_csv(spec)
    out = []
    for _, row in df.iterrows():
        url = str(row.iloc[0]).strip()
        if not url.startswith(("http://", "https://")):
            continue
        name = ""
        if len(row) > 1 and isinstance(row.iloc[1], str):
            name = row.iloc[1].strip()
        out.append((url, name))
    return out


# --------------------------------------------------------------------------- resolve
def resolve_place(plain, url):
    """Short-link/URL đầy đủ → dict(ftid, gid, lat, lng, name, final_url)."""
    final = url
    if "goo.gl" in url or "maps.app" in url:
        r = plain.get(url, allow_redirects=True, timeout=40)
        final = str(r.url)
    ftid = re.search(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", final)
    gid = re.search(r"!16s%2F(g|m)%2F([^!?&%]+)", final)
    lat = re.search(r"!3d([\d.-]+)", final)
    lng = re.search(r"!4d([\d.-]+)", final)
    name = re.search(r"/maps/place/([^/@]+)", final)
    return {
        "final_url": final,
        "ftid": ftid.group(1) if ftid else None,
        "gid": f"/{gid.group(1)}/{gid.group(2)}" if gid else None,
        "lat": lat.group(1) if lat else "10.77",
        "lng": lng.group(1) if lng else "106.69",
        "name": unquote(name.group(1).replace("+", " ")) if name else "",
    }


# --------------------------------------------------------------------------- summary
def fetch_summary(sess, ftid, lat, lng, gid, hl="vi"):
    """/maps/preview/place → (rating, review_count, name, address)."""
    pb = _PLACE_PB.format(ftid=ftid, lat=lat, lng=lng, gid=gid or "/g/1")
    u = (f"https://www.google.com/maps/preview/place?authuser=0&hl={hl}&gl=vn"
         f"&pb={quote(pb, safe='!*()._-')}")
    r = sess.get(u, timeout=40)
    _check_block(r)
    if r.status_code != 200 or not r.text.startswith(")]}'"):
        return None, None, None, None
    d = json.loads(r.text[r.text.index("\n") + 1:])
    p = d[6] if len(d) > 6 and d[6] else []

    def g(node, *idx):
        for i in idx:
            if not isinstance(node, list) or i >= len(node) or node[i] is None:
                return None
            node = node[i]
        return node

    return g(p, 4, 7), g(p, 37, 1), g(p, 11), g(p, 39)


# --------------------------------------------------------------------------- reviews
def _varint(n):
    out = b""
    while True:
        x = n & 0x7F
        n >>= 7
        out += bytes([x | (0x80 if n else 0)])
        if not n:
            return out


def entity_token(ftid, gid):
    """Dựng entity token của Google Travel từ cid (nửa sau ftid) + /g/ id."""
    cid = int(ftid.split(":")[1], 16)
    inner = b"\x08" + _varint(cid)
    if gid:
        gb = gid.encode()
        inner += b"\x1a" + bytes([len(gb)]) + gb
    raw = b"\x0a" + bytes([len(inner)]) + inner + b"\x10\x01"
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _ocp93e(sess, ent, token=None, hl="vi"):
    """1 trang review. Trả (reviews_raw, next_token)."""
    if token:
        param = [None, None, None, 10, 1, None, None, "", ent, token, None, [[]], None, ""]
    else:
        param = [None, None, None, None, None, None, None, None, ent, None, None, [[]]]
    freq = json.dumps([[["ocp93e", json.dumps(param), None, "1"]]])
    u = (f"https://www.google.com/_/TravelFrontendUi/data/batchexecute"
         f"?rpcids=ocp93e&source-path="
         f"{quote(f'/travel/hotels/entity/{ent}/reviews', safe='')}&hl={hl}&gl=vn&rt=c")
    r = sess.post(u, data={"f.req": freq}, timeout=40, headers={
        "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        "x-same-domain": "1"})
    _check_block(r)
    if r.status_code != 200:
        return None, None
    inner = None
    for ln in r.text.split("\n"):
        if ln.startswith('[["wrb.fr"'):
            env = json.loads(ln)
            if env[0][2]:
                inner = json.loads(env[0][2])
            break
    if not inner or not inner[0]:
        return None, None
    blk = inner[0]
    return blk[0] or [], (blk[5] if len(blk) > 5 else None) or None


def _g(node, *idx):
    for i in idx:
        if not isinstance(node, list) or i >= len(node) or node[i] is None:
            return None
        node = node[i]
    return node


def parse_review(rev):
    src, b = rev[0] or [], rev[1] or []
    segs = _g(b, 3, 0) or []
    text = "\n".join(s[1] for s in segs if isinstance(s, list) and len(s) > 1
                     and isinstance(s[1], str) and s[1])
    orig = "\n".join(s[3] for s in segs if isinstance(s, list) and len(s) > 3
                     and isinstance(s[3], str) and s[3])
    reply_parts = _g(b, 5, 0) or []
    reply = "\n".join(p for p in reply_parts if isinstance(p, str) and p)
    subs = []
    for it in (_g(b, 7) or []):
        val = _g(it, 1, 0)
        if val is not None:
            subs.append(f"{_SUBRATING_LABELS.get(_g(it, 0), _g(it, 0))}:{val}")
    br = re.compile(r"<br\s*/?>", re.I)
    return {
        "source": _g(src, 0),
        "author": _g(b, 0, 0),
        "author_url": _g(b, 0, 1),
        "when": _g(b, 1),
        "rating": _g(b, 2, 0),
        "rating_max": _g(b, 2, 1),
        "text": br.sub("\n", text),
        "text_original": br.sub("\n", orig) if orig and orig != text else "",
        "subratings": ";".join(subs),
        "reply": br.sub("\n", reply),
        "reply_when": _g(b, 5, 1),
        "review_id": _g(b, 8),
        "review_url": _g(b, 4),
    }


_REL_UNITS = {  # đơn vị ngày (xấp xỉ) — hỗ trợ tiếng Anh + tiếng Việt
    "second": 0, "minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30.44,
    "year": 365.25, "giây": 0, "phút": 0, "giờ": 0, "ngày": 1, "tuần": 7,
    "tháng": 30.44, "năm": 365.25,
}


def rel_to_date(when, base=None):
    """'3 tuần trước' / 'a month ago' → ngày ISO xấp xỉ. Không parse được → ''."""
    if not when:
        return ""
    base = base or datetime.now()
    w = str(when).lower()
    if any(k in w for k in ("vừa xong", "just now", "hôm nay", "today")):
        return base.strftime("%Y-%m-%d")
    if any(k in w for k in ("hôm qua", "yesterday")):
        return (base - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d+|a|an|một)\s*(second|minute|hour|day|week|month|year"
                  r"|giây|phút|giờ|ngày|tuần|tháng|năm)", w)
    if not m:
        return ""
    n = 1 if m.group(1) in ("a", "an", "một") else int(m.group(1))
    days = _REL_UNITS[m.group(2)] * n
    return (base - timedelta(days=days)).strftime("%Y-%m-%d")


def fetch_reviews(sess, ent, max_reviews=0, hl="vi", on_page=None):
    """Kéo review theo trang tới hết token / đủ max_reviews (0 = tất cả)."""
    out, token, last_off = [], None, -1
    while True:
        raws, token = _ocp93e(sess, ent, token=token, hl=hl)
        if raws is None:
            raise Blocked("ocp93e empty/blocked response")
        out.extend(parse_review(rv) for rv in raws)
        if on_page:
            on_page(len(out))
        if not token or not raws:
            break
        off = int(token.rsplit(":", 1)[1]) if ":" in token else -1
        if off <= last_off:            # chống lặp vô hạn nếu token không tiến
            break
        last_off = off
        if max_reviews and len(out) >= max_reviews:
            out = out[:max_reviews]
            break
        time.sleep(random.uniform(*PAGE_SLEEP))
    return out


# --------------------------------------------------------------------------- checkpoint
HOTEL_COLS = ["input_url", "hotel_name", "address", "overall_rating", "review_count",
              "fetched_reviews", "status", "ftid", "gid", "entity", "final_url",
              "crawled_at"]
REVIEW_COLS = ["input_url", "hotel_name", "source", "author", "rating", "rating_max",
               "when", "approx_date", "text", "text_original", "subratings", "reply",
               "reply_when", "review_id", "review_url", "author_url", "crawled_at"]


def _load_csv(path, cols):
    import pandas as pd
    if os.path.exists(path):
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df[cols]
    return pd.DataFrame(columns=cols)


def _save_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


# --------------------------------------------------------------------------- crawl
def crawl(input, out_dir=".", max_reviews=0, max_hotels=0, hl="vi",
          sheet="", gid=""):
    """Chạy full: đọc input → crawl từng hotel (resume được) → FINAL csv.

    input       : URL Google Sheet, hoặc file CSV/XLSX/TXT (cột 1 = URL hotel)
    out_dir     : thư mục output (TEMP_/FINAL_)
    max_reviews : số review tối đa mỗi hotel (0 = lấy hết)
    max_hotels  : chỉ crawl N hotel đầu (0 = tất cả) — để test nhanh
    hl          : ngôn ngữ dữ liệu trả về ("vi"/"en" — ảnh hưởng bản dịch + chuỗi ngày)
    """
    import pandas as pd

    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    temp_h = os.path.join(out_dir, "TEMP_gmaps_hotels.csv")
    temp_r = os.path.join(out_dir, "TEMP_gmaps_reviews.csv")

    links = read_links(input, sheet, gid)
    if max_hotels:
        links = links[:max_hotels]
    hotels_df = _load_csv(temp_h, HOTEL_COLS)
    reviews_df = _load_csv(temp_r, REVIEW_COLS)
    done = set(hotels_df.loc[hotels_df["status"] == "ok", "input_url"])
    if len(hotels_df):
        print(f"📂 Resume: {len(hotels_df)} hotel trong checkpoint, "
              f"{len(done)} đã ok — sẽ bỏ qua", flush=True)

    # hotel chưa từng crawl chạy trước, hotel lỗi retry sau (giống agoda)
    fresh = [x for x in links if x[0] not in set(hotels_df["input_url"])]
    redo = [x for x in links if x[0] in set(hotels_df["input_url"]) and x[0] not in done]
    work = fresh + redo
    print(f"🚀 {len(links)} hotel trong input | crawl {len(work)} "
          f"(mới {len(fresh)}, retry {len(redo)}) | max_reviews="
          f"{max_reviews or 'ALL'} | hl={hl}", flush=True)

    plain, sess = make_sessions()
    for i, (url, custom_name) in enumerate(work, 1):
        row = {c: "" for c in HOTEL_COLS}
        row["input_url"] = url
        row["crawled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        got_rows = []
        try:
            info = resolve_place(plain, url)
            if not info["ftid"]:
                raise ValueError("không tìm thấy ftid trong URL")
            rating = count = name = addr = None
            try:
                rating, count, name, addr = fetch_summary(
                    sess, info["ftid"], info["lat"], info["lng"], info["gid"], hl)
            except Blocked:
                raise
            except Exception:
                pass                                   # summary hỏng vẫn crawl review
            name = custom_name or name or info["name"]
            ent = entity_token(info["ftid"], info["gid"])
            print(f"\n🏨 {i}/{len(work)} {name[:58]}", flush=True)
            print(f"   ⭐ {rating} | {count} đánh giá | {str(addr)[:60]}", flush=True)

            def _progress(n):
                if n and n % 200 == 0:
                    print(f"   … đã lấy {n} review", flush=True)

            revs = fetch_reviews(sess, ent, max_reviews=max_reviews, hl=hl,
                                 on_page=_progress)
            crawl_dt = datetime.now()
            for rv in revs:
                rv_row = {c: "" for c in REVIEW_COLS}
                rv_row.update({k: ("" if v is None else v) for k, v in rv.items()
                               if k in REVIEW_COLS})
                rv_row["input_url"] = url
                rv_row["hotel_name"] = name
                rv_row["approx_date"] = rel_to_date(rv.get("when"), crawl_dt)
                rv_row["crawled_at"] = crawl_dt.strftime("%Y-%m-%d %H:%M")
                got_rows.append(rv_row)

            row.update({"hotel_name": name, "address": addr or "",
                        "overall_rating": rating if rating is not None else "",
                        "review_count": count if count is not None else "",
                        "fetched_reviews": len(revs), "status": "ok",
                        "ftid": info["ftid"], "gid": info["gid"] or "",
                        "entity": ent, "final_url": info["final_url"]})
            print(f"   ✅ lấy được {len(revs)} review", flush=True)
        except Blocked as e:
            row.update({"status": "blocked"})
            print(f"   🚫 bị chặn ({e}) — nghỉ {BLOCK_COOLDOWN} rồi tiếp hotel sau",
                  flush=True)
            time.sleep(random.uniform(*BLOCK_COOLDOWN))
        except Exception as e:
            row.update({"status": f"error:{type(e).__name__}:{str(e)[:60]}"})
            print(f"   ❌ {type(e).__name__}: {str(e)[:90]}", flush=True)

        # ghi checkpoint sau MỖI hotel: thay dòng hotel + thay toàn bộ review của nó
        hotels_df = hotels_df[hotels_df["input_url"] != url]
        hotels_df = pd.concat([hotels_df, pd.DataFrame([row])], ignore_index=True)
        if got_rows:
            reviews_df = reviews_df[reviews_df["input_url"] != url]
            reviews_df = pd.concat([reviews_df, pd.DataFrame(got_rows)],
                                   ignore_index=True)
        _save_csv(hotels_df, temp_h)
        _save_csv(reviews_df, temp_r)
        if i < len(work):
            time.sleep(random.uniform(*HOTEL_SLEEP))

    today = datetime.today().strftime("%Y%m%d")
    out_h = os.path.join(out_dir, f"FINAL_hotels_{today}.csv")
    out_r = os.path.join(out_dir, f"FINAL_reviews_{today}.csv")
    order = {u: k for k, (u, _) in enumerate(links)}
    hotels_df = hotels_df[hotels_df["input_url"].isin(order)]
    hotels_df = hotels_df.sort_values(by="input_url", key=lambda s: s.map(order))
    reviews_df_out = reviews_df[reviews_df["input_url"].isin(order)]
    _save_csv(hotels_df, out_h)
    _save_csv(reviews_df_out, out_r)
    n_ok = int((hotels_df["status"] == "ok").sum())
    print(f"\n🏁 Xong {n_ok}/{len(links)} hotel, {len(reviews_df_out)} review "
          f"trong {time.time()-t0:.0f}s", flush=True)
    print(f"📄 {out_h}\n📄 {out_r}", flush=True)
    return out_h, out_r


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--max-reviews", type=int, default=0)
    ap.add_argument("--max-hotels", type=int, default=0)
    ap.add_argument("--hl", default="vi")
    a = ap.parse_args()
    crawl(a.input, a.out, a.max_reviews, a.max_hotels, a.hl)
