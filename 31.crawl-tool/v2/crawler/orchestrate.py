# -*- coding: utf-8 -*-
"""Per-hotel hybrid crawl + the full run loop (resume, adaptive pacing, retry rounds).

Round 1: crawl every hotel (direct replay + browser fallback).
Round 2: browser re-crawl of every cell still NA / SOLD OUT (auto_retry_na_soldout).
Round 3: long-cooldown browser retry of hotels whose breaker tripped (retry_blocked_hotels).
"""
import asyncio
import contextlib
import os
import random
import time
from dataclasses import replace as _cfg_replace
from datetime import datetime, timedelta

from .common import is_real
from .config import Config
from .dates import base_checkin, week_days
from . import capstore, checkpoint, envcheck, hotels_io, iprotate, warm
from .pace import AdaptivePacer, is_block_signal
from .replay import parameterize, query_via_capture, swap_property
from .session import make_session, load_cookies, export_cookies
from .sites import get_adapter


# --------------------------------------------------------------------------- direct replay
async def _direct_weeks(adapter, sess, cap, room_type, base, weeks, days, pacer, cfg):
    """Replay every (week, day) via curl_cffi. Two fail-fast properties bound the cost:

    * dead-capture abort — a capture whose replays only ever return block signals is dead
      (Akamai rejected the session); more queries cannot heal it, they only burn 20-45s pacer
      cooldowns each. After `direct_abort_blocks` blocks with zero successes the whole phase
      aborts (worst case ~1 cooldown instead of weeks*days of them).
    * clean flag — a week whose probed days ALL answered without a block signal carries the
      same evidence a browser sweep would (same API, same extract); the caller may trust its
      SOLD OUT/NA verdict and skip the browser re-verify.
    """
    health = {"oks": 0, "blocks": 0}

    def dead():
        return health["oks"] == 0 and health["blocks"] >= cfg.direct_abort_blocks

    async def one_week(wn):
        sold = False
        clean = True
        for checkin in week_days(base, wn, days):
            if dead():
                return {"week": wn, "price": "SOLD OUT" if sold else "NA", "clean": False}
            ci = checkin.strftime("%Y-%m-%d")
            if ci == cap.get("checkin") and adapter.response_is_definitive(cap.get("resp_json")):
                st, j = 200, cap["resp_json"]     # warm nav already answered this exact day
            else:
                async with pacer.slot():
                    if dead():                    # may have died while waiting out a cooldown
                        return {"week": wn, "price": "SOLD OUT" if sold else "NA", "clean": False}
                    st, j = await query_via_capture(sess, cap, checkin, timeout=cfg.query_timeout_s)
            res = adapter.extract(j or {}, room_type)
            if is_block_signal(st, res):
                health["blocks"] += 1
                pacer.record_block()
                clean = False
                continue                      # blocked -> never a price; try next day / re-verified later
            health["oks"] += 1
            pacer.record_ok()
            if res.get("found"):
                return {"week": wn, "price": res["price"], "clean": clean}
            if res.get("soldOut"):
                sold = True
        return {"week": wn, "price": "SOLD OUT" if sold else "NA", "clean": clean}

    return await asyncio.gather(*[one_week(w) for w in weeks])


# --------------------------------------------------------------------------- capture reuse
def _open_session(adapter, cap):
    sess = make_session(cap.get("impersonate"))
    load_cookies(sess, cap.get("cookies"), default_domain=f".{adapter.name}.com")
    return sess


async def _probe_capture(adapter, sess, cap, base, pacer, cfg):
    """One replay against W1 day 1 decides whether a CACHED capture still answers.

    Success re-dates cap['req'] to today's window and seeds resp_json, so the sweep reuses
    the probe's answer — a live probe costs zero extra queries. A dead probe does NOT ding
    the pacer: a stale cookie says nothing about how hot the IP is."""
    checkin = week_days(base, 1, 1)[0]
    ci = checkin.strftime("%Y-%m-%d")
    async with pacer.slot():
        st, j = await query_via_capture(sess, cap, checkin, timeout=cfg.query_timeout_s)
    if is_block_signal(st, adapter.extract(j or {}, "")):
        return False
    pacer.record_ok()
    m, u, h, d = parameterize(cap["req"], cap["checkin"], ci)
    cap["req"] = {"method": m, "url": u, "headers": h, "post_data": d}
    cap["checkin"], cap["resp_json"] = ci, j
    return True


