# -*- coding: utf-8 -*-
"""Command-line interface.

  python -m crawler doctor
  python -m crawler capture --site agoda --url "<hotel url>" [--room "Deluxe"]
  python -m crawler replay  --site agoda [--room "Deluxe"]
  python -m crawler diag    --site agoda --url "<url>" --room "Deluxe"
  python -m crawler crawl   --site agoda --input agoda1.csv [--shard 1/5] [--weeks 6] [--max 5]
                            [--engine camoufox|chromium] [--headless/--no-headless]
                            [--rotate-ip-cmd "<shell cmd>"]
"""
import argparse
import asyncio

from .config import Config


def _add_common(p):
    p.add_argument("--site", default="agoda", choices=["agoda", "trip"])
    p.add_argument("--engine", default=None, choices=["camoufox", "chromium"])
    p.add_argument("--impersonate", default=None, help="force curl_cffi target, e.g. firefox147")
    p.add_argument("--headless", dest="headless", action="store_true", default=None)
    p.add_argument("--no-headless", dest="headless", action="store_false")


def _cfg_from(args):
    cfg = Config()
    if getattr(args, "engine", None):
        cfg.engine = args.engine
    if getattr(args, "impersonate", None):
        cfg.impersonate = args.impersonate
    if getattr(args, "headless", None) is not None:
        cfg.headless = args.headless
    if getattr(args, "rotate_ip_cmd", None):
        cfg.rotate_ip_cmd = args.rotate_ip_cmd
    if getattr(args, "rotate_after_blocks", None):
        cfg.rotate_after_blocks = args.rotate_after_blocks
    if getattr(args, "shared_capture", None):
        cfg.shared_capture = True
    if getattr(args, "room_match_llm", None):
        cfg.room_match_llm = True
    return cfg


def build_parser():
    ap = argparse.ArgumentParser(prog="crawler", description="Free direct-API price crawler (Agoda/Trip)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check THIS interpreter: packages + browser binaries + venv match")

    c = sub.add_parser("capture", help="Gate 0: warm + capture one real room-API request")
    _add_common(c)
    c.add_argument("--url", required=True)
    c.add_argument("--room", default="")

    r = sub.add_parser("replay", help="Gate 1: replay verbatim + +14d")
    _add_common(r)
    r.add_argument("--room", default="")

    d = sub.add_parser("diag", help="Compare warm-response vs curl_cffi replay")
    _add_common(d)
    d.add_argument("--url", required=True)
    d.add_argument("--room", required=True)

    s = sub.add_parser("shared-gate", help="Gate S: prove one warm can price many hotels (propertyId swap)")
    _add_common(s)
    s.add_argument("--url", required=True, help="hotel A (warmed)")
    s.add_argument("--url2", required=True, help="hotel B URL, or B's raw numeric propertyId")
    s.add_argument("--room", default="")

    g = sub.add_parser("crawl", help="Full hybrid crawl (direct + browser fallback)")
    _add_common(g)
    g.add_argument("--input", default="agoda1.csv",
                   help="CSV/XLSX path, 'gsheet:<id>', or a full Google Sheets URL (gid auto-parsed)")
    g.add_argument("--sheet", default="", help="worksheet/tab name (gsheet by name / xlsx)")
    g.add_argument("--gid", default="", help="worksheet tab id (gsheet); overrides gid in the URL")
    g.add_argument("--shard", default="", help="'N/M' — crawl only shard N of M")
    g.add_argument("--weeks", type=int, default=0, help="0 = 6")
    g.add_argument("--max", type=int, default=0, help="cap number of hotels (0 = all)")
    g.add_argument("--out", default="", help="final CSV name (default FINAL_<date>.csv)")
    g.add_argument("--temp", default="", help="checkpoint CSV name")
    g.add_argument("--rotate-ip-cmd", dest="rotate_ip_cmd", default="",
                   help="shell command to switch IP (opt-in); verified before continuing")
    g.add_argument("--rotate-after-blocks", dest="rotate_after_blocks", type=int, default=0,
                   help="rotate IP starting at this cooldown round (0 = never)")
    g.add_argument("--shared-capture", dest="shared_capture", action="store_true", default=None,
                   help="opt-in: one warm prices many hotels via propertyId swap (repeat runs)")
    g.add_argument("--room-match-llm", dest="room_match_llm", action="store_true", default=None,
                   help="opt-in: Claude tie-break when the free room matcher abstains (needs ANTHROPIC_API_KEY)")
    return ap


def main(argv=None):
    from . import gates, orchestrate
    args = build_parser().parse_args(argv)
    if args.cmd == "doctor":
        from . import envcheck
        return 1 if envcheck.check(verbose=True) else 0
    cfg = _cfg_from(args)
    if args.cmd == "capture":
        return asyncio.run(gates.gate_capture(args.site, args.url, args.room, cfg))
    if args.cmd == "replay":
        return asyncio.run(gates.gate_replay(args.site, args.room, cfg))
    if args.cmd == "diag":
        return asyncio.run(gates.gate_diag(args.site, args.url, args.room, cfg))
    if args.cmd == "shared-gate":
        return asyncio.run(gates.gate_shared(args.site, args.url, args.url2, args.room, cfg))
    if args.cmd == "crawl":
        return asyncio.run(orchestrate.run(
            site=args.site, input=args.input, sheet=args.sheet, gid=args.gid, shard=args.shard,
            weeks=args.weeks, max=args.max, out=args.out, temp=args.temp, cfg=cfg))


if __name__ == "__main__":
    main()
