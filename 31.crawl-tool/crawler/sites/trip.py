# -*- coding: utf-8 -*-
"""Trip.com adapter. Parsers ported verbatim from `crawl price TRIP - 1.ipynb`.

NOTE on direct_replay: Trip serves the room list from `getHotelRoomList`, which may sign each
request (nonce/timestamp) — replay-with-shifted-date is unverified. So `direct_replay` starts
False (browser-per-query, exactly like the current notebook). Milestone M5 flips it to True
once a capture->replay gate passes. The plumbing already supports either mode.
"""
import re
from datetime import timedelta

from .base import SiteAdapter
from ..common import to_int, norm, tokens


def parse_vnd(text):
    if not text:
        return None
    m = re.search(r"VND\s*([\d.,]+)", str(text), re.I)
    if not m:
        m = re.search(r"([\d][\d.,]{3,})", str(text))
    if not m:
        return None
    v = to_int(m.group(1))
    return v if v and v >= 1000 else None


def fmt_vnd(v):
    return f"VND {v:,}"


def pick_room(name2prices, target):
    """Best room match -> (name, min price). Token-based (Trip variant)."""
    if not name2prices:
        return None, None
    tnorm = norm(target)
    ttok = tokens(target)
    for name, prices in name2prices.items():            # 1) exact normalized match
        if norm(name) == tnorm and prices:
            return name, min(prices)
    best, best_score = None, -1.0                        # 2) token coverage
    for name, prices in name2prices.items():
        if not prices:
            continue
        ntok = tokens(name)
        if not ntok:
            continue
        score = len(ttok & ntok) / max(len(ttok), 1)
        if ttok <= ntok or ntok <= ttok:
            score += 0.5
        if score > best_score:
            best_score, best = score, (name, min(prices))
    return best if (best and best_score >= 0.5) else (None, None)


def sale_price(pinfo, ptype="total_incl_tax"):
    pinfo = pinfo or {}
    if ptype == "total_incl_tax":
        return parse_vnd(pinfo.get("priceExplanation")) or parse_vnd(pinfo.get("displayPrice"))
    if ptype == "display":
        v = parse_vnd(pinfo.get("displayPrice"))
        if v:
            return v
        p = pinfo.get("price")
        return int(p) if isinstance(p, (int, float)) and p >= 1000 else None
    if ptype == "original":
        p = pinfo.get("deletePricewithOutCurrency")
        if isinstance(p, (int, float)) and p >= 1000:
            return int(p)
        return parse_vnd(pinfo.get("deletePrice"))
    return None


def extract_from_api(api, target_room, ptype="total_incl_tax"):
    d = (api or {}).get("data") or {}
    phys = d.get("physicRoomMap") or {}
    sales = d.get("saleRoomMap") or {}
    id2name = {str(k): (v.get("name") or "").strip() for k, v in phys.items()}
    name2prices = {}
    for sid, sr in sales.items():
        pid = str(sr.get("physicalRoomId") or "")
        name = id2name.get(pid) or (sr.get("name") or "").strip()
        if not name:
            continue
        p = sale_price(sr.get("priceInfo") or {}, ptype)
        if p:
            name2prices.setdefault(name, []).append(p)
    name, price = pick_room(name2prices, target_room)
    if price:
        return {"found": True, "price": fmt_vnd(price), "room": name}
    if d.get("isRoomListSoldOut"):
        return {"found": False, "soldOut": True}
    # No priced rooms AND no sold-out flag AND no room maps at all = soft-block, not NA.
    if not phys and not sales:
        return {"found": False, "soldOut": False, "blocked": True}
    return {"found": False, "soldOut": False, "rooms": list(name2prices.keys())}


EXTRACT_DOM_JS = r"""() => {
  const cards = document.querySelectorAll("div[class*='commonRoomCard__'], div[class*='saleRoomItemBox__']");
  const rooms = [];
  cards.forEach(c => {
    const t = c.querySelector("span[class*='commonRoomCard-title'], [class*='saleRoomItemBox-head-title'], h2");
    rooms.push({name: t ? t.textContent.trim() : '', text: (c.innerText || '')});
  });
  const body = document.body.innerText || '';
  return {rooms, soldOut: /sold\s*out|hết\s*phòng/i.test(body) && cards.length === 0};
}"""


def extract_from_dom(dom, target_room, ptype="total_incl_tax"):
    name2prices = {}
    for r in (dom.get("rooms") or []):
        name = (r.get("name") or "").strip()
        if not name:
            continue
        text = r.get("text") or ""
        v = None
        if ptype == "total_incl_tax":
            m = re.search(r"Total\s*\(incl[^)]*\)\s*:?\s*(VND\s*[\d.,]+)", text, re.I)
            if not m:
                m = re.search(r"Tổng\s*giá[^\d]*([\d.,]+)", text, re.I)
            if m:
                v = parse_vnd(m.group(1))
        if v is None:
            v = parse_vnd(text)
        if v:
            name2prices.setdefault(name, []).append(v)
    name, price = pick_room(name2prices, target_room)
    if price:
        return {"found": True, "price": fmt_vnd(price), "room": name}
    if dom.get("soldOut"):
        return {"found": False, "soldOut": True}
    return {"found": False, "soldOut": False, "rooms": list(name2prices.keys())}


class TripAdapter(SiteAdapter):
    name = "trip"
    api_hint = "getHotelRoomList"
    direct_replay = False         # flip to True after M5 replay gate passes
    price_prefix = "VND "
    dom_extract_js = EXTRACT_DOM_JS

    def update_url_checkin(self, url, checkin):
        # Keep the original host (vn/www/ca.trip.com) so room names come back in the language
        # that matches room_type in the CSV. Only set checkIn/checkOut + curr.
        ci = checkin.strftime("%Y-%m-%d")
        co = (checkin + timedelta(days=1)).strftime("%Y-%m-%d")
        url = re.sub(r"check[Ii]n=[\d-]+", f"checkIn={ci}", url) if re.search(r"check[Ii]n=", url) \
            else url + f"{'&' if '?' in url else '?'}checkIn={ci}"
        url = re.sub(r"check[Oo]ut=[\d-]+", f"checkOut={co}", url) if re.search(r"check[Oo]ut=", url) \
            else url + f"&checkOut={co}"
        if "curr=" not in url.lower():
            url += f"&curr={self.cfg.currency}"
        return url

    def response_has_rooms(self, resp_json):
        d = (resp_json or {}).get("data") or {}
        return bool(d.get("physicRoomMap") or d.get("saleRoomMap"))

    def response_is_definitive(self, resp_json):
        """Rooms-bearing OR confirmed sold-out. Empty skeleton is NOT definitive — keep scrolling."""
        if self.response_has_rooms(resp_json):
            return True
        d = (resp_json or {}).get("data") or {}
        return bool(d.get("isRoomListSoldOut"))

    def extract(self, resp_json, target_room):
        return extract_from_api(resp_json, target_room, ptype="total_incl_tax")

    def extract_from_dom(self, dom, target_room):
        return extract_from_dom(dom, target_room, ptype="total_incl_tax")
