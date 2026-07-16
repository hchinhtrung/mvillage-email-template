# -*- coding: utf-8 -*-
"""Agoda hotel review & rating crawler — direct API, không cần browser.

Pipeline mỗi hotel URL:
  1. RESOLVE  — GET trang hotel → lấy propertyId (+ tên) từ HTML.
  2. SUMMARY  — POST /api/cronos/property/review/HotelReviews
                → rating tổng, số review, sub-ratings (Cleanliness/Service…).
  3. REVIEWS  — POST /api/cronos/property/review/ReviewComments (phân trang)
                → từng review: rating, title, text, reviewer, room, reply…

Output trong OUTDIR:
  TEMP_agoda_hotels.csv  — checkpoint theo hotel (resume: status=ok thì bỏ qua)
  TEMP_agoda_reviews.csv — checkpoint dòng review
  FINAL_hotels_<YYYYMMDD>.csv / FINAL_reviews_<YYYYMMDD>.csv
"""
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from curl_cffi import requests as cq

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)                      # .../31.crawl-tool
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

BLOCK_HTTP = {403, 429, 503}
PAGE_SLEEP = (0.4, 1.0)
HOTEL_SLEEP = (1.2, 2.8)
BLOCK_COOLDOWN = (30, 75)
PAGE_SIZE = 50
AGODA_PROVIDER = 332                                # Agoda verified guests

# sorting: 1=Most recent, 2=Rating high→low, 3=Rating low→high, 7=Most helpful
SORT_MAP = {
    "recent": 1,
    "most_recent": 1,
    "rating_high": 2,
    "rating_low": 3,
    "helpful": 7,
    "most_helpful": 7,
}


class Blocked(Exception):
    pass


# --------------------------------------------------------------------------- sessions
def make_session():
    sess = cq.Session(impersonate="chrome")
    sess.headers.update({
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/json",
    })
    return sess


def _check_block(r):
    if r.status_code in BLOCK_HTTP:
        raise Blocked(f"HTTP {r.status_code}")
    text = (r.text or "")[:4000].lower()
    if "access denied" in text or "unusual traffic" in text:
        raise Blocked(f"HTTP {r.status_code} soft-block")


def clean_hotel_url(url):
    """Bỏ query tracking (cid, searchrequestid…) — giữ path sạch để resume ổn định."""
    parts = urlsplit(str(url).strip())
    keep = {k.lower() for k in ()}                  # không giữ query nào
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() in keep]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), ""))


# --------------------------------------------------------------------------- input
def read_links(input_spec, sheet_name="", gid=""):
    """Đọc list hotel: Google Sheet / CSV / XLSX / TXT.
    Nhận cả format (URL, name) lẫn (Hotel, URL) — cột nào là URL thì lấy.
    Trả về [(url, name|"")], đã dedupe theo URL sạch.
    """
    import pandas as pd
    from crawler.hotels_io import _gsheet_url, is_gsheet

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

    out, seen = [], set()
    for _, row in df.iterrows():
        vals = [str(v).strip() if isinstance(v, str) or not pd.isna(v) else ""
                for v in row.tolist()]
        url = name = ""
        for v in vals:
            if v.startswith(("http://", "https://")) and "agoda.com" in v:
                url = v
                break
        if not url:
            continue
        for v in vals:
            if v and v != url and not v.startswith(("http://", "https://")):
                name = v
                break
        key = clean_hotel_url(url)
        if key in seen:
            continue
        seen.add(key)
        out.append((url, name))
    return out


# --------------------------------------------------------------------------- resolve + summary
def resolve_hotel(sess, url):
    """GET hotel page → dict(property_id, hotel_name, final_url, clean_url)."""
    r = sess.get(url, timeout=50, allow_redirects=True)
    _check_block(r)
    if r.status_code != 200:
        raise ValueError(f"hotel page HTTP {r.status_code}")
    html = r.text or ""
    m = re.search(r'propertyId["\'\s:=]+(\d+)', html)
    if not m:
        m = re.search(r'hotelId["\'\s:=]+(\d+)', html)
    if not m:
        raise ValueError("không tìm thấy propertyId trong trang hotel")
    name = ""
    for pat in (r'"hotelName"\s*:\s*"([^"]+)"',
                r'"propertyName"\s*:\s*"([^"]+)"',
                r"<title>([^|<]+)"):
        nm = re.search(pat, html)
        if nm:
            name = nm.group(1).strip()
            break
    final = str(r.url)
    return {
        "property_id": m.group(1),
        "hotel_name": name,
        "final_url": final,
        "clean_url": clean_hotel_url(final or url),
    }


