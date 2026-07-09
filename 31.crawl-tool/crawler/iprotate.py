# -*- coding: utf-8 -*-
"""Opt-in free IP-rotation hook.

Runs a user-supplied shell command (e.g. cycle Wi-Fi, toggle a phone hotspot / airplane mode,
or reassign an IPv6 address) then verifies the public IP actually changed before continuing.
Off by default; enabled via Config.rotate_ip_cmd. All free — no proxies.

Detects BOTH IPv4 and IPv6 egress: Agoda is frequently reached over IPv6, and an ISP that
hands out a /64 lets you rotate the v6 address for free (see scripts/rotate_ip_macos.sh) even
when the v4 address is sticky — so a change in EITHER family counts as a successful rotation.
"""
import asyncio
import contextlib

_V4 = ("https://api.ipify.org", "https://ipv4.icanhazip.com", "https://ifconfig.me/ip")
_V6 = ("https://api6.ipify.org", "https://ipv6.icanhazip.com")


async def _fetch(url, timeout):
    try:
        from curl_cffi import AsyncSession
    except Exception:
        try:
            from curl_cffi.requests import AsyncSession
        except Exception:
            return None
    try:
        async with AsyncSession() as s:
            r = await s.get(url, timeout=timeout)
            ip = (r.text or "").strip()
            return ip if ip and len(ip) <= 45 else None
    except Exception:
        return None


async def public_ips(timeout=8.0):
    """Return (ipv4, ipv6) best-effort; either may be None."""
    v4 = v6 = None
    for u in _V4:
        v4 = await _fetch(u, timeout)
        if v4:
            break
    for u in _V6:
        v6 = await _fetch(u, timeout)
        if v6:
            break
    return v4, v6


async def public_ip(timeout=8.0):
    """Back-compat: a single public-IP string (v4 preferred, else v6), or None."""
    v4, v6 = await public_ips(timeout)
    return v4 or v6


async def rotate(cfg, verbose=True, verify_timeout=90.0):
    """Run cfg.rotate_ip_cmd and wait until the public IPv4 OR IPv6 differs (or timeout).

    Returns (old, new, changed: bool) where old/new are "v4|v6" fingerprints. No-op returning
    (None, None, False) if unset.
    """
    if not cfg.rotate_ip_cmd:
        return None, None, False
    b4, b6 = await public_ips()
    before = f"{b4}|{b6}"
    if verbose:
        print(f"🔀 IP rotate: running {cfg.rotate_ip_cmd!r} (v4={b4} v6={b6})", flush=True)
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
        n4, n6 = await public_ips()
        # A change in EITHER family is a win (v6 rotation is the free lever on a /64).
        if (n4 and n4 != b4) or (n6 and n6 != b6):
            now = f"{n4}|{n6}"
            if verbose:
                print(f"   ✅ IP changed → v4={n4} v6={n6}", flush=True)
            return before, now, True
    if verbose:
        print(f"   ⚠️ IP unchanged within {int(verify_timeout)}s (v4={b4} v6={b6})", flush=True)
    return before, before, False
