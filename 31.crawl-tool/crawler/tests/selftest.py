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

    from crawler.config import Config
    from crawler.sites import get_adapter
    a = get_adapter("agoda", Config())
    check("definitive: rooms present", a.response_is_definitive(priced))
    check("definitive: genuine full sold-out (no rooms will ever come)",
          a.response_is_definitive(genuine_soldout))
    check("NOT definitive: bare empty payload (soft-block, keep waiting)",
          not a.response_is_definitive(soft_block) and not a.response_is_definitive(None))


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


def test_gsheet_parse():
    print("[google sheet URL parsing]")
    from crawler.hotels_io import _parse_gsheet, _gsheet_url, is_gsheet
    full = "https://docs.google.com/spreadsheets/d/ABC123_-x/edit?gid=1289817800#gid=1289817800"
    sid, gid = _parse_gsheet(full)
    check("extracts spreadsheet id", sid == "ABC123_-x")
    check("extracts gid (tab id) from URL", gid == "1289817800")
    check("is_gsheet detects full URL", is_gsheet(full) and not is_gsheet("agoda1.csv"))
    check("gviz url uses gid", "gid=1289817800" in _gsheet_url(full))
    sid2, gid2 = _parse_gsheet("gsheet:XYZ:456")
    check("gsheet:<id>:<gid> form", sid2 == "XYZ" and gid2 == "456")


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


def test_resume_order():
    print("[resume order: fresh hotels before NA/SOLD-OUT retries]")
    from crawler.config import Config
    from crawler.orchestrate import _resume_order
    # simulate: hotels 1-3 already in checkpoint (partial), 4-5 never crawled
    prev = {("H1", "R"): {}, ("H2", "R"): {}, ("H3", "R"): {}}
    work = [(i, f"H{i}", f"u{i}", "R", (f"H{i}", "R"), [1]) for i in range(1, 6)]
    fresh, redo = _resume_order(work, prev)
    check("never-crawled hotels come first", [w[1] for w in fresh] == ["H4", "H5"])
    check("checkpointed hotels retry after", [w[1] for w in redo] == ["H1", "H2", "H3"])
    check("input order kept inside each group", [w[0] for w in fresh + redo] == [4, 5, 1, 2, 3])
    fresh2, redo2 = _resume_order(work, {})
    check("fresh run (no checkpoint) keeps input order", [w[0] for w in fresh2 + redo2] == [1, 2, 3, 4, 5])
    check("resume_new_first defaults on", Config().resume_new_first is True)


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


