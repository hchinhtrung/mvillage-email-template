#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRIP.com crawler runner — reads the Trip master Google Sheet and crawls every hotel.

    python3 run_trip.py

Trip runs in BROWSER mode (its room API signs each request, so direct replay is not viable —
confirmed live). Slower than Agoda but reliable. Output lands in 31.crawl-tool/results/trip/ :
    FINAL_<YYYYMMDD>.csv   (final result)
    TEMP_trip.csv          (checkpoint — kill & re-run resumes only unfinished weeks)
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))      # .../31.crawl-tool
sys.path.insert(0, ROOT)
import crawler

# ── Trip input sheet (the tab's gid is parsed from the URL automatically) ──
SHEET = "https://docs.google.com/spreadsheets/d/1g_S06QeEAWnCTHYXGH0Nn4Mcb3FCT_-uIS1jUm4GGkw/edit?gid=607908359#gid=607908359"

OUTDIR = os.path.join(ROOT, "results", "trip")
os.makedirs(OUTDIR, exist_ok=True)
os.chdir(OUTDIR)                                       # outputs land here

crawler.crawl(
    site="trip",           # browser-per-query (direct replay not possible for Trip)
    input=SHEET,
    weeks=6,
    # ---- optional ----
    # max=5,               # quick test: only the first 5 hotels
    # shard="1/2",         # split the 55 hotels into 2 runs: 1/2, then 2/2
)
