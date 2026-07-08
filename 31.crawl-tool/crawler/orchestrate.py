# -*- coding: utf-8 -*-
"""Per-hotel hybrid crawl + the full run loop (resume, adaptive pacing, cooldown rounds)."""
import asyncio
import os
import random
import time
from datetime import datetime, timedelta

from .common import is_real
from .config import Config
from .dates import base_checkin, week_days
from . import checkpoint, hotels_io, iprotate, warm
from .pace import AdaptivePacer, is_block_signal
from .replay import query_via_capture
from .session import make_session, load_cookies
from .sites import get_adapter


# --------------------------------------------------------------------------- direct replay
async def _direct_weeks(adapter, sess, cap, room_type, base, weeks, days, pacer, cfg):
    async def one_week(wn):
        sold = False
        for checkin in week_days(base, wn, days):
            async with pacer.slot():
                st, j = await query_via_capture(sess, cap, checkin, timeout=cfg.query_timeout_s)
            res = adapter.extract(j or {}, room_type)
            if is_block_signal(st, res):
                pacer.record_block()
                continue                      # blocked -> never a price; try next day / re-verified later
            pacer.record_ok()
            if res.get("found"):
                return {"week": wn, "price": res["price"]}
            if res.get("soldOut"):
                sold = True
        return {"week": wn, "price": "SOLD OUT" if sold else "NA"}

    return await asyncio.gather(*[one_week(w) for w in weeks])


# --------------------------------------------------------------------------- browser fallback
async def _browser_week(adapter, browser, url, room_type, wn, base, cfg, stealth, days):
    sold = False
    day_list = week_days(base, wn, days)
    for i, checkin in enumerate(day_list):
        res = await warm.browser_crawl_day(adapter, browser, url, room_type, checkin, cfg, stealth)
        if res.get("found"):
            return {"week": wn, "price": res["price"]}
        if res.get("soldOut"):
            sold = True
        if i < len(day_list) - 1:
            await asyncio.sleep(random.uniform(*cfg.intra_week_delay))
    return {"week": wn, "price": "SOLD OUT" if sold else "NA"}


# --------------------------------------------------------------------------- per hotel
async def crawl_hotel(adapter, browser, stealth, hotel_name, url, room_type,
                      base, num_weeks, want, pacer, cfg):
    prices = {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
    want = want or list(range(1, num_weeks + 1))
    direct_got = 0

    # PHASE A+B — direct replay (only for sites where capture->replay is proven)
    if adapter.direct_replay:
        cap = await warm.warm_capture(adapter, url, base, cfg,
                                      chromium=browser, stealth=stealth, verbose=False)
        if cap.get("req") is not None:
            sess = make_session(cap.get("impersonate"))
            load_cookies(sess, cap.get("cookies"), default_domain=f".{adapter.name}.com")
            try:
                direct = await _direct_weeks(adapter, sess, cap, room_type, base,
                                             want, cfg.days_per_week, pacer, cfg)
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
                    prices[f"Price W{r['week']}"] = r["price"]   # tentative; browser verifies

    # PHASE C — browser fallback for weeks still lacking a REAL price (browser = source of truth)
    need = [w for w in want if not is_real(prices[f"Price W{w}"])]
    fallback_count = len(need)
    still_blocked = []
    if need:
        sem = asyncio.Semaphore(cfg.weeks_parallel)

        async def one(wn):
            async with sem:
                return await _browser_week(adapter, browser, url, room_type, wn, base, cfg,
                                           stealth, cfg.days_per_week)

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
    return prices, direct_got, fallback_count, still_blocked


# --------------------------------------------------------------------------- run
def _merge_only_improve(cur, prices, num_weeks):
    for i in range(1, num_weeks + 1):
        new = prices.get(f"Price W{i}", "NA")
        if is_real(new) or (str(new).startswith("SOLD OUT") and not is_real(cur.get(f"Price W{i}", "NA"))):
            cur[f"Price W{i}"] = new
    return cur


async def run(site="agoda", input="agoda1.csv", sheet="", shard="", weeks=0, max=0,
              out="", temp="", cfg=None, **overrides):
    """Full crawl. Returns the output CSV path."""
    cfg = cfg or Config()
    for k, v in overrides.items():
        if hasattr(cfg, k) and v is not None:
            setattr(cfg, k, v)
    adapter = get_adapter(site, cfg)
    num_weeks = weeks or cfg.num_weeks
    t0 = time.time()

    hotels = hotels_io.read_hotels(input, sheet)
    shard_t = hotels_io.parse_shard(shard)
    if shard_t:
        hotels = hotels_io.apply_shard(hotels, shard_t)
    if max:
        hotels = hotels[:max]

    base = base_checkin(cfg)
    today = datetime.today().strftime("%Y%m%d")
    base_name = os.path.splitext(os.path.basename(str(input)))[0] or site
    if str(input).startswith("gsheet:") or "docs.google.com" in str(input):
        base_name = site
    if shard_t:
        base_name = f"{base_name}_s{shard_t[0]}of{shard_t[1]}"
    temp_file = temp or f"TEMP_{base_name}.csv"
    out_file = out or f"FINAL_{today}.csv"

    prev = checkpoint.load_prev(temp_file, num_weeks)
    awp = {k: dict(v) for k, v in prev.items()}
    if prev:
        print(f"📂 Resume: {len(prev)} rows from {temp_file}", flush=True)

    pacer = AdaptivePacer(cfg)
    mode = "direct+fallback" if adapter.direct_replay else "browser-only"
    print(f"🚀 {site.upper()} crawl | {len(hotels)} hotels × {num_weeks}w | {mode} | "
          f"engine={cfg.engine} | W1={base.strftime('%Y-%m-%d')}", flush=True)

    blocked_keys = set()
    async with warm.open_chromium(cfg) as (browser, stealth):
        for idx, (hn, hu, rt) in enumerate(hotels, 1):
            key = (str(hn), str(rt))
            need = checkpoint.weeks_needed(prev, key, num_weeks)
            if not need:
                print(f"✔️  {idx}/{len(hotels)} {hn} — complete, skip", flush=True)
                continue
            print(f"\n🏨 {idx}/{len(hotels)} {hn} | {rt} | need weeks {need}", flush=True)
            try:
                prices, dgot, nfb, blk = await crawl_hotel(
                    adapter, browser, stealth, hn, hu, rt, base, num_weeks, need, pacer, cfg)
            except Exception as e:
                print(f"   ❌ {e}", flush=True)
                prices = awp.get(key) or {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
                dgot, nfb, blk = 0, 0, need
            cur = awp.get(key) or {f"Price W{i}": "NA" for i in range(1, num_weeks + 1)}
            awp[key] = _merge_only_improve(cur, prices, num_weeks)
            if blk:
                blocked_keys.add(key)
            got = sum(1 for i in range(1, num_weeks + 1) if is_real(awp[key][f"Price W{i}"]))
            p = pacer.snapshot()
            print(f"   {'✅' if got == num_weeks else '⚠️'} {got}/{num_weeks} priced "
                  f"(direct {dgot}, fallback {nfb}) | pace limit={p['limit']}", flush=True)
            checkpoint.save_backup_csv(awp, temp_file, num_weeks)
            await asyncio.sleep(random.uniform(*cfg.between_hotels))

        # ---- cooldown rounds for still-blocked hotels ----
        if cfg.retry_blocked_hotels and blocked_keys:
            ki = {(str(h), str(r)): (h, u, r) for (h, u, r) in hotels}
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
                            return await _browser_week(adapter, browser, hu, rt, wn, base, cfg,
                                                       stealth, cfg.days_per_week)

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
