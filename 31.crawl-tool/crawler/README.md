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
3. **Browser fallback** (chromium + stealth) only for weeks direct replay couldn't answer
   **without a block signal**. A soft-block is **retried, never recorded as a price**; an
   unblocked direct sweep (priced / genuine sold-out / room-mismatch) is final and is NOT
   re-navigated.

Two run-level accelerators cut the remaining warm cost (both on by default):

* **Capture cache** (`capture_cache`, `captures/<site>/`) — every capture that replay proved
  alive is persisted with its freshest cookies. A later run loads it and verifies with ONE
  probe replay (the probe's answer is reused for W1, so a live probe is free); only a dead
  probe pays for a fresh warm. On a daily cadence most hotels skip the browser warm entirely.
* **Warm pipeline** (`pipeline_warm`) — hotel N+1's warm (or cache load) runs in the
  background while hotel N is still replaying, hiding warm latency behind work the run does
  anyway.

After round 1 (steps 1–3 for every hotel) two automatic retry rounds run, same as the old
notebooks: **round 2** re-crawls every cell still `NA`/`SOLD OUT` via the browser
(`auto_retry_na_soldout`, probing `retry_days_per_week` days), and **round 3** retries hotels
whose circuit breaker tripped, after a long cooldown and without the breaker
(`retry_blocked_hotels`). Both rounds only ever *improve* a cell: a real price wins over
anything; `SOLD OUT` wins over `NA` only.

### Fail-fast guarantees (bounds worst-case time per hotel)

The happy path was always fast; these stop the *bad* paths from costing 20-40 min/hotel:

* **Dead-capture abort** — if the first `direct_abort_blocks` (2) replays of a hotel are all
  soft-blocked with zero successes, the capture is dead (Akamai rejected the session); the
  direct phase aborts instead of grinding weeks×days queries through 20-45 s pacer cooldowns.
* **Run-level direct disable** — `disable_direct_after` (3) consecutive dead-direct hotels ⇒
  the IP/TLS pairing is burned; the run stops paying warm+replay per hotel and switches to
  browser-only (exactly the proven old pipeline).
* **Per-hotel browser circuit breaker** (ported from the old notebook's `BLOCK_CIRCUIT_LIMIT`) —
  `block_circuit_limit` (2) consecutive fully-blocked browser days ⇒ the rest of the hotel
  answers NA instantly; the cooldown rounds retry it later without the breaker.
* **Definitive early-break** — browser wait loops stop as soon as a response carries the final
  verdict (rooms present *or* a genuine full-property sold-out) instead of always burning the
  full `api_wait_timeout_s` (25 s) on sold-out days.

## The one rule that makes it work: Firefox↔Firefox TLS pairing

Agoda sits behind **Akamai Bot Manager**, which binds the `_abck` cookie to the **TLS
fingerprint + IP** that created it. Camoufox is **Firefox**, so replay impersonates a **Firefox**
target (`firefox147`/`144`/…), and the captured Firefox User-Agent is replayed verbatim. If
Firefox replay is ever rejected, fall back to `--engine chromium` (Chrome warm ↔ Chrome
impersonate). Because the cookie is IP-bound, **warm and replay run in the same process on the
same machine** — a capture from another machine is useless.

## Install (once)

```bash
pip install -r crawler/requirements.txt
python -m playwright install chromium
python -m camoufox fetch                   # ~300 MB anti-detect Firefox
python -m crawler doctor                   # verify THIS interpreter has everything
```

> **Packages are per-interpreter, not per-folder.** Run `python -m crawler doctor` with the
> exact python you crawl with (e.g. `.venv/bin/python -m crawler doctor`): it checks every
> package, both browser binaries, and warns if you're not on the project `.venv`.
> `crawl` runs the same preflight automatically and aborts early if a required package is
> missing (a missing optional package like camoufox degrades loudly, once).

> playwright note: 1.60 crashed Camoufox's Firefox (daijro/camoufox#617); playwright 1.61 +
> camoufox 0.4.11 passed a live smoke test (2026-07-09). If Camoufox ever crashes at launch,
> the run degrades to the chromium warm by itself — or force it with `--engine chromium`.

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
Fail-fast knobs: `direct_abort_blocks`, `disable_direct_after`, `block_circuit_limit`,
`trust_direct_clean` (set False to force the browser to re-verify every non-priced week).

## Self-test (no network)

```bash
python -m crawler.tests.selftest    # parsers, date-shift, pacing, fail-fast, checkpoint, sharding, CLI
```