def _review_body(hotel_id, page=1, page_size=PAGE_SIZE, sorting=1, provider_id=AGODA_PROVIDER):
    return {
        "hotelId": int(hotel_id),
        "providerId": int(provider_id),
        "demographicId": 0,
        "page": int(page),
        "pageSize": int(page_size),
        "sorting": int(sorting),
        "providerIds": [int(provider_id)] if int(provider_id) > 0 else [],
        "isReviewPage": False,
        "isCrawlablePage": True,
        "filters": {"language": [], "room": []},
        "searchKeyword": "",
        "searchFilters": [],
    }


def _post_json(sess, endpoint, body, referer):
    r = sess.post(
        f"https://www.agoda.com/api/cronos/property/review/{endpoint}",
        json=body,
        timeout=40,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            "Referer": referer,
            "Origin": "https://www.agoda.com",
        },
    )
    _check_block(r)
    if r.status_code != 200:
        raise ValueError(f"{endpoint} HTTP {r.status_code}")
    try:
        return r.json()
    except Exception as e:
        raise ValueError(f"{endpoint} not JSON: {e}") from e


def fetch_summary(sess, hotel_id, referer, provider_id=AGODA_PROVIDER):
    """HotelReviews → summary dict (rating, counts, grades, providers…)."""
    data = _post_json(sess, "HotelReviews",
                      _review_body(hotel_id, page=1, page_size=20,
                                   sorting=1, provider_id=provider_id),
                      referer)
    combined = (data.get("combinedReview") or {}).get("score") or {}
    demos = ((data.get("score") or {}).get("demographics") or [])
    demo0 = demos[0] if demos else {}
    grades = demo0.get("grades") or (data.get("combinedReview") or {}).get("grades") or []
    sub = ";".join(
        f"{g.get('name')}:{g.get('score')}"
        for g in grades if g.get("name") is not None and g.get("score") is not None
    )
    providers = []
    cl = data.get("commentList") or {}
    for p in cl.get("providerList") or []:
        providers.append({
            "provider_id": p.get("id"),
            "total_comments": p.get("totalIndex"),
            "is_default": bool(p.get("isDefaultProvider")),
        })
    return {
        "hotel_name": data.get("hotelName") or demo0.get("hotelName") or "",
        "overall_rating": combined.get("score") if combined.get("score") is not None
                          else demo0.get("score"),
        "rating_text": combined.get("scoreText") or demo0.get("scoreText") or "",
        "review_count": combined.get("reviewCount") if combined.get("reviewCount") is not None
                        else demo0.get("count"),
        "comment_count": combined.get("reviewCommentsCount"),
        "provider_comment_count": next(
            (p["total_comments"] for p in providers
             if p["provider_id"] == int(provider_id)), None),
        "subratings": sub,
        "providers": providers,
        "raw_providers": json.dumps(providers, ensure_ascii=False),
    }


# --------------------------------------------------------------------------- reviews
def parse_comment(c):
    info = c.get("reviewerInfo") or {}
    photos = []
    for img in c.get("ugcImages") or []:
        if isinstance(img, dict):
            u = img.get("url") or img.get("imageUrl") or img.get("thumbnailUrl")
            if u:
                photos.append(u)
        elif isinstance(img, str) and img:
            photos.append(img)
    return {
        "review_id": c.get("hotelReviewId"),
        "provider_id": c.get("providerId"),
        "source": c.get("reviewProviderText") or "",
        "rating": c.get("rating"),
        "rating_text": c.get("ratingText") or "",
        "title": c.get("reviewTitle") or "",
        "text": c.get("reviewComments") or "",
        "text_original": c.get("originalComment") or "",
        "title_original": c.get("originalTitle") or "",
        "positives": c.get("reviewPositives") or "",
        "negatives": c.get("reviewNegatives") or "",
        "review_date": (c.get("reviewDate") or "")[:10],
        "review_date_text": c.get("formattedReviewDate") or "",
        "check_in": (c.get("checkInDate") or "")[:10],
        "check_out": (c.get("checkOutDate") or "")[:10],
        "stay_month": c.get("checkInDateMonthAndYear") or "",
        "author": info.get("displayMemberName") or "",
        "country": info.get("countryName") or "",
        "traveler_type": info.get("reviewGroupName") or "",
        "room_type": info.get("roomTypeName") or "",
        "nights": info.get("lengthOfStay") if info.get("lengthOfStay") is not None else "",
        "helpful_votes": c.get("helpfulVotes") if c.get("helpfulVotes") is not None else "",
        "reply": c.get("responseText") or "",
        "reply_by": c.get("responderName") or "",
        "reply_date": (c.get("responseDate") or "")[:10],
        "reply_date_text": c.get("responseDateText") or "",
        "language": c.get("translateSource") or "",
        "photos": ";".join(photos),
    }