async def test_direct_fail_fast():
    print("[direct replay — dead-capture abort + clean-sweep trust]")
    from crawler import orchestrate
    from crawler.config import Config
    from crawler.pace import AdaptivePacer
    from crawler.sites import get_adapter

    cfg = Config()
    cfg.pace_jitter = (0.0, 0.0)
    cfg.pace_block_cooldown = (0.0, 0.0)
    adapter = get_adapter("agoda", cfg)
    base = datetime(2026, 7, 13)
    cap = {"req": {"method": "GET", "url": "u", "headers": {}}, "checkin": "1900-01-01"}
    weeks = list(range(1, 7))
    calls = {"n": 0}
    real_query = orchestrate.query_via_capture

    def fake(payload):
        async def q(sess, cap_, checkin, timeout=30):
            calls["n"] += 1
            return 200, payload
        return q

    try:
        # 1) dead capture: every replay soft-blocked -> abort after ~pace_start queries, not 42
        calls["n"] = 0
        orchestrate.query_via_capture = fake({"rooms": []})
        res = await orchestrate._direct_weeks(
            adapter, None, cap, "Deluxe", base, weeks, 7, AdaptivePacer(cfg), cfg)
        check("dead capture aborts fast (queries << weeks*days)",
              calls["n"] <= cfg.pace_start + cfg.direct_abort_blocks)
        check("aborted weeks are NA and NOT clean (browser will handle them)",
              all(r["price"] == "NA" and not r["clean"] for r in res))

        # 2) clean sold-out sweep: definitive verdicts all week -> SOLD OUT trusted, clean=True
        calls["n"] = 0
        orchestrate.query_via_capture = fake(
            {"rooms": [], "isSoldOut": True, "propertyName": "X",
             "searchCriteriaDescription": "1 room 2 adults"})
        res = await orchestrate._direct_weeks(
            adapter, None, cap, "Deluxe", base, weeks, 7, AdaptivePacer(cfg), cfg)
        check("unblocked sold-out sweep -> SOLD OUT + clean (skips browser re-verify)",
              all(r["price"] == "SOLD OUT" and r["clean"] for r in res))

        # 3) priced day 1 -> one query per week, real price, clean
        calls["n"] = 0
        orchestrate.query_via_capture = fake(
            {"rooms": [{"name": "Deluxe", "offers": [{"price": {"final": {"amountNumber": 2000000}}}]}]})
        res = await orchestrate._direct_weeks(
            adapter, None, cap, "Deluxe", base, weeks, 7, AdaptivePacer(cfg), cfg)
        check("priced sweep: 1 query/week", calls["n"] == len(weeks))
        check("priced sweep: real + clean", all(r["price"] == "2,000,000" and r["clean"] for r in res))

        # 4) warm response reuse: cap already holds the answer for W1 day 1 -> no query for it
        calls["n"] = 0
        cap2 = dict(cap, checkin="2026-07-13",
                    resp_json={"rooms": [{"name": "Deluxe", "offers": [
                        {"price": {"final": {"amountNumber": 3000000}}}]}]})
        res = await orchestrate._direct_weeks(
            adapter, None, cap2, "Deluxe", base, weeks, 7, AdaptivePacer(cfg), cfg)
        check("W1 day1 answered from warm capture (no extra query)",
              calls["n"] == len(weeks) - 1 and res[0]["price"] == "3,000,000")
    finally:
        orchestrate.query_via_capture = real_query


async def test_browser_breaker():
    print("[browser fallback — per-hotel circuit breaker]")
    from crawler import warm
    from crawler.config import Config
    cfg = Config()
    b = warm.new_breaker()
    warm.breaker_note_block(b, cfg.block_circuit_limit, tag="t")
    check("one blocked day does not trip", not b["tripped"])
    warm.breaker_note_block(b, cfg.block_circuit_limit, tag="t")
    check(f"trips after {cfg.block_circuit_limit} consecutive blocked days", b["tripped"])

    b2 = warm.new_breaker()
    warm.breaker_note_ok(b2)
    for _ in range(5):
        warm.breaker_note_block(b2, cfg.block_circuit_limit, tag="t")
    check("a hotel that responded once NEVER trips", not b2["tripped"])

    r = await warm.browser_crawl_day(None, None, "http://x", "Deluxe",
                                     datetime(2026, 7, 13), cfg, None, breaker=b)
    check("tripped breaker -> instant skipped-blocked (no nav, no timeout burned)",
          r.get("skipped") and r.get("blocked"))


def test_property_swap():
    print("[shared capture — propertyId swap]")
    from crawler.replay import property_id, swap_property
    body = '{"clientApplicationName":"capybara","propertyId":400138,' \
           '"searchCriteria":{"checkIn":"2026-07-14","checkOut":"2026-07-15"}}'
    req = {"method": "POST", "url": "https://www.agoda.com/api/v1/property/room-grid",
           "headers": {}, "post_data": body}
    check("property_id reads the body pid", property_id(req) == "400138")
    swapped = swap_property(req, "5945467")
    check("swap changes ONLY the pid", '"propertyId":5945467' in swapped["post_data"]
          and '"checkIn":"2026-07-14"' in swapped["post_data"]
          and "400138" not in swapped["post_data"])
    check("swap leaves original req untouched", req["post_data"] == body)
    check("swap with None pid is a no-op", swap_property(req, None)["post_data"] == body)
    check("property_id None on GET-style body", property_id({"post_data": ""}) is None)