async def _live_capture(adapter, url, base, pacer, cfg, capinfo, warm_kw):
    """Resolve a replayable (cap, sess) for a hotel: prewarmed/cached capture first (cached
    ones are probe-verified), else one fresh browser warm. sess is None => direct is dead."""
    cap = (capinfo or {}).get("cap")
    cached = bool((capinfo or {}).get("cached"))
    if cap is not None and cap.get("req") is not None:
        sess = _open_session(adapter, cap)
        if not cached:
            return cap, sess
        if await _probe_capture(adapter, sess, cap, base, pacer, cfg):
            print("   ♻️ cached capture alive — warm skipped", flush=True)
            return cap, sess
        capstore.invalidate(cfg, adapter.name, url)
        with contextlib.suppress(Exception):
            await sess.close()
        print("   ♻️→🔥 cached capture stale — warming fresh", flush=True)
    cap = await warm.warm_capture(adapter, url, base, cfg, **warm_kw)
    if cap.get("req") is None:
        return cap, None
    return cap, _open_session(adapter, cap)


# --------------------------------------------------------------------------- shared capture
async def _shared_prepass(adapter, browser, stealth, cam, hotels, base, num_weeks, awp,
                          pacer, cfg, temp_file):
    """Opt-in fast pre-pass: ONE donor warm prices every hotel whose propertyId we already
    know (from the capstore cache) by swapping propertyId into the donor's live session.

    Trust rule (see agoda-shared-capture memory): only a REAL PRICE is taken here. SOLD OUT /
    NA / blocked verdicts from the shared session are discarded — big chains false-sold-out on
    a cold shared session — so those weeks stay NA and flow through the normal per-hotel path
    (fresh warm + browser). The donor is re-warmed periodically and whenever it goes cold."""
    todo = [(str(hn), hu, rt, (str(hn), str(rt)), capstore.cached_property_id(cfg, adapter.name, hu))
            for (hn, hu, rt) in hotels]
    todo = [t for t in todo if t[4]]                 # only hotels with a known propertyId
    if not todo:
        print("   (shared-capture: no cached propertyIds yet — warming per hotel this run)",
              flush=True)
        return 0

    print(f"⚡ shared-capture pre-pass: {len(todo)}/{len(hotels)} hotels have a cached "
          f"propertyId — pricing them from one donor session", flush=True)
    donor = None
    filled = since_refresh = block_streak = warms = 0

    async def new_donor(seed_url):
        cap = await warm.warm_capture(adapter, seed_url, base, cfg, chromium=browser,
                                      stealth=stealth, camoufox_browser=cam, verbose=False)
        return cap if cap.get("req") is not None else None

    for hn, hu, rt, key, pid in todo:
        # No awp row is created up front: a checkpoint row must mean "this hotel has real
        # data", otherwise a restart would misread untouched hotels as already-attempted
        # and resume_new_first would silently degrade to plain input order.
        row = awp.get(key) or {}
        need = [i for i in range(1, num_weeks + 1) if not is_real(row.get(f"Price W{i}", "NA"))]
        if not need:
            continue
        if (donor is None or since_refresh >= cfg.shared_refresh_every
                or block_streak >= cfg.shared_max_block_streak):
            donor = await new_donor(hu)
            since_refresh = block_streak = 0
            if donor is None:
                print("   ⚠️ shared-capture: donor warm failed — handing rest to normal path",
                      flush=True)
                break
            warms += 1
        cap = dict(donor)
        cap["req"] = swap_property(donor["req"], pid)
        cap["resp_json"] = None                      # donor's W1 answer is a DIFFERENT hotel
        sess = _open_session(adapter, cap)
        try:
            direct = await _direct_weeks(adapter, sess, cap, rt, base, need,
                                         cfg.days_per_week, pacer, cfg)
        except Exception:
            direct = []
        finally:
            with contextlib.suppress(Exception):
                await sess.close()
        got = 0
        for r in direct:
            if is_real(r["price"]):                  # trust ONLY real prices
                awp.setdefault(key, {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)})
                awp[key][f"Price W{r['week']}"] = r["price"]
                got += 1
                filled += 1
        since_refresh += 1
        block_streak = block_streak + 1 if got == 0 else 0
        print(f"   ⚡ {hn[:34]}: {got}/{len(need)} priced from shared session", flush=True)
        checkpoint.save_backup_csv(awp, temp_file, num_weeks)
    print(f"   ⚡ shared pre-pass done: {filled} cells priced with {warms} warm(s) "
          f"instead of {len(todo)}", flush=True)
    return filled


