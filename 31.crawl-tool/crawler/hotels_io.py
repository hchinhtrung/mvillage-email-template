# -*- coding: utf-8 -*-
"""Hotel-list input (Google Sheet master / CSV / XLSX) + auto-sharding.

Input resolution:
  - "gsheet:<id>" or a docs.google.com URL  -> Google Sheet via gviz CSV export
  - "*.xlsx"                                 -> Excel (sheet with hyperlink targets)
  - anything else                            -> CSV (searched under 31.crawl-tool if not found)

Only the first three columns are used (hotel_name, hotel_url, room_type); the original URL
host is preserved so returned room names match the language of room_type in the sheet.
"""
import glob
import os
from urllib.parse import quote


def _norm_cols(df):
    req = ["hotel_name", "hotel_url", "room_type"]
    if not all(c in df.columns for c in req):
        df.columns = req + list(df.columns[3:])
    df = df[df["hotel_url"].notna() & (df["hotel_url"].astype(str).str.strip() != "")]
    return df[req]


def _resolve_local(path):
    if os.path.exists(path):
        return path
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)  # 31.crawl-tool
    cands = glob.glob(os.path.join(root, "**", os.path.basename(path)), recursive=True)
    return cands[0] if cands else path


def _gsheet_url(spec, sheet_name=""):
    sid = spec
    if spec.startswith("gsheet:"):
        sid = spec.split(":", 1)[1]
    elif "docs.google.com" in spec:
        # .../spreadsheets/d/<ID>/...
        parts = spec.split("/d/")
        if len(parts) > 1:
            sid = parts[1].split("/")[0]
    url = f"https://docs.google.com/spreadsheets/d/{sid}/gviz/tq?tqx=out:csv"
    if sheet_name:
        url += f"&sheet={quote(sheet_name)}"
    return url


def read_hotels(input_spec, sheet_name=""):
    """Return a list of (hotel_name, hotel_url, room_type) tuples."""
    import pandas as pd

    spec = str(input_spec)
    if spec.startswith("gsheet:") or "docs.google.com" in spec:
        df = _norm_cols(pd.read_csv(_gsheet_url(spec, sheet_name)))
    elif spec.endswith(".xlsx"):
        df = _read_xlsx(_resolve_local(spec), sheet_name or "Hotel Link")
    else:
        df = _norm_cols(pd.read_csv(_resolve_local(spec), encoding="utf-8-sig"))
    return [(r["hotel_name"], r["hotel_url"], r["room_type"]) for _, r in df.iterrows()]


def _read_xlsx(path, sheet_name):
    import pandas as pd
    from openpyxl import load_workbook

    wb = load_workbook(filename=path, data_only=True)
    ws = wb[sheet_name]
    rows = []
    for row in ws.iter_rows(min_row=2, max_col=3):
        hcell = row[0]
        rcell = row[2] if len(row) > 2 else None
        url = hcell.hyperlink.target if hcell.hyperlink else (hcell.value or "")
        rows.append({"hotel_name": hcell.value or "", "hotel_url": url,
                     "room_type": (rcell.value if rcell else "")})
    df = pd.DataFrame(rows)
    df = df[df["hotel_url"].notna() & df["hotel_url"].astype(str).str.startswith("http")]
    return df[["hotel_name", "hotel_url", "room_type"]]


def parse_shard(spec):
    """'2/5' -> (2, 5). Returns None if spec is empty/invalid."""
    if not spec:
        return None
    try:
        n, m = str(spec).split("/")
        n, m = int(n), int(m)
        if 1 <= n <= m:
            return (n, m)
    except Exception:
        pass
    raise ValueError(f"--shard must be 'N/M' with 1<=N<=M, got {spec!r}")


def apply_shard(items, shard):
    """Contiguous split into M near-equal chunks; return chunk N (1-based). Contiguous (not
    modulo) so a shard's rows stay grouped, which keeps resume/checkpoint local."""
    if not shard:
        return items
    n, m = shard
    total = len(items)
    base, rem = divmod(total, m)
    # chunk i (0-based) gets base (+1 for the first `rem` chunks)
    start = 0
    for i in range(n - 1):
        start += base + (1 if i < rem else 0)
    size = base + (1 if (n - 1) < rem else 0)
    return items[start:start + size]