def test_capstore_property_id():
    print("[capture cache — propertyId persistence]")
    from crawler import capstore
    from crawler.config import Config
    cfg = Config()
    with tempfile.TemporaryDirectory() as td:
        cfg.capture_dir = os.path.join(td, "captures")
        cfg.capture_max_age_h = 48.0
        url = "https://www.agoda.com/x/hotel/hoi-an-vn.html"
        cap = {"req": {"method": "POST", "url": "u",
                       "post_data": '{"propertyId":661142,"searchCriteria":{}}'},
               "checkin": "2026-07-14", "cookies": []}
        capstore.save(cfg, "agoda", url, cap)
        check("save records property_id", capstore.cached_property_id(cfg, "agoda", url) == "661142")
        import time
        # pid lookup ignores TTL (a propertyId is permanent) even when load() expires it
        check("cached_property_id ignores TTL",
              capstore.cached_property_id(cfg, "agoda", url) == "661142")
        old = capstore.load(cfg, "agoda", url, now=time.time() + 100 * 3600)
        check("load() still honours TTL", old is None)
        check("unknown url pid -> None", capstore.cached_property_id(cfg, "agoda", "https://z") is None)


def test_roommatch():
    print("[room matching — bilingual synonym matcher]")
    from crawler.roommatch import best_room, canon

    def rooms(*names):
        return [{"name": n, "offers": [{"price": {"final": {"amountNumber": 2000000}}}]} for n in names]

    rm, method = best_room(rooms("Chic Suite", "Standard Double"), "Chic Suite")
    check("exact still matches", rm and rm["name"] == "Chic Suite" and method == "exact")

    # the real 2026-07-09 false-NA: sheet EN vs a vi-vn grid
    grid = rooms("Phòng Loại Sang (Deluxe Room)", "Phòng Tiêu Chuẩn", "Phòng Giường Đôi Cao Cấp")
    rm, method = best_room(grid, "Deluxe Room")
    check("EN target matches VN 'Loại Sang' grid",
          rm and "Loại Sang" in rm["name"], )

    rm, _ = best_room(rooms("Superior King Room", "Deluxe Twin"), "Phòng Giường Lớn Cao Cấp")
    check("VN target 'Giường Lớn Cao Cấp' -> Superior King", rm and rm["name"] == "Superior King Room")

    rm, _ = best_room(rooms("Deluxe Double with Garden View", "Superior Twin"),
                      "Phòng Loại Sang Giường Đôi Hướng Vườn")
    check("multi-attribute VN -> Deluxe Double Garden", rm and "Garden" in rm["name"])

    rm, method = best_room(rooms("Presidential Suite", "Royal Villa"), "Standard Twin Room")
    check("genuine mismatch -> None (never false-match)", rm is None and method.startswith("below"))

    check("canon collapses deluxe synonyms", canon("Phòng Loại Sang") == canon("Deluxe Room"))
    check("canon collapses view synonyms", "gardenview" in canon("Hướng Vườn"))


