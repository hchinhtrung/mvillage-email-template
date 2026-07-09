# -*- coding: utf-8 -*-
"""Tunable configuration. Defaults ported from the proven notebooks/prototype."""
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class Config:
    # --- schedule ---
    checkin_offset: int = 5          # W1 = today + 5 days
    num_weeks: int = 6
    days_per_week: int = 7           # probe up to N consecutive days/week, stop at first price
    currency: str = "VND"
    adults: int = 2
    rooms: int = 1
    price_type: str = "final"        # final (all-in) | original (struck-through) | cashback

    # --- browser warm ---
    engine: str = "camoufox"         # "camoufox" (default, Firefox) | "chromium" (fallback)
    headless: bool = True
    page_timeout_ms: int = 45000
    api_wait_timeout_s: float = 25.0
    cookies_file: str = "cookies.json"   # optional; loaded into browser contexts when present

    # --- direct replay (curl_cffi) ---
    impersonate: str = ""            # "" = auto-pick from captured UA / engine
    query_timeout_s: float = 30.0

    # --- capture cache + warm pipeline (kills most of the per-hotel warm cost) ---
    capture_cache: bool = True       # persist live captures; later runs probe & reuse them
    capture_dir: str = "captures"    # relative to the run's working directory
    capture_max_age_h: float = 48.0  # older cache entries are ignored outright
    pipeline_warm: bool = True       # warm hotel N+1 while hotel N is still replaying

    # --- adaptive pacing (AIMD) for direct replay ---
    pace_start: int = 3              # starting concurrency
    pace_min: int = 1
    pace_max: int = 8
    pace_ramp_after: int = 12        # clean successes before +1 concurrency
    pace_jitter: Tuple[float, float] = (0.6, 1.6)
    pace_block_cooldown: Tuple[float, float] = (20.0, 45.0)

    # --- fail-fast (bounds worst-case time per hotel; see orchestrate.py) ---
    direct_abort_blocks: int = 2     # direct blocks with 0 successes -> capture is dead, abort phase
    disable_direct_after: int = 3    # consecutive dead-direct hotels -> browser-only for rest of run
    block_circuit_limit: int = 2     # consecutive fully-blocked browser days -> skip hotel (NA fast)
    trust_direct_clean: bool = True  # an unblocked direct week sweep is final (no browser re-verify)

    # --- general cadence (ported) ---
    between_hotels: Tuple[float, float] = (2.0, 5.0)
    nav_jitter: Tuple[float, float] = (0.3, 1.2)
    intra_week_delay: Tuple[float, float] = (0.5, 1.5)
    retry_backoff: Tuple[float, float] = (1.0, 2.5)

    # --- browser fallback ---
    weeks_parallel: int = 2          # weeks crawled concurrently in browser fallback
    nav_attempts: int = 2            # fresh-context nav retries when blocked

    # --- round 2: auto re-crawl NA / SOLD OUT cells after round 1 ---
    auto_retry_na_soldout: bool = True
    retry_days_per_week: int = 5     # days probed per week during retry rounds
    retry_page_timeout_ms: int = 55000   # rounds 2/3 navigate more patiently than round 1

    # --- round 3: cooldown retry of still-blocked hotels ---
    retry_blocked_hotels: bool = True
    max_block_rounds: int = 2
    block_cooldown_base_s: float = 60.0
    block_cooldown_between: Tuple[float, float] = (8.0, 15.0)

    # --- fingerprint pools (chromium fallback engine only) ---
    warm_backoff: Tuple[float, float] = (1.5, 3.5)
    warm_attempts: int = 2           # a failed warm is rescued by the browser fallback anyway

    # --- opt-in IP rotation ---
    rotate_ip_cmd: str = ""          # shell command run to switch IP (e.g. toggle hotspot)
    rotate_after_blocks: int = 0     # 0 = never auto-rotate; N = rotate after N block rounds

    block_resource_types: frozenset = field(
        default_factory=lambda: frozenset({"image", "media", "font"}))
