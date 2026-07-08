# -*- coding: utf-8 -*-
"""One-off gate commands: capture (Gate 0), replay (Gate 1), diag.

These MUST run on the machine/IP that will do the crawling — a capture's cookies are bound to
the TLS fingerprint + IP that created them, so a capture from another host is useless.
"""
import contextlib
import json
import os
from datetime import timedelta

from .config import Config
from .dates import base_checkin
from . import warm
from .replay import query_via_capture
from .session import make_session, load_cookies
from .sites import get_adapter

CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_capture")


def _capture_path(site):
    return os.path.join(CAPTURE_DIR, f"capture_{site}.json")


async def gate_capture(site, url, room="", cfg=None):
    cfg = cfg or Config()
    adapter = get_adapter(site, cfg)
    bc = base_checkin(cfg)
    print(f"🔥 GATE 0 — warm + capture {site} (checkin={bc.strftime('%Y-%m-%d')}, engine={cfg.engine})", flush=True)
    cap = await warm.warm_capture(adapter, url, bc, cfg, verbose=True)
    if cap.get("req") is not None:
        os.makedirs(CAPTURE_DIR, exist_ok=True)
        with open(_capture_path(site), "w", encoding="utf-8") as f:
            json.dump(cap, f, ensure_ascii=False, indent=2)
        r = cap["req"]
        print(f"  ✅ captured {r['method']} {r['url'][:80]}… | POST body: "
              f"{'yes' if r.get('post_data') else 'no (GET)'} | cookies: {len(cap.get('cookies', []))}"
              f" | impersonate={cap.get('impersonate')} | rooms={adapter.response_has_rooms(cap.get('resp_json'))}",
              flush=True)
        print(f"  💾 saved {_capture_path(site)}", flush=True)
        if room:
            print(f"  🔎 sanity '{room}': {adapter.extract(cap.get('resp_json') or {}, room)}", flush=True)
        if cap.get("xhr_urls"):
            cal = [u for u in cap["xhr_urls"] if any(w in u.lower() for w in ("calendar", "pricecalendar", "los", "daily"))]
            if cal:
                print(f"  🗓️ candidate multi-date endpoints (M2 spike): {cal[:5]}", flush=True)
    else:
        print("  ❌ warm failed. Retry / switch IP (4G) / set headless=False / try engine=chromium.", flush=True)
    return cap


async def gate_replay(site, room="", cfg=None):
    cfg = cfg or Config()
    adapter = get_adapter(site, cfg)
    path = _capture_path(site)
    if not os.path.exists(path):
        print(f"❌ no {path} — run 'capture' first.", flush=True)
        return
    with open(path, encoding="utf-8") as f:
        cap = json.load(f)
    from datetime import datetime
    sess = make_session(cap.get("impersonate"))
    load_cookies(sess, cap.get("cookies"), default_domain=f".{adapter.name}.com")
    try:
        bc = datetime.strptime(cap["checkin"], "%Y-%m-%d")
        print(f"🧪 GATE 1a — replay VERBATIM (impersonate={cap.get('impersonate')}):", flush=True)
        st, j = await query_via_capture(sess, cap, bc, timeout=cfg.query_timeout_s)
        print(f"     status={st} | rooms={adapter.response_has_rooms(j)}", flush=True)
        if room:
            print(f"     '{room}': {adapter.extract(j or {}, room)}", flush=True)
        bc2 = bc + timedelta(days=14)
        print(f"🧪 GATE 1b — replay +14d ({bc2.strftime('%Y-%m-%d')}):", flush=True)
        st2, j2 = await query_via_capture(sess, cap, bc2, timeout=cfg.query_timeout_s)
        print(f"     status={st2} | rooms={adapter.response_has_rooms(j2)}", flush=True)
        if room:
            print(f"     '{room}': {adapter.extract(j2 or {}, room)}", flush=True)
    finally:
        with contextlib.suppress(Exception):
            await sess.close()


def _summarize(adapter, tag, j):
    j = j or {}
    has = adapter.response_has_rooms(j)
    print(f"  [{tag}] rooms={has} | keys={list(j.keys())[:7]}", flush=True)


async def gate_diag(site, url, room, cfg=None):
    cfg = cfg or Config()
    adapter = get_adapter(site, cfg)
    bc = base_checkin(cfg)
    print(f"🔬 DIAG {site} | {url[:70]}…\n   room='{room}' | checkin={bc.strftime('%Y-%m-%d')}", flush=True)
    cap = await warm.warm_capture(adapter, url, bc, cfg, verbose=True)
    if cap.get("req") is None:
        print("⛔ warm failed.", flush=True)
        return
    print("\n── (1) response the BROWSER saw during warm ──", flush=True)
    _summarize(adapter, "warm", cap.get("resp_json"))
    print(f"  extract '{room}': {adapter.extract(cap.get('resp_json') or {}, room)}", flush=True)
    sess = make_session(cap.get("impersonate"))
    load_cookies(sess, cap.get("cookies"), default_domain=f".{adapter.name}.com")
    try:
        print("\n── (2) response from curl_cffi REPLAY ──", flush=True)
        for label, dd in [("replay +0d", 0), ("replay +14d", 14)]:
            st, j = await query_via_capture(sess, cap, bc + timedelta(days=dd), timeout=cfg.query_timeout_s)
            print(f"\n  ▶ {label}: HTTP {st}", flush=True)
            _summarize(adapter, label, j)
            print(f"     extract '{room}': {adapter.extract(j or {}, room)}", flush=True)
    finally:
        with contextlib.suppress(Exception):
            await sess.close()
