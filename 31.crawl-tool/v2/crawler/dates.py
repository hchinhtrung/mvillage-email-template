# -*- coding: utf-8 -*-
"""Check-in date generation: 6 weeks out, up to days_per_week probes per week."""
from datetime import datetime, timedelta


def base_checkin(cfg, today=None):
    """W1 check-in = today (midnight) + checkin_offset days."""
    d = today or datetime.today()
    return d.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=cfg.checkin_offset)


def week_start(base, week_num):
    """Monday-agnostic: start of week N is base + (N-1)*7 days."""
    return base + timedelta(days=(week_num - 1) * 7)


def week_days(base, week_num, days):
    """The candidate check-in dates to probe for a given week (first-hit-wins)."""
    ws = week_start(base, week_num)
    return [ws + timedelta(days=d) for d in range(days)]