def test_capstore():
    print("[capture cache]")
    import time
    from crawler import capstore
    from crawler.config import Config
    cfg = Config()
    with tempfile.TemporaryDirectory() as td:
        cfg.capture_dir = os.path.join(td, "captures")
        url = "https://www.agoda.com/some-hotel/hotel/hoi-an-vn.html?cid=1"
        cap = {"req": {"method": "POST", "url": "https://agoda.com/api?x=1",
                       "headers": {"h": "1"}, "post_data": "{}"},
               "checkin": "2026-07-14", "cookies": [{"name": "_abck", "value": "v"}],
               "impersonate": "firefox147", "engine": "camoufox",
               "resp_json": {"rooms": [1]}, "xhr_urls": ["u"]}
        capstore.save(cfg, "agoda", url, cap)
        got = capstore.load(cfg, "agoda", url)
        check("roundtrip keeps req/cookies/impersonate",
              got is not None and got["req"]["url"].endswith("x=1")
              and got["cookies"][0]["name"] == "_abck" and got["impersonate"] == "firefox147")
        check("bulky fields stripped, resp_json reset",
              got is not None and got.get("resp_json") is None and "xhr_urls" not in got)
        check("unknown url -> None", capstore.load(cfg, "agoda", "https://other") is None)
        check("expired -> None",
              capstore.load(cfg, "agoda", url, now=time.time() + 49 * 3600) is None)
        check("within max age -> served",
              capstore.load(cfg, "agoda", url, now=time.time() + 24 * 3600) is not None)
        capstore.invalidate(cfg, "agoda", url)
        check("invalidate removes", capstore.load(cfg, "agoda", url) is None)
        capstore.invalidate(cfg, "agoda", url)   # second call must not raise
        check("invalidate idempotent", True)
        capstore.save(cfg, "agoda", "https://agoda.com/y", {"req": None})
        check("dead capture never saved",
              capstore.load(cfg, "agoda", "https://agoda.com/y") is None)


async def test_probe_capture():
    print("[capture probe — cached sessions verified before trust]")
    from crawler import orchestrate
    from crawler.config import Config
    from crawler.pace import AdaptivePacer
    from crawler.sites import get_adapter

    cfg = Config()
    cfg.pace_jitter = (0.0, 0.0)
    cfg.pace_block_cooldown = (0.0, 0.0)
    adapter = get_adapter("agoda", cfg)
    base = datetime(2026, 7, 14)

    def cap():
        return {"req": {"method": "POST", "url": "https://x/api?checkIn=2026-07-01",
                        "headers": {}, "post_data": '{"checkIn":"2026-07-01","checkOut":"2026-07-02"}'},
                "checkin": "2026-07-01"}

    real_query = orchestrate.query_via_capture

    def fake(payload, status=200):
        async def q(sess, cap_, checkin, timeout=30):
            return status, payload
        return q

    try:
        live = {"rooms": [{"name": "Deluxe", "offers": []}]}
        orchestrate.query_via_capture = fake(live)
        c = cap()
        ok = await orchestrate._probe_capture(adapter, None, c, base, AdaptivePacer(cfg), cfg)
        check("live probe -> True", ok)
        check("probe re-dates req to W1 day 1",
              "2026-07-14" in c["req"]["post_data"] and c["checkin"] == "2026-07-14")
        check("probe seeds resp_json (no extra query for W1D1)", c.get("resp_json") == live)

        orchestrate.query_via_capture = fake({"rooms": []})   # Akamai rejected: empty skeleton
        c2 = cap()
        check("soft-blocked probe -> False",
              not await orchestrate._probe_capture(adapter, None, c2, base, AdaptivePacer(cfg), cfg))
        check("dead probe leaves req untouched", c2["checkin"] == "2026-07-01")

        orchestrate.query_via_capture = fake(live, status=403)
        check("HTTP 403 probe -> False",
              not await orchestrate._probe_capture(adapter, None, cap(), base, AdaptivePacer(cfg), cfg))
    finally:
        orchestrate.query_via_capture = real_query