# --------------------------------------------------------------------------- browser fallback
async def _browser_week(adapter, browser, url, room_type, wn, base, cfg, stealth, days,
                        breaker=None, tag=""):
    sold = False
    day_list = week_days(base, wn, days)
    for i, checkin in enumerate(day_list):
        day_tag = f"[{tag[:18]}] W{wn} {checkin.strftime('%m/%d')}" if tag else ""
        res = await warm.browser_crawl_day(adapter, browser, url, room_type, checkin, cfg,
                                           stealth, breaker, tag=day_tag)
        if res.get("found"):
            if tag:
                print(f"      ✅ [{tag[:22]}] W{wn}: {res['price']} "
                      f"({checkin.strftime('%m/%d')}, {str(res.get('room', ''))[:20]})", flush=True)
            return {"week": wn, "price": res["price"]}
        if res.get("soldOut"):
            sold = True
        if res.get("skipped"):                # breaker tripped: no nav happened, no pause needed
            continue
        if i < len(day_list) - 1:
            await asyncio.sleep(random.uniform(*cfg.intra_week_delay))
    price = "SOLD OUT" if sold else "NA"
    if tag:
        print(f"      {'🚫' if sold else '❌'} [{tag[:22]}] W{wn}: {price}", flush=True)
    return {"week": wn, "price": price}


