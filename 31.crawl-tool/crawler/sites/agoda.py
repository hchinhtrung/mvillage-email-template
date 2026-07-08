# -*- coding: utf-8 -*-
"""Agoda adapter. Parsers ported verbatim from `crawl price AGODA - 1.ipynb` /
`_direct_api/agoda_direct.py` (proven against real Agoda data)."""
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .base import SiteAdapter
from ..common import to_int, norm, tokens

JUNK_URL_PARAMS = {"searchrequestid", "ds", "searchtoken", "flightsearchcriteria",
                   "showreviewsubmissionentry", "iscalendarcallout"}


def parse_amount(text):
    if text is None:
        return None
    m = re.search(r"([\d][\d.,]{3,})", str(text))
    if not m:
        return None
    v = to_int(m.group(1))
    return v if v and v >= 1000 else None


def fmt_price(v):
    return f"{v:,}"


def _best_room(rooms, target):
    named = [(rm, (rm.get("name") or "").strip()) for rm in rooms]
    named = [(rm, n) for rm, n in named if n]
    if not named:
        return None
    tnorm = norm(target)
    ttok = tokens(target)
    for rm, n in named:
        if norm(n) == tnorm:
            return rm
    tfirst = tnorm.split()[0] if tnorm else ""
    best, best_score = None, -1.0
    for rm, n in named:
        ntok = tokens(n)
        if not ntok:
            continue
        score = len(ttok & ntok) / max(len(ttok | ntok), 1)
        nfirst = norm(n).split()[0] if norm(n) else ""
        if tfirst and tfirst == nfirst:
            score += 0.3
        if score > best_score:
            best_score, best = score, rm
    return best if best_score >= 0.5 else None


def agoda_offer_price(offer, ptype="final"):
    pr = (offer or {}).get("price") or {}
    if ptype == "cashback":
        node = (pr.get("cashback") or {}).get("price") or {}
    else:
        node = pr.get(ptype) or {}
    v = node.get("amountNumber")
    if isinstance(v, (int, float)) and v >= 1000:
        return int(v)
    return parse_amount(node.get("amount") or node.get("text"))


def extract_from_agoda(rg, target_room, ptype="final"):
    """Empty `rooms` = BLOCKED (soft-block), NOT sold-out — unless the response also carries
    isSoldOut + propertyName + searchCriteriaDescription (a genuine full sold-out)."""
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


class AgodaAdapter(SiteAdapter):
    name = "agoda"
    api_hint = "/api/v1/property/room-grid"
    direct_replay = True          # capture->replay proven (Gate 0/1)
    price_prefix = ""             # Agoda cells are plain grouped numbers e.g. "4,671,429"

    def update_url_checkin(self, url, checkin):
        ci = checkin.strftime("%Y-%m-%d")
        s = urlsplit(url)
        q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True)
             if k.lower() not in JUNK_URL_PARAMS and k.lower() != "checkin"]
        q.append(("checkin", ci))
        low = {k.lower() for k, _ in q}
        if "los" not in low:
            q.append(("los", "1"))
        if "currencycode" not in low:
            q.append(("currencyCode", self.cfg.currency))
        if "finalpriceview" not in low:
            q.append(("finalPriceView", "1"))
        if "adults" not in low:
            q.append(("adults", str(self.cfg.adults)))
        if "rooms" not in low:
            q.append(("rooms", str(self.cfg.rooms)))
        return urlunsplit((s.scheme, s.netloc, s.path, urlencode(q, safe=","), ""))

    def response_has_rooms(self, resp_json):
        return bool((resp_json or {}).get("rooms"))

    def extract(self, resp_json, target_room):
        return extract_from_agoda(resp_json, target_room, ptype="final")