async def test_shared_prepass():
    print("[shared capture — pre-pass trust rule]")
    from crawler import orchestrate, warm, capstore
    from crawler.config import Config
    from crawler.pace import AdaptivePacer

    cfg = Config()
    cfg.pace_jitter = (0.0, 0.0)
    cfg.pace_block_cooldown = (0.0, 0.0)
    cfg.days_per_week = 1
    with tempfile.TemporaryDirectory() as td:
        cfg.capture_dir = os.path.join(td, "captures")
        # two hotels with cached propertyIds, one without
        priced_url = "https://www.agoda.com/priced/hotel/x.html"
        so_url = "https://www.agoda.com/soldout/hotel/x.html"
        cold_url = "https://www.agoda.com/cold/hotel/x.html"
        for u, pid in [(priced_url, 111), (so_url, 222)]:
            capstore.save(cfg, "agoda", u, {"req": {"method": "POST", "url": "u",
                          "post_data": '{"propertyId":%d,"searchCriteria":{"checkIn":"2026-07-14","checkOut":"2026-07-15"}}' % pid},
                          "checkin": "2026-07-14", "cookies": []})
        hotels = [("Priced Hotel", priced_url, "Deluxe"),
                  ("SoldOut Hotel", so_url, "Deluxe"),
                  ("Cold Hotel", cold_url, "Deluxe")]
        awp = {}

        real_warm, real_query, real_sess = warm.warm_capture, orchestrate.query_via_capture, orchestrate.make_session

        async def fake_warm(adapter, url, base, cfg_, **kw):
            return {"req": {"method": "POST", "url": "u",
                            "post_data": '{"propertyId":999,"searchCriteria":{"checkIn":"2026-07-14","checkOut":"2026-07-15"}}'},
                    "checkin": "2026-07-14", "cookies": [], "impersonate": "chrome131"}

        def fake_query_factory():
            async def q(sess, cap, checkin, timeout=30):
                pid = orchestrate.property_id(cap["req"]) if hasattr(orchestrate, "property_id") else None
                # hotel 111 -> priced; hotel 222 -> genuine-sold-out shell (must NOT be trusted)
                from crawler.replay import property_id
                pid = property_id(cap["req"])
                if pid == "111":
                    return 200, {"rooms": [{"name": "Deluxe",
                                 "offers": [{"price": {"final": {"amountNumber": 3000000}}}]}]}
                return 200, {"rooms": [], "isSoldOut": True, "propertyName": "Big Chain",
                             "searchCriteriaDescription": "1 room"}
            return q

        from datetime import datetime as _dt
        base = _dt(2026, 7, 14)
        warm.warm_capture = fake_warm
        orchestrate.query_via_capture = fake_query_factory()
        orchestrate.make_session = lambda imp=None: type("S", (), {"close": lambda self: None,
                                                                    "cookies": object()})()
        try:
            filled = await orchestrate._shared_prepass(
                orchestrate.get_adapter("agoda", cfg), object(), None, None, hotels,
                base, 6, awp, AdaptivePacer(cfg), cfg, os.path.join(td, "T.csv"))
        finally:
            warm.warm_capture, orchestrate.query_via_capture, orchestrate.make_session = \
                real_warm, real_query, real_sess

        pk = ("Priced Hotel", "Deluxe")
        sk = ("SoldOut Hotel", "Deluxe")
        check("priced hotel filled from shared session", awp.get(pk, {}).get("Price W1") == "3,000,000")
        check("sold-out shell NOT trusted (stays NA)",
              all(awp.get(sk, {}).get(f"Price W{i}", "NA") == "NA" for i in range(1, 7)))
        check("cold hotel (no cached pid) skipped by pre-pass",
              ("Cold Hotel", "Deluxe") not in awp)
        check("filled count = priced cells only", filled == 6)


def test_export_cookies():
    print("[cookie export]")
    from crawler.session import export_cookies

    class _C:
        def __init__(self, n, v):
            self.name, self.value, self.domain, self.path = n, v, ".agoda.com", "/"

    class _Cookies:
        jar = [_C("_abck", "fresh")]

    class _Sess:
        cookies = _Cookies()

    out = export_cookies(_Sess(), fallback=[{"name": "old", "value": "1"}])
    check("reads freshest jar", out and out[0]["name"] == "_abck" and out[0]["value"] == "fresh")

    class _Bad:
        cookies = object()

    out2 = export_cookies(_Bad(), fallback=[{"name": "old", "value": "1"}])
    check("broken jar -> fallback list", out2 == [{"name": "old", "value": "1"}])