# --------------------------------------------------------------------------- per hotel
async def crawl_hotel(adapter, browser, stealth, hotel_name, url, room_type,
                      base, num_weeks, want, pacer, cfg, direct_enabled=True,
                      camoufox_browser=None, capinfo=None):
    prices = {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
    want = want or list(range(1, num_weeks + 1))
    direct_got = 0
    clean_weeks = set()
    direct_dead = False

    # PHASE A+B — direct replay (only for sites where capture->replay is proven)
    if adapter.direct_replay and direct_enabled:
        warm_kw = dict(chromium=browser, stealth=stealth,
                       camoufox_browser=camoufox_browser, verbose=False)
        cap, sess = await _live_capture(adapter, url, base, pacer, cfg, capinfo, warm_kw)
        if sess is not None:
            try:
                direct = await _direct_weeks(adapter, sess, cap, room_type, base,
                                             want, cfg.days_per_week, pacer, cfg)
                if cfg.capture_cache:
                    cap["cookies"] = export_cookies(sess, cap.get("cookies"))
            finally:
                try:
                    await sess.close()
                except Exception:
                    pass
            for r in direct:
                if r["week"] not in want:
                    continue
                if r.get("clean"):
                    clean_weeks.add(r["week"])
                if is_real(r["price"]):
                    prices[f"Price W{r['week']}"] = r["price"]
                    direct_got += 1
                elif str(r["price"]).startswith("SOLD OUT"):
                    prices[f"Price W{r['week']}"] = r["price"]
            direct_dead = not direct_got and not clean_weeks   # every replay came back blocked
            if cfg.capture_cache:
                if direct_dead:
                    capstore.invalidate(cfg, adapter.name, url)
                else:
                    capstore.save(cfg, adapter.name, url, cap)  # alive: roll the cache forward
        else:
            direct_dead = True                                 # warm never captured the API req

    # PHASE C — browser fallback ONLY for weeks direct could not answer without a block signal.
    # A clean direct sweep saw the same API payloads a browser nav would, so its SOLD OUT/NA
    # verdict is final; re-navigating those weeks was pure duplicate work.
    need = [w for w in want if not is_real(prices[f"Price W{w}"])
            and not (cfg.trust_direct_clean and w in clean_weeks)]
    fallback_count = len(need)
    still_blocked = []
    if need:
        sem = asyncio.Semaphore(cfg.weeks_parallel)
        breaker = warm.new_breaker()   # shared across this hotel's weeks: fast-NA when hard-blocked

        async def one(wn):
            async with sem:
                return await _browser_week(adapter, browser, url, room_type, wn, base, cfg,
                                           stealth, cfg.days_per_week, breaker,
                                           tag=str(hotel_name))

        for r in await asyncio.gather(*[one(w) for w in need]):
            wn, new = r["week"], r["price"]
            old = prices[f"Price W{wn}"]
            if is_real(new):
                prices[f"Price W{wn}"] = new
            elif str(new).startswith("SOLD OUT"):
                prices[f"Price W{wn}"] = "SOLD OUT"
            else:
                still_blocked.append(wn)
                if not str(old).startswith("SOLD OUT"):
                    prices[f"Price W{wn}"] = "NA"
    return prices, direct_got, fallback_count, still_blocked, direct_dead


# --------------------------------------------------------------------------- run
def _merge_only_improve(cur, prices, num_weeks):
    for i in range(1, num_weeks + 1):
        new = prices.get(f"Price W{i}", "NA")
        if is_real(new) or (str(new).startswith("SOLD OUT") and not is_real(cur.get(f"Price W{i}", "NA"))):
            cur[f"Price W{i}"] = new
    return cur


def _resume_order(work, prev):
    """Split the round-1 work list into (fresh, redo), each keeping input order.

    fresh = hotels with NO row in the checkpoint yet (never attempted); redo = hotels that
    already have a row but still show NA/SOLD OUT cells. A restarted run crawls fresh first
    so it reaches new hotels immediately instead of re-fighting blocked/sold-out ones.
    `work` items are (idx, hotel_name, hotel_url, room_type, key, need)."""
    fresh = [w for w in work if w[4] not in prev]
    redo = [w for w in work if w[4] in prev]
    return fresh, redo


def _build_work(hotels, awp, prev, num_weeks, resume_new_first):
    """Round-1 work list in final crawl order, plus the complete hotels to skip.

    Returns (work, skipped, n_fresh, n_redo). `need` is read from awp so pre-pass fills and
    resume state both count as done. With resume_new_first and a non-empty checkpoint the
    list is re-ordered never-crawled-first (see _resume_order); n_fresh/n_redo are 0 when no
    re-ordering was applied."""
    work, skipped = [], []
    for idx, (hn, hu, rt) in enumerate(hotels, 1):
        key = (str(hn), str(rt))
        need = checkpoint.weeks_needed(awp, key, num_weeks)
        if not need:
            skipped.append((idx, hn))
        else:
            work.append((idx, hn, hu, rt, key, need))
    if resume_new_first and prev:
        fresh, redo = _resume_order(work, prev)
        return fresh + redo, skipped, len(fresh), len(redo)
    return work, skipped, 0, 0


async def run(site="agoda", input="agoda1.csv", sheet="", gid="", shard="", weeks=0, max=0,
              out="", temp="", cfg=None, **overrides):
    """Full crawl. Returns the output CSV path."""
    cfg = cfg or Config()
    for k, v in overrides.items():
        if hasattr(cfg, k) and v is not None:
            setattr(cfg, k, v)
    adapter = get_adapter(site, cfg)
    num_weeks = weeks or cfg.num_weeks
    t0 = time.time()

    hotels = hotels_io.read_hotels(input, sheet, gid)
    shard_t = hotels_io.parse_shard(shard)
    if shard_t:
        hotels = hotels_io.apply_shard(hotels, shard_t)
    if max:
        hotels = hotels[:max]

    base = base_checkin(cfg)
    today = datetime.today().strftime("%Y%m%d")
    base_name = os.path.splitext(os.path.basename(str(input)))[0] or site
    if hotels_io.is_gsheet(input):
        base_name = site
    if shard_t:
        base_name = f"{base_name}_s{shard_t[0]}of{shard_t[1]}"
    temp_file = temp or f"TEMP_{base_name}.csv"
    out_file = out or f"FINAL_{today}.csv"

    prev = checkpoint.load_prev(temp_file, num_weeks)
    awp = {k: dict(v) for k, v in prev.items()}
    if prev:
        print(f"📂 Resume: {len(prev)} rows from {temp_file}", flush=True)

    # Preflight THIS interpreter before spending hours crawling: a missing required package
    # aborts with the exact install command; a missing optional one (e.g. camoufox) degrades
    # loudly ONCE instead of silently per hotel.
    missing = envcheck.check(verbose=False)
    if missing:
        raise SystemExit("❌ missing required packages — run:\n   " + envcheck.pip_hint(missing))
    if cfg.engine == "camoufox" and not envcheck.has("camoufox"):
        print("⚠️ Camoufox not installed — using chromium warm. For stronger stealth:\n"
              "   pip install -U 'camoufox[geoip]' && python -m camoufox fetch", flush=True)
        cfg.engine = "chromium"

    pacer = AdaptivePacer(cfg)
    direct_enabled = adapter.direct_replay
    dead_streak = 0
    # Soft-cap concurrent browser contexts (hotels × weeks) to avoid thrashing the machine / IP.
    # NOTE: param name `max` shadows the builtin — use max_ helper below.
    hp = max_(1, int(getattr(cfg, "hotels_parallel", 1) or 1))
    wp = max_(1, int(cfg.weeks_parallel))
    cap_ctx = max_(1, int(getattr(cfg, "max_browser_contexts", 12) or 12))
    if hp * wp > cap_ctx:
        old_hp = hp
        hp = max_(1, cap_ctx // wp)
        cfg.hotels_parallel = hp
        print(f"⚠️ hotels_parallel {old_hp}×weeks_parallel {wp} > max_browser_contexts {cap_ctx} "
              f"— clamped hotels_parallel={hp}", flush=True)
    else:
        cfg.hotels_parallel = hp

    mode = "direct+fallback" if direct_enabled else "browser-only"
    print(f"🚀 {site.upper()} crawl | {len(hotels)} hotels × {num_weeks}w | {mode} | "
          f"engine={cfg.engine} | hotels_parallel={cfg.hotels_parallel} | "
          f"weeks_parallel={cfg.weeks_parallel} | W1={base.strftime('%Y-%m-%d')}", flush=True)

    blocked_keys = set()
    awp_lock = asyncio.Lock()
    async with contextlib.AsyncExitStack() as stack:
        browser, stealth = await stack.enter_async_context(warm.open_chromium(cfg))
        cam = None
        if direct_enabled and cfg.engine == "camoufox":
            # ONE Camoufox for the whole run (launching it per hotel cost 5-10 s each).
            cam = await stack.enter_async_context(warm.open_camoufox(cfg))
            if cam is None:
                cfg.engine = "chromium"
        # Opt-in shared-capture pre-pass (one warm prices many hotels via propertyId swap).
        # It fills trusted prices straight into awp, so the work list below shrinks.
        if cfg.shared_capture and direct_enabled:
            await _shared_prepass(adapter, browser, stealth, cam, hotels, base, num_weeks,
                                  awp, pacer, cfg, temp_file)

        # The work list is fixed up front (resume state never changes inside round 1), which
        # lets the warm pipeline see exactly one hotel ahead.
        work, skipped, n_fresh, n_redo = _build_work(hotels, awp, prev, num_weeks,
                                                     cfg.resume_new_first)
        for idx, hn in skipped:
            print(f"✔️  {idx}/{len(hotels)} {hn} — complete, skip", flush=True)
        if n_fresh and n_redo:
            print(f"⏭️  Resume order: {n_fresh} new hotels first, "
                  f"{n_redo} NA/SOLD-OUT retries after", flush=True)

        async def _prepare(hu_):
            """Capture for one hotel: disk cache first, else browser warm. Never raises —
            a None result just means crawl_hotel resolves the capture itself."""
            try:
                if not direct_enabled:
                    return None
                if cfg.capture_cache:
                    c = capstore.load(cfg, adapter.name, hu_)
                    if c is not None:
                        return {"cap": c, "cached": True}
                c = await warm.warm_capture(adapter, hu_, base, cfg, chromium=browser,
                                            stealth=stealth, camoufox_browser=cam,
                                            verbose=False)
                return {"cap": c, "cached": False}
            except Exception:
                return None

        async def _finish_hotel(idx, hn, hu, rt, key, need, prices, dgot, nfb, blk, ddead, t_hotel):
            """Merge results + checkpoint under lock (safe for hotels_parallel > 1)."""
            nonlocal direct_enabled, dead_streak
            async with awp_lock:
                if direct_enabled:
                    known_bad = key in prev and not any(
                        is_real(prev[key].get(f"Price W{i}", "NA"))
                        for i in range(1, num_weeks + 1))
                    if ddead:
                        if not known_bad:
                            dead_streak += 1
                    else:
                        dead_streak = 0
                    if dead_streak >= cfg.disable_direct_after:
                        direct_enabled = False
                        print(f"   🔻 direct replay dead for {dead_streak} hotels in a row — "
                              f"switching to browser-only for the rest of the run", flush=True)
                cur = awp.get(key) or {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
                awp[key] = _merge_only_improve(cur, prices, num_weeks)
                if blk:
                    blocked_keys.add(key)
                got = sum(1 for i in range(1, num_weeks + 1) if is_real(awp[key][f"Price W{i}"]))
                p = pacer.snapshot()
                print(f"   {'✅' if got == num_weeks else '⚠️'} {got}/{num_weeks} priced "
                      f"(direct {dgot}, fallback {nfb}) | pace limit={p['limit']} | "
                      f"{t_hotel:.1f}s", flush=True)
                checkpoint.save_backup_csv(awp, temp_file, num_weeks)

        async def _run_one_hotel(item, capinfo=None):
            idx, hn, hu, rt, key, need = item
            print(f"\n🏨 {idx}/{len(hotels)} {hn} | {rt} | need weeks {need}", flush=True)
            t1 = time.time()
            try:
                prices, dgot, nfb, blk, ddead = await crawl_hotel(
                    adapter, browser, stealth, hn, hu, rt, base, num_weeks, need, pacer, cfg,
                    direct_enabled=direct_enabled, camoufox_browser=cam, capinfo=capinfo)
            except Exception as e:
                print(f"   ❌ {e}", flush=True)
                prices = awp.get(key) or {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
                dgot, nfb, blk, ddead = 0, 0, need, False
            await _finish_hotel(idx, hn, hu, rt, key, need, prices, dgot, nfb, blk, ddead,
                                time.time() - t1)
            await asyncio.sleep(random.uniform(*cfg.between_hotels))

        if cfg.hotels_parallel <= 1:
            # v1 path: sequential + optional pipeline warm of the next hotel
            prewarm = None
            for j, item in enumerate(work):
                idx, hn, hu, rt, key, need = item
                capinfo = None
                if direct_enabled:
                    capinfo = (await prewarm) if prewarm is not None else await _prepare(hu)
                prewarm = None
                if cfg.pipeline_warm and direct_enabled and j + 1 < len(work):
                    prewarm = asyncio.create_task(_prepare(work[j + 1][2]))
                await _run_one_hotel(item, capinfo=capinfo)
                if not direct_enabled and prewarm is not None:
                    prewarm.cancel()
                    prewarm = None
        else:
            # Parallel hotels (no pipeline_warm — overlapping warms fight for the same browser).
            hotel_sem = asyncio.Semaphore(cfg.hotels_parallel)

            async def _parallel_one(item):
                async with hotel_sem:
                    capinfo = await _prepare(item[2]) if direct_enabled else None
                    await _run_one_hotel(item, capinfo=capinfo)

            await asyncio.gather(*[_parallel_one(item) for item in work])

        ki = {(str(h), str(r)): (h, u, r) for (h, u, r) in hotels}
        # Rounds 2/3 navigate more patiently than the fail-fast round 1 (ported: 50-55 s
        # page timeout vs 45 s) — these are the last shots at a cell, so patience > speed.
        rcfg = _cfg_replace(cfg, page_timeout_ms=cfg.retry_page_timeout_ms)

        # ---- round 2: browser re-crawl of every NA / SOLD OUT cell ----
        if cfg.auto_retry_na_soldout:
            retry = {k: [i for i in range(1, num_weeks + 1)
                         if not is_real(awp[k].get(f"Price W{i}", "NA"))]
                     for k in awp if k in ki}
            retry = {k: v for k, v in retry.items() if v}
            if retry:
                print(f"\n🔄 Round 2: {sum(len(v) for v in retry.values())} cells / "
                      f"{len(retry)} hotels still NA/SOLD OUT — browser retry…", flush=True)
                updated = 0
                for k, wk in retry.items():
                    hn, hu, rt = ki[k]
                    sem = asyncio.Semaphore(cfg.weeks_parallel)
                    breaker = warm.new_breaker()   # tripped here -> hotel joins the cooldown rounds

                    async def one(wn):
                        async with sem:
                            return await _browser_week(adapter, browser, hu, rt, wn, base, rcfg,
                                                       stealth, cfg.retry_days_per_week, breaker,
                                                       tag=str(hn))

                    res = await asyncio.gather(*[one(w) for w in wk])
                    if breaker.get("tripped"):
                        blocked_keys.add(k)
                    for r in res:
                        new, old = r["price"], awp[k].get(f"Price W{r['week']}", "NA")
                        if is_real(new) and new != old:
                            awp[k][f"Price W{r['week']}"] = new
                            updated += 1
                        elif str(new).startswith("SOLD OUT") and not is_real(old):
                            awp[k][f"Price W{r['week']}"] = new
                    checkpoint.save_backup_csv(awp, temp_file, num_weeks)
                    await asyncio.sleep(random.uniform(*cfg.between_hotels))
                print(f"   🔄 Round 2 done: {updated} cells recovered", flush=True)

        # ---- round 3: cooldown rounds for still-blocked hotels ----
        if cfg.retry_blocked_hotels and blocked_keys:
            for rnd in range(1, cfg.max_block_rounds + 1):
                still = {k: [i for i in range(1, num_weeks + 1)
                             if not is_real(awp[k].get(f"Price W{i}", "NA"))]
                         for k in blocked_keys if k in ki}
                still = {k: v for k, v in still.items() if v}
                if not still:
                    break
                if cfg.rotate_ip_cmd and cfg.rotate_after_blocks and rnd >= cfg.rotate_after_blocks:
                    await iprotate.rotate(cfg)
                cd = cfg.block_cooldown_base_s * rnd
                print(f"\n🧊 Block round {rnd}/{cfg.max_block_rounds}: {len(still)} hotels — "
                      f"cooldown {int(cd)}s then browser retry…", flush=True)
                await asyncio.sleep(cd)
                for k, wk in still.items():
                    hn, hu, rt = ki[k]
                    sem = asyncio.Semaphore(cfg.weeks_parallel)

                    async def one(wn):
                        async with sem:
                            return await _browser_week(adapter, browser, hu, rt, wn, base, rcfg,
                                                       stealth, cfg.retry_days_per_week,
                                                       tag=str(hn))

                    for r in await asyncio.gather(*[one(w) for w in wk]):
                        new, old = r["price"], awp[k].get(f"Price W{r['week']}", "NA")
                        if is_real(new) or (str(new).startswith("SOLD OUT") and not is_real(old)):
                            awp[k][f"Price W{r['week']}"] = new
                    checkpoint.save_backup_csv(awp, temp_file, num_weeks)
                    await asyncio.sleep(random.uniform(*cfg.block_cooldown_between))

    checkpoint.save_backup_csv(awp, out_file, num_weeks)
    tc = len(awp) * num_weeks
    na = sum(1 for pp in awp.values() for i in range(1, num_weeks + 1) if pp.get(f"Price W{i}", "NA") == "NA")
    so = sum(1 for pp in awp.values() for i in range(1, num_weeks + 1)
             if str(pp.get(f"Price W{i}", "")).startswith("SOLD OUT"))
    tt = time.time() - t0
    print(f"\n{'='*60}", flush=True)
    print(f"✅ {out_file} | priced {tc-na-so}/{tc} ({(tc-na-so)/max_(tc,1):.1%}) | 🚫 {so} SO | ❌ {na} NA", flush=True)
    print(f"⏱️ {int(tt//60)}m {int(tt%60)}s for {len(awp)} hotels × {num_weeks}w", flush=True)
    print(f"{'='*60}", flush=True)
    return out_file


def max_(a, b):
    return a if a > b else b
