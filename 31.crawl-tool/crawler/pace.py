# -*- coding: utf-8 -*-
"""Adaptive pacing (AIMD) for direct replay on a single free IP.

Rather than a fixed concurrency + fixed sleeps, the pacer starts conservative and:
  - additively ramps concurrency after a run of clean successes;
  - multiplicatively halves concurrency and enters a cooldown on any block signal.
This finds the fastest safe rate for the current IP without a human tuning constants.
"""
import asyncio
import random
import time

BLOCK_HTTP = {403, 429, 503}


def is_block_signal(status, result):
    """A response counts as a block (retry, never a price) if the HTTP status is a known
    throttle/deny code or the adapter classified it as a soft-block."""
    if status in BLOCK_HTTP:
        return True
    return bool((result or {}).get("blocked"))


class AdaptivePacer:
    def __init__(self, cfg):
        self.limit = max(1, cfg.pace_start)
        self.min = max(1, cfg.pace_min)
        self.max = max(self.min, cfg.pace_max)
        self.ramp_after = max(1, cfg.pace_ramp_after)
        self.jitter = cfg.pace_jitter
        self.block_cooldown = cfg.pace_block_cooldown
        self._active = 0
        self._ok_streak = 0
        self._cooldown_until = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        # Poll-based gate: robust and simple for IO-bound crawling (no Condition pitfalls).
        while True:
            async with self._lock:
                if self._active < self.limit and time.monotonic() >= self._cooldown_until:
                    self._active += 1
                    break
            await asyncio.sleep(0.15)
        await asyncio.sleep(random.uniform(*self.jitter))

    async def release(self):
        async with self._lock:
            self._active = max(0, self._active - 1)

    def record_ok(self):
        self._ok_streak += 1
        if self._ok_streak >= self.ramp_after and self.limit < self.max:
            self.limit += 1
            self._ok_streak = 0

    def record_block(self):
        self._ok_streak = 0
        self.limit = max(self.min, self.limit // 2)
        self._cooldown_until = time.monotonic() + random.uniform(*self.block_cooldown)

    def slot(self):
        return _Slot(self)

    def snapshot(self):
        return {"limit": self.limit, "active": self._active,
                "cooling": time.monotonic() < self._cooldown_until}


class _Slot:
    def __init__(self, pacer):
        self._pacer = pacer

    async def __aenter__(self):
        await self._pacer.acquire()
        return self._pacer

    async def __aexit__(self, *exc):
        await self._pacer.release()
        return False