async def test_iprotate():
    print("[ip rotation — v4/v6 detection]")
    from crawler import iprotate
    real = iprotate._fetch
    try:
        async def only_v6(url, timeout):
            return "2401:abcd::1" if "6" in url else None
        iprotate._fetch = only_v6
        v4, v6 = await iprotate.public_ips()
        check("v6-only network detected", v4 is None and v6 == "2401:abcd::1")
        check("public_ip falls back to v6", (await iprotate.public_ip()) == "2401:abcd::1")

        async def both(url, timeout):
            return "203.0.113.5" if ("6" not in url) else "2401:abcd::9"
        iprotate._fetch = both
        v4, v6 = await iprotate.public_ips()
        check("both families detected", v4 == "203.0.113.5" and v6 == "2401:abcd::9")
        check("public_ip prefers v4", (await iprotate.public_ip()) == "203.0.113.5")

        from crawler.config import Config
        old, new, changed = await iprotate.rotate(Config())   # rotate_ip_cmd empty
        check("rotate no-op when unset", changed is False and old is None)
    finally:
        iprotate._fetch = real


def test_envcheck():
    print("[env preflight]")
    import io
    import contextlib as _ctx
    from crawler import envcheck
    check("has(): stdlib import visible", envcheck.has("json"))
    check("has(): nonsense import invisible", not envcheck.has("definitely_not_a_pkg_xyz"))
    buf = io.StringIO()
    with _ctx.redirect_stdout(buf):
        missing = envcheck.check(verbose=False)
    check("this interpreter has every REQUIRED package", missing == [])
    check("pip hint targets THIS interpreter, never a bare `pip`",
          envcheck.pip_hint(["x"]).startswith(sys.executable))


def test_cli():
    print("[cli parsing]")
    from crawler.cli import build_parser
    a = build_parser().parse_args(["crawl", "--site", "trip", "--input", "gsheet:ABC",
                                   "--shard", "2/5", "--weeks", "6", "--engine", "chromium"])
    check("crawl args parse", a.cmd == "crawl" and a.site == "trip" and a.shard == "2/5" and a.engine == "chromium")
    c = build_parser().parse_args(["capture", "--site", "agoda", "--url", "http://x", "--no-headless"])
    check("capture args + --no-headless", c.cmd == "capture" and c.headless is False)
    d = build_parser().parse_args(["doctor"])
    check("doctor subcommand parses", d.cmd == "doctor")
    e = build_parser().parse_args(["crawl", "--input", "x.csv", "--shared-capture",
                                   "--room-match-llm"])
    from crawler.cli import _cfg_from
    cfg = _cfg_from(e)
    check("opt-in flags reach cfg", cfg.shared_capture and cfg.room_match_llm)
    s = build_parser().parse_args(["shared-gate", "--url", "http://a", "--url2", "12345"])
    check("shared-gate subcommand parses", s.cmd == "shared-gate" and s.url2 == "12345")


def main():
    test_imports()
    test_agoda_parser()
    test_trip_parser()
    test_date_shift()
    test_impersonate_pairing()
    test_adapters_url()
    test_shard()
    test_gsheet_parse()
    test_dates()
    test_checkpoint_and_merge()
    test_resume_order()
    asyncio.run(test_pacer())
    asyncio.run(test_direct_fail_fast())
    asyncio.run(test_browser_breaker())
    test_roommatch()
    test_property_swap()
    test_capstore()
    test_capstore_property_id()
    asyncio.run(test_probe_capture())
    asyncio.run(test_shared_prepass())
    test_export_cookies()
    asyncio.run(test_iprotate())
    test_envcheck()
    test_cli()
    print(f"\n{'='*48}\n  {_PASS} passed, {_FAIL} failed\n{'='*48}")
    return 1 if _FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
