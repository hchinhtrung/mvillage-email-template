# crawler — free direct-API price crawler (Agoda + Trip.com)

Fast, free (no paid proxies / no paid APIs) competitor-price crawler. Optimized for **hundreds
of hotels × 6 weeks** on a single home IP.

## Why this is faster than the old notebooks

The old notebooks launch a **headless browser per price query** (~30–60 s each) and get
soft-blocked on big chains (→ false `NA`/`SOLD OUT`). This tool pays the browser cost **once
per hotel**:

1. **Warm** one anti-detect browser page per hotel (Camoufox = stealth Firefox) and capture the
   *real* room-API request (method/url/headers/body) + cookies + `apiKey`.
2. **Replay** every week × day directly with **`curl_cffi`** (TLS/JA3/HTTP2 impersonation) —
   ~1 s per query instead of 30–60 s.
3. **Browser fallback** (chromium + stealth) for any cell direct replay couldn't price. A
   soft-block is **retried, never recorded as a price**.

## The one rule that makes it work: Firefox↔Firefox TLS pairing

Agoda sits behind **Akamai Bot Manager**, which binds the `_abck` cookie to the **TLS
fingerprint + IP** that created it. Camoufox is **Firefox**, so replay impersonates a **Firefox**
target (`firefox147`/`144`/…), and the captured Firefox User-Agent is replayed verbatim. If
Firefox replay is ever rejected, fall back to `--engine chromium` (Chrome warm ↔ Chrome
impersonate). Because the cookie is IP-bound, **warm and replay run in the same process on the
same machine** — a capture from another machine is useless.

## Install (once)

```bash
pip install -r crawler/requirements.txt   # pins playwright==1.59.0 (1.60+ crashes Camoufox)
python -m playwright install chromium
python -m camoufox fetch                   # ~300 MB anti-detect Firefox
```

> If you later `pip install --upgrade playwright` past 1.59, Camoufox warm will crash
> (daijro/camoufox#617). Either keep 1.59 pinned, or run Agoda with `--engine chromium`
> (no Camoufox needed — validated live, slightly weaker stealth).

## Run — on YOUR machine (captures are IP-bound)

Gates are ordered; don't scale before each passes. Run from a shard folder (e.g. `agoda/agoda1/`)
or anywhere with your hotel CSV.

```bash
# Gate 0 — can we warm + capture a real request?  (make-or-break)
python -m crawler capture --site agoda --url "<an Agoda hotel URL>" --room "Deluxe Room"

# Gate 1 — does replay return rooms verbatim AND at +14 days?
python -m crawler replay  --site agoda --room "Deluxe Room"

# diag — side-by-side warm-response vs curl_cffi replay (use if Gate 1 disagrees)
python -m crawler diag    --site agoda --url "<url>" --room "Deluxe Room"

# Gate 2 — scale test: 5 hotels × 2 weeks, compare to the old notebook
python -m crawler crawl   --site agoda --input agoda1.csv --max 5 --weeks 2

# Full shard
python -m crawler crawl   --site agoda --input agoda1.csv
```

If Gate 0/1 fail with Firefox, retry with `--engine chromium`, or `--no-headless`, or switch to
a mobile-hotspot IP.

## Scale: Google Sheet master + auto-shard

```bash
# One central sheet, split into 5 shards; run each (optionally on a different IP / at a different time)
python -m crawler crawl --site agoda --input "gsheet:<SPREADSHEET_ID>" --sheet "Hotel Link" --shard 1/5
python -m crawler crawl --site agoda --input "gsheet:<SPREADSHEET_ID>" --sheet "Hotel Link" --shard 2/5
# … shards 3/5 4/5 5/5
```

`--input` accepts a local CSV/XLSX path, `gsheet:<id>`, or a full Google Sheets URL. The sheet's
first three columns must be **hotel name, hotel URL, room type** (extra columns ignored). Each
shard writes its own `TEMP_<name>_sNofM.csv` checkpoint, so shards never collide.

## Opt-in free IP rotation

For the hardest hotels on one IP, supply a shell command that switches your network (e.g. cycle a
phone hotspot / toggle airplane mode / a tethering script). It runs between cooldown rounds and is
**verified** (public IP must actually change) before continuing:

```bash
python -m crawler crawl --site agoda --input agoda1.csv \
    --rotate-ip-cmd "/path/to/toggle_hotspot.sh" --rotate-after-blocks 1
```

## Output (unchanged from the current pipeline)

- Checkpoint: `TEMP_<input>.csv` (written after every hotel; safe to kill & resume — only weeks
  without a real price are re-crawled).
- Final: `FINAL_<YYYYMMDD>.csv`.
- Columns: `hotel_name, room_type, price_w1 … price_w6`. Agoda cells are plain numbers
  (`4,671,429`); Trip cells are `VND 1,070,809`. Missing = `NA`; genuinely unavailable = `SOLD OUT`.
- **only-improve**: a real price is never overwritten by `NA`/`SOLD OUT`.

## Trip.com status — browser-only (confirmed 2026-07-08)

Live gate result: Trip's `getHotelRoomListOversea` POST is captured fine, but **replay fails
even verbatim same-day** (returns empty rooms) → the request is signed / anti-replay. So Trip
runs **browser-per-query** (`TripAdapter.direct_replay = False`), same as the old notebook, but
with the new adaptive pacing, resume, Google-Sheet input and sharding. Agoda is unaffected and
uses fast direct replay. (Re-test anytime with `capture`+`replay --site trip`; if replay ever
returns rooms at +14d, flip `direct_replay = True`.)

## Notebook usage

```python
import sys; sys.path.insert(0, "/absolute/path/to/31.crawl-tool")
import crawler
crawler.crawl(site="agoda", input="agoda1.csv", weeks=6)   # applies nest_asyncio automatically
```

## Tuning (`crawler/config.py`)

Adaptive pacing (AIMD) replaces fixed sleeps: concurrency starts at `pace_start=3`, ramps by +1
after `pace_ramp_after` clean replays, and **halves + cools down** on any block. Other knobs:
`num_weeks`, `days_per_week`, `weeks_parallel`, `engine`, `impersonate`, `headless`.

## Self-test (no network)

```bash
python -m crawler.tests.selftest    # 37 checks: parsers, date-shift, pacing, checkpoint, sharding, CLI
```