def fetch_reviews(sess, hotel_id, referer, max_reviews=0, sorting=1,
                  provider_id=AGODA_PROVIDER, on_page=None):
    """Kéo ReviewComments theo trang tới hết / đủ max_reviews (0 = tất cả)."""
    out, page, seen = [], 1, set()
    while True:
        data = _post_json(
            sess, "ReviewComments",
            _review_body(hotel_id, page=page, page_size=PAGE_SIZE,
                         sorting=sorting, provider_id=provider_id),
            referer,
        )
        comments = data.get("comments") or []
        if not comments:
            break
        for c in comments:
            rid = c.get("hotelReviewId")
            if rid in seen:
                continue
            seen.add(rid)
            out.append(parse_comment(c))
            if max_reviews and len(out) >= max_reviews:
                if on_page:
                    on_page(len(out))
                return out[:max_reviews]
        if on_page:
            on_page(len(out))
        if len(comments) < PAGE_SIZE:
            break
        page += 1
        time.sleep(random.uniform(*PAGE_SLEEP))
    return out


def resolve_sort(sort):
    if isinstance(sort, int):
        return sort
    return SORT_MAP.get(str(sort).lower().strip(), 1)


# --------------------------------------------------------------------------- checkpoint
HOTEL_COLS = [
    "input_url", "clean_url", "hotel_name", "property_id",
    "overall_rating", "rating_text", "review_count", "comment_count",
    "provider_comment_count", "fetched_reviews", "subratings",
    "providers_json", "status", "final_url", "crawled_at",
]
REVIEW_COLS = [
    "input_url", "hotel_name", "property_id", "source", "provider_id",
    "review_id", "rating", "rating_text", "title", "text", "text_original",
    "title_original", "positives", "negatives", "review_date",
    "review_date_text", "check_in", "check_out", "stay_month",
    "author", "country", "traveler_type", "room_type", "nights",
    "helpful_votes", "reply", "reply_by", "reply_date", "reply_date_text",
    "language", "photos", "crawled_at",
]


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
def crawl(input, out_dir=".", max_reviews=0, max_hotels=0, sort="recent",
          provider="agoda", sheet="", gid=""):
    """Chạy full: đọc input → crawl từng hotel (resume được) → FINAL csv.

    input       : URL Google Sheet, hoặc file CSV/XLSX/TXT
    out_dir     : thư mục output (TEMP_/FINAL_)
    max_reviews : số review tối đa mỗi hotel (0 = lấy hết theo provider)
    max_hotels  : chỉ crawl N hotel đầu (0 = tất cả)
    sort        : recent | helpful | rating_high | rating_low
    provider    : "agoda" (332) | "all" (lần lượt mọi provider) | số providerId
    """
    import pandas as pd

    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    temp_h = os.path.join(out_dir, "TEMP_agoda_hotels.csv")
    temp_r = os.path.join(out_dir, "TEMP_agoda_reviews.csv")
    sorting = resolve_sort(sort)

    links = read_links(input, sheet, gid)
    if max_hotels:
        links = links[:max_hotels]
    hotels_df = _load_csv(temp_h, HOTEL_COLS)
    reviews_df = _load_csv(temp_r, REVIEW_COLS)
    done = set(hotels_df.loc[hotels_df["status"] == "ok", "input_url"])
    if len(hotels_df):
        print(f"📂 Resume: {len(hotels_df)} hotel trong checkpoint, "
              f"{len(done)} đã ok — sẽ bỏ qua", flush=True)

    fresh = [x for x in links if x[0] not in set(hotels_df["input_url"])]
    redo = [x for x in links if x[0] in set(hotels_df["input_url"]) and x[0] not in done]
    work = fresh + redo
    print(f"🚀 {len(links)} hotel trong input | crawl {len(work)} "
          f"(mới {len(fresh)}, retry {len(redo)}) | max_reviews="
          f"{max_reviews or 'ALL'} | sort={sort}({sorting}) | provider={provider}",
          flush=True)

    sess = make_session()
    for i, (url, custom_name) in enumerate(work, 1):
        row = {c: "" for c in HOTEL_COLS}
        row["input_url"] = url
        row["crawled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        got_rows = []
        try:
            info = resolve_hotel(sess, url)
            pid = info["property_id"]
            referer = info["final_url"] or url
            summary = fetch_summary(sess, pid, referer, provider_id=AGODA_PROVIDER)
            name = custom_name or summary.get("hotel_name") or info.get("hotel_name") or ""
            print(f"\n🏨 {i}/{len(work)} {name[:58]}", flush=True)
            print(f"   ⭐ {summary.get('overall_rating')} ({summary.get('rating_text')}) | "
                  f"{summary.get('review_count')} đánh giá | "
                  f"propertyId={pid}", flush=True)
            if summary.get("subratings"):
                print(f"   📊 {summary['subratings'][:90]}", flush=True)

            # chọn provider(s) để kéo comment
            providers = summary.get("providers") or []
            if str(provider).lower() in ("all", "*"):
                provider_ids = [p["provider_id"] for p in providers if p.get("provider_id")]
                if not provider_ids:
                    provider_ids = [AGODA_PROVIDER]
            elif str(provider).lower() in ("agoda", "default", ""):
                provider_ids = [AGODA_PROVIDER]
            else:
                provider_ids = [int(provider)]

            def _progress(n):
                if n and n % 200 == 0:
                    print(f"   … đã lấy {n} review", flush=True)

            revs, remain = [], max_reviews
            for pvid in provider_ids:
                chunk = fetch_reviews(
                    sess, pid, referer,
                    max_reviews=remain if remain else 0,
                    sorting=sorting, provider_id=pvid, on_page=_progress,
                )
                revs.extend(chunk)
                if max_reviews:
                    remain = max_reviews - len(revs)
                    if remain <= 0:
                        revs = revs[:max_reviews]
                        break

            crawl_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
            for rv in revs:
                rv_row = {c: "" for c in REVIEW_COLS}
                rv_row.update({k: ("" if v is None else v) for k, v in rv.items()
                               if k in REVIEW_COLS})
                rv_row["input_url"] = url
                rv_row["hotel_name"] = name
                rv_row["property_id"] = pid
                rv_row["crawled_at"] = crawl_dt
                got_rows.append(rv_row)

            row.update({
                "clean_url": info["clean_url"],
                "hotel_name": name,
                "property_id": pid,
                "overall_rating": "" if summary.get("overall_rating") is None
                                 else summary["overall_rating"],
                "rating_text": summary.get("rating_text") or "",
                "review_count": "" if summary.get("review_count") is None
                               else summary["review_count"],
                "comment_count": "" if summary.get("comment_count") is None
                                else summary["comment_count"],
                "provider_comment_count": "" if summary.get("provider_comment_count") is None
                                         else summary["provider_comment_count"],
                "fetched_reviews": len(revs),
                "subratings": summary.get("subratings") or "",
                "providers_json": summary.get("raw_providers") or "",
                "status": "ok",
                "final_url": info["final_url"],
            })
            print(f"   ✅ lấy được {len(revs)} review", flush=True)
        except Blocked as e:
            row.update({"status": "blocked"})
            print(f"   🚫 bị chặn ({e}) — nghỉ rồi tiếp hotel sau", flush=True)
            time.sleep(random.uniform(*BLOCK_COOLDOWN))
        except Exception as e:
            row.update({"status": f"error:{type(e).__name__}:{str(e)[:60]}"})
            print(f"   ❌ {type(e).__name__}: {str(e)[:90]}", flush=True)

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
    ap = argparse.ArgumentParser(description="Crawl Agoda hotel reviews & ratings")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=".")
    ap.add_argument("--max-reviews", type=int, default=0)
    ap.add_argument("--max-hotels", type=int, default=0)
    ap.add_argument("--sort", default="recent")
    ap.add_argument("--provider", default="agoda",
                    help="agoda | all | numeric providerId")
    a = ap.parse_args()
    crawl(a.input, a.out, a.max_reviews, a.max_hotels, a.sort, a.provider)
