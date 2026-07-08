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

    # --- browser warm ---
    engine: str = "camoufox"         # "camoufox" (default, Firefox) | "chromium" (fallback)
    headless: bool = True
    page_timeout_ms: int = 45000
    api_wait_timeout_s: float = 25.0

    # --- direct replay (curl_cffi) ---
    impersonate: str = ""            # "" = auto-pick from captured UA / engine
    query_timeout_s: float = 30.0

    # --- adaptive pacing (AIMD) for direct replay ---
    pace_start: int = 3              # starting concurrency
    pace_min: int = 1
    pace_max: int = 8
    pace_ramp_after: int = 12        # clean successes before +1 concurrency
    pace_jitter: Tuple[float, float] = (0.6, 1.6)
    pace_block_cooldown: Tuple[float, float] = (20.0, 45.0)

    # --- general cadence (ported) ---
    between_hotels: Tuple[float, float] = (2.0, 5.0)
    nav_jitter: Tuple[float, float] = (0.3, 1.2)
    intra_week_delay: Tuple[float, float] = (0.5, 1.5)
    retry_backoff: Tuple[float, float] = (1.0, 2.5)

    # --- browser fallback ---
    weeks_parallel: int = 2          # weeks crawled concurrently in browser fallback
    nav_attempts: int = 2            # fresh-context nav retries when blocked

    # --- round 3: cooldown retry of still-blocked hotels ---
    retry_blocked_hotels: bool = True
    max_block_rounds: int = 2
    block_cooldown_base_s: float = 60.0
    block_cooldown_between: Tuple[float, float] = (8.0, 15.0)

    # --- fingerprint pools (chromium fallback engine only) ---
    warm_backoff: Tuple[float, float] = (1.5, 3.5)
    warm_attempts: int = 4

    # --- opt-in IP rotation ---
    rotate_ip_cmd: str = ""          # shell command run to switch IP (e.g. toggle hotspot)
    rotate_after_blocks: int = 0     # 0 = never auto-rotate; N = rotate after N block rounds

    block_resource_types: frozenset = field(
        default_factory=lambda: frozenset({"image", "media", "font"}))
