# -*- coding: utf-8 -*-
"""Network-free self-test for the crawler package.

Exercises everything that is deterministic and IP-independent: parsers (the anti-false-NA
invariant), date shifting, impersonate pairing, sharding, checkpoint only-improve, the
adaptive pacer, adapter URL rewriting, and CLI parsing. The live capture/replay/crawl gates
are IP-bound and MUST be run on the user's machine (see README).

Run:  python -m crawler.tests.selftest
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime

_PASS = 0
_FAIL = 0


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  ✅ {name}")
    else:
        _FAIL += 1
        print(f"  ❌ {name}")


def test_imports():
    print("[imports]")
    import crawler
    from crawler import (config, common, dates, session, replay, pace,
                         warm, hotels_io, checkpoint, iprotate, orchestrate, gates, cli)
    from crawler.sites import get_adapter, AgodaAdapter, TripAdapter
    check("package imports", bool(crawler.__version__))
    check("registry resolves agoda", isinstance(get_adapter("agoda", config.Config()), AgodaAdapter))
    check("registry resolves trip", isinstance(get_adapter("trip", config.Config()), TripAdapter))


def test_agoda_parser():
    print("[agoda parser — anti-false-NA invariant]")
    from crawler.sites.agoda import extract_from_agoda
    priced = {"rooms": [{"name": "Deluxe Double", "offers": [
        {"price": {"final": {"amountNumber": 1234567}}}]}]}
    r = extract_from_agoda(priced, "Deluxe Double")
    check("priced -> found", r.get("found") and r.get("price") == "1,234,567")

    genuine_soldout = {"rooms": [], "isSoldOut": True, "propertyName": "X Hotel",
                       "searchCriteriaDescription": "1 room, 2 adults"}
    r = extract_from_agoda(genuine_soldout, "Deluxe")
    check("empty+metadata -> genuine soldOut", r.get("soldOut") and not r.get("blocked"))

    soft_block = {"rooms": []}  # empty WITHOUT property metadata
    r = extract_from_agoda(soft_block, "Deluxe")
    check("empty, no metadata -> BLOCKED (never a price)",
          r.get("blocked") and not r.get("found") and not r.get("soldOut"))

    mismatch = {"rooms": [{"name": "Totally Other Room", "offers": [
        {"price": {"final": {"amountNumber": 999999}}}]}]}
    r = extract_from_agoda(mismatch, "Nonexistent Suite XYZ")
    check("room mismatch -> NA (not found, not blocked)",
          not r.get("found") and not r.get("blocked"))


def test_trip_parser():
    print("[trip parser]")
    from crawler.sites.trip import extract_from_api
    priced = {"data": {
        "physicRoomMap": {"11": {"name": "Superior Room"}},
        "saleRoomMap": {"s1": {"physicalRoomId": 11,
                               "priceInfo": {"priceExplanation": "Total VND 1,070,809"}}}}}
    r = extract_from_api(priced, "Superior Room")
    check("priced -> VND formatted", r.get("found") and r.get("price") == "VND 1,070,809")

    soldout = {"data": {"physicRoomMap": {}, "saleRoomMap": {}, "isRoomListSoldOut": True}}
    r = extract_from_api(soldout, "Superior")
    check("sold-out flag -> soldOut", r.get("soldOut") and not r.get("blocked"))

    block = {"data": {}}  # no maps, no flag
    r = extract_from_api(block, "Superior")
    check("empty data, no flag -> BLOCKED", r.get("blocked"))


def test_date_shift():
    print("[replay date shifting]")
    from crawler.replay import shift_dates, parameterize
    body = '{"searchCriteria":{"checkIn":"2026-07-13","checkOut":"2026-07-14"}}'
    shifted = shift_dates(body, 14)
    check("both dates shift by same delta (window preserved)",
          '"checkIn":"2026-07-27"' in shifted and '"checkOut":"2026-07-28"' in shifted)
    cap_req = {"method": "POST", "url": "https://x/api?checkin=2026-07-13", "headers": {},
               "post_data": body}
    m, u, h, d = parameterize(cap_req, "2026-07-13", "2026-07-20")
    check("parameterize shifts url+body +7d",
          "2026-07-20" in u and '"checkIn":"2026-07-20"' in d and '"checkOut":"2026-07-21"' in d)


def test_impersonate_pairing():
    print("[TLS impersonate pairing]")
    from crawler.session import pick_impersonate
    ff = "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"
    ch = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
    check("camoufox UA -> firefox target", pick_impersonate(ff, "camoufox").startswith("firefox"))
    check("chromium UA -> chrome target", pick_impersonate(ch, "chromium").startswith("chrome"))
    check("override respected", pick_impersonate(ff, "camoufox", "firefox147") == "firefox147")


def test_adapters_url():
    print("[adapter URL rewriting]")
    from crawler.config import Config
    from crawler.sites import get_adapter
    cfg = Config()
    d = datetime(2026, 7, 20)
    a = get_adapter("agoda", cfg).update_url_checkin("https://www.agoda.com/x?searchrequestid=stale&checkin=2020-01-01", d)
    check("agoda sets checkin+los, drops junk", "checkin=2026-07-20" in a and "los=1" in a and "searchrequestid" not in a)
    t = get_adapter("trip", cfg).update_url_checkin("https://vn.trip.com/hotels/detail/?hotelId=1", d)
    check("trip sets checkIn+checkOut+curr, keeps host",
          "checkIn=2026-07-20" in t and "checkOut=2026-07-21" in t and "vn.trip.com" in t)


def test_shard():
    print("[sharding]")
    from crawler.hotels_io import parse_shard, apply_shard
    check("parse '2/5'", parse_shard("2/5") == (2, 5))
    items = list(range(23))
    parts = [apply_shard(items, (n, 5)) for n in range(1, 6)]
    flat = [x for p in parts for x in p]
    check("shards partition fully, no overlap", sorted(flat) == items and len(flat) == 23)
    check("shard sizes near-equal", max(len(p) for p in parts) - min(len(p) for p in parts) <= 1)


def test_dates():
    print("[date generation]")
    from crawler.config import Config
    from crawler.dates import base_checkin, week_days
    cfg = Config()
    base = base_checkin(cfg, today=datetime(2026, 7, 8))
    check("W1 = today + offset", base == datetime(2026, 7, 13))
    check("week_days count = days_per_week", len(week_days(base, 1, cfg.days_per_week)) == 7)
    check("week 3 starts +14d", week_days(base, 3, 1)[0] == datetime(2026, 7, 27))


def test_checkpoint_and_merge():
    print("[checkpoint only-improve + merge invariant]")
    from crawler.checkpoint import save_backup_csv, load_prev
    from crawler.orchestrate import _merge_only_improve
    with tempfile.TemporaryDirectory() as td:
        fp = os.path.join(td, "TEMP_x.csv")
        key = ("Hotel A", "Deluxe")
        save_backup_csv({key: {"Price W1": "1,000", "Price W2": "NA"}}, fp, 2)
        save_backup_csv({key: {"Price W1": "NA", "Price W2": "2,000"}}, fp, 2)  # NA must not clobber W1
        save_backup_csv({key: {"Price W1": "SOLD OUT", "Price W2": "NA"}}, fp, 2)  # SOLD OUT must not clobber W1
        prev = load_prev(fp, 2)
        check("NA does not overwrite real price", prev[key]["Price W1"] == "1,000")
        check("SOLD OUT does not overwrite real price on disk", prev[key]["Price W1"] == "1,000")
        check("real fills previously-NA week", prev[key]["Price W2"] == "2,000")

    cur = {"Price W1": "1,000", "Price W2": "NA", "Price W3": "SOLD OUT"}
    merged = _merge_only_improve(dict(cur),
                                 {"Price W1": "SOLD OUT", "Price W2": "SOLD OUT", "Price W3": "3,000"}, 3)
    check("SOLD OUT does not overwrite real", merged["Price W1"] == "1,000")
    check("SOLD OUT replaces NA", merged["Price W2"] == "SOLD OUT")
    check("real overwrites SOLD OUT", merged["Price W3"] == "3,000")


async def test_pacer():
    print("[adaptive pacer AIMD]")
    from crawler.config import Config
    from crawler.pace import AdaptivePacer, is_block_signal
    cfg = Config()
    cfg.pace_start, cfg.pace_max, cfg.pace_min, cfg.pace_ramp_after = 2, 4, 1, 3
    cfg.pace_block_cooldown = (0.0, 0.0)
    p = AdaptivePacer(cfg)
    async with p.slot():
        check("acquire increments active", p.snapshot()["active"] == 1)
    check("release decrements active", p.snapshot()["active"] == 0)
    start = p.limit
    for _ in range(3):
        p.record_ok()
    check("ramps up after clean streak", p.limit == start + 1)
    before = p.limit
    p.record_block()
    check("halves on block", p.limit == max(cfg.pace_min, before // 2))
    check("block signal: HTTP 429", is_block_signal(429, {}))
    check("block signal: adapter blocked", is_block_signal(200, {"blocked": True}))
    check("not a block: priced 200", not is_block_signal(200, {"found": True}))


def test_cli():
    print("[cli parsing]")
    from crawler.cli import build_parser
    a = build_parser().parse_args(["crawl", "--site", "trip", "--input", "gsheet:ABC",
                                   "--shard", "2/5", "--weeks", "6", "--engine", "chromium"])
    check("crawl args parse", a.cmd == "crawl" and a.site == "trip" and a.shard == "2/5" and a.engine == "chromium")
    c = build_parser().parse_args(["capture", "--site", "agoda", "--url", "http://x", "--no-headless"])
    check("capture args + --no-headless", c.cmd == "capture" and c.headless is False)


def main():
    test_imports()
    test_agoda_parser()
    test_trip_parser()
    test_date_shift()
    test_impersonate_pairing()
    test_adapters_url()
    test_shard()
    test_dates()
    test_checkpoint_and_merge()
    asyncio.run(test_pacer())
    test_cli()
    print(f"\n{'='*48}\n  {_PASS} passed, {_FAIL} failed\n{'='*48}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
