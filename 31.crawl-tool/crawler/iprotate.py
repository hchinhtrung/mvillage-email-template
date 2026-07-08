# -*- coding: utf-8 -*-
"""Opt-in free IP-rotation hook.

Runs a user-supplied shell command (e.g. toggle a phone hotspot / cycle airplane mode / a
tethering script) then verifies the public IP actually changed before continuing. Off by
default; enabled via Config.rotate_ip_cmd. All free — no proxies.
"""
import asyncio
import contextlib


async def public_ip(timeout=8.0):
    """Best-effort public IP via a free endpoint. Returns str or None."""
    try:
        from curl_cffi import AsyncSession
    except Exception:
        try:
            from curl_cffi.requests import AsyncSession
        except Exception:
            return None
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"):
        try:
            async with AsyncSession() as s:
                r = await s.get(url, timeout=timeout)
                ip = (r.text or "").strip()
                if ip and len(ip) <= 45:
                    return ip
        except Exception:
            continue
    return None


async def rotate(cfg, verbose=True, verify_timeout=90.0):
    """Run cfg.rotate_ip_cmd and wait until the public IP differs from before (or timeout).

    Returns (old_ip, new_ip, changed: bool). No-op returning (None, None, False) if unset.
    """
    if not cfg.rotate_ip_cmd:
        return None, None, False
    before = await public_ip()
    if verbose:
        print(f"🔀 IP rotate: running {cfg.rotate_ip_cmd!r} (current IP {before})", flush=True)
    try:
        proc = await asyncio.create_subprocess_shell(
            cfg.rotate_ip_cmd,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), timeout=verify_timeout)
    except Exception as e:
        if verbose:
            print(f"   ⚠️ rotate command failed: {e}", flush=True)
        return before, before, False
    waited = 0.0
    while waited < verify_timeout:
        await asyncio.sleep(3.0)
        waited += 3.0
        now = await public_ip()
        if now and now != before:
            if verbose:
                print(f"   ✅ IP changed {before} → {now}", flush=True)
            return before, now, True
    if verbose:
        print(f"   ⚠️ IP did not change within {int(verify_timeout)}s (still {before})", flush=True)
    return before, before, False
