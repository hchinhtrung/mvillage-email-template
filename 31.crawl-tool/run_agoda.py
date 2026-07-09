#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGODA crawler runner — reads the Agoda master Google Sheet and crawls every hotel.

    python3 run_agoda.py

Output lands in 31.crawl-tool/results/agoda/ :
    FINAL_<YYYYMMDD>.csv   (final result)
    TEMP_agoda.csv         (checkpoint — kill & re-run resumes only unfinished weeks)

Speed depends on Camoufox being importable (otherwise the run prints a warning and uses the
chromium warm). One-time setup inside the venv:
    pip install -U 'camoufox[geoip]' && python -m camoufox fetch
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))      # .../31.crawl-tool
sys.path.insert(0, ROOT)
import crawler

# ── Agoda input sheet (the tab's gid is parsed from the URL automatically) ──
SHEET = "https://docs.google.com/spreadsheets/d/1EauwTNOMVMBT_CUHwf4EtOz1nsZAjG2SJ_LEh199N0Q/edit?gid=1289817800#gid=1289817800"

OUTDIR = os.path.join(ROOT, "results", "agoda")
os.makedirs(OUTDIR, exist_ok=True)
os.chdir(OUTDIR)                                       # outputs land here

crawler.crawl(
    site="agoda",          # direct replay (fast) + Camoufox warm
    input=SHEET,
    weeks=6,
    # ---- optional ----
    # max=5,               # quick test: only the first 5 hotels
    # shard="1/3",         # split the 90 hotels into 3 runs: 1/3, then 2/3, then 3/3
    # engine="chromium",   # use if you ever upgrade playwright past 1.59
    # shared_capture=True, # repeat runs: 1 warm prices all hotels via propertyId swap (fastest)
    # room_match_llm=True, # Claude tie-break for room names the free matcher can't match
                           #   (needs ANTHROPIC_API_KEY in the environment)
)
