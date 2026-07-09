# -*- coding: utf-8 -*-
"""Persistent warm-capture cache: one file per hotel URL, reused across runs.

The warm nav is the expensive part of a hotel (~10-15 s of anti-detect browser); the
Akamai cookies it produces usually outlive the run by hours-days on the same IP. Persisting
the capture lets the NEXT run skip the warm entirely: it loads the file, verifies it with a
single probe replay (orchestrate._probe_capture), and only falls back to a fresh warm when
the probe says the session is dead. Layout: <capture_dir>/<site>/<sha1(url)[:16]>.json.

A capture is only ever saved AFTER replay proved it alive, with the session's freshest
cookies exported back into it — so the cache rolls forward run after run instead of aging out.
"""
import contextlib
import hashlib
import json
import os
import time

_STRIP = ("resp_json", "xhr_urls")   # bulky and stale-by-design; never persisted


def _path(cfg, site, hotel_url):
    h = hashlib.sha1(str(hotel_url).encode("utf-8", "ignore")).hexdigest()[:16]
    d = getattr(cfg, "capture_dir", "captures") or "captures"
    return os.path.join(d, site, f"{h}.json")


def save(cfg, site, hotel_url, cap, now=None):
    """Persist a live capture atomically. Never raises."""
    if cap is None or cap.get("req") is None:
        return
    path = _path(cfg, site, hotel_url)
    try:
        from .replay import property_id
        os.makedirs(os.path.dirname(path), exist_ok=True)
        slim = {k: v for k, v in cap.items() if k not in _STRIP}
        slim["_saved_at"] = now if now is not None else time.time()
        slim["_url"] = str(hotel_url)
        slim["property_id"] = cap.get("property_id") or property_id(cap.get("req"))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(slim, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(Exception):
            os.remove(path + ".tmp")


def load(cfg, site, hotel_url, now=None):
    """Return a persisted capture, or None when absent, expired, or unreadable.
    The caller MUST probe-verify it before trusting (cookies may have died server-side)."""
    path = _path(cfg, site, hotel_url)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cap = json.load(f)
        now = now if now is not None else time.time()
        age_h = (now - float(cap.get("_saved_at", 0))) / 3600.0
        if age_h > float(getattr(cfg, "capture_max_age_h", 48.0)) or age_h < 0:
            return None
        if not isinstance(cap.get("req"), dict) or not cap["req"].get("url"):
            return None
        cap["resp_json"] = None          # replay evidence is per-day; never reuse stale JSON
        return cap
    except Exception:
        return None


def cached_property_id(cfg, site, hotel_url):
    """The hotel's Agoda propertyId if any past capture recorded it. Ignores the freshness
    TTL on purpose — a propertyId is permanent, so a stale capture's pid is still valid and
    lets shared-capture mode price the hotel without ever warming it again."""
    path = _path(cfg, site, hotel_url)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cap = json.load(f)
        pid = cap.get("property_id")
        if pid:
            return str(pid)
        from .replay import property_id
        return property_id(cap.get("req"))
    except Exception:
        return None


def invalidate(cfg, site, hotel_url):
    """Drop a capture the probe (or a dead sweep) proved stale. Never raises."""
    with contextlib.suppress(Exception):
        os.remove(_path(cfg, site, hotel_url))
