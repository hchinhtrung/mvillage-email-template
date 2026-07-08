# -*- coding: utf-8 -*-
"""Checkpoint I/O: only-improve + atomic CSV writes, and resume-by-week loading.

Output schema (matches the existing pipeline): hotel_name, room_type, price_w1..price_wN.
only-improve: a fresh NA/blank NEVER overwrites a previously real price; SOLD OUT may replace NA.
"""
import os

from .common import is_real


def save_backup_csv(all_week_prices, filename, num_weeks):
    """Merge `all_week_prices` (keyed by (hotel_name, room_type)) into `filename` and write
    atomically. Existing real prices are preserved against fresh NA/blank."""
    import pandas as pd
    try:
        rows, written = [], set()
        if os.path.exists(filename):
            try:
                df_old = pd.read_csv(filename, keep_default_na=False, na_values=[])
                for _, row in df_old.iterrows():
                    k = (str(row.get("hotel_name", "")), str(row.get("room_type", "")))
                    written.add(k)
                    if k in all_week_prices:
                        nr = {"hotel_name": k[0], "room_type": k[1]}
                        for i in range(1, num_weeks + 1):
                            old = str(row.get(f"price_w{i}", "NA")).strip()
                            new = str(all_week_prices[k].get(f"Price W{i}", "NA")).strip()
                            if new in ("NA", "nan", "") and old not in ("NA", "nan", ""):
                                nr[f"price_w{i}"] = old
                            else:
                                nr[f"price_w{i}"] = new if new not in ("nan", "") else "NA"
                        rows.append(nr)
                    else:
                        rows.append(row.to_dict())
            except Exception:
                pass
        for (hotel, room), prices in all_week_prices.items():
            if (hotel, room) not in written:
                r = {"hotel_name": hotel, "room_type": room}
                for i in range(1, num_weeks + 1):
                    r[f"price_w{i}"] = prices.get(f"Price W{i}", "NA")
                rows.append(r)
        tmp = filename + ".tmp"
        pd.DataFrame(rows).to_csv(tmp, index=False, encoding="utf-8-sig")
        os.replace(tmp, filename)
    except Exception as e:
        print(f"❌ Error saving {filename}: {e}", flush=True)


def load_prev(filename, num_weeks):
    """Load a checkpoint into {(hotel_name, room_type): {"Price W1".."Price WN"}}."""
    prev = {}
    if not os.path.exists(filename):
        return prev
    try:
        import pandas as pd
        dp = pd.read_csv(filename, keep_default_na=False, na_values=[])
        for _, row in dp.iterrows():
            k = (str(row.get("hotel_name", "")), str(row.get("room_type", "")))
            p = {}
            for i in range(1, num_weeks + 1):
                v = str(row.get(f"price_w{i}", "NA")).strip()
                p[f"Price W{i}"] = "NA" if (not v or v in ("nan", "NA")) else v
            prev[k] = p
    except Exception:
        pass
    return prev


def weeks_needed(prev, key, num_weeks):
    """Weeks that still lack a real price for this hotel (drives resume)."""
    row = prev.get(key)
    if not row:
        return list(range(1, num_weeks + 1))
    return [i for i in range(1, num_weeks + 1) if not is_real(row.get(f"Price W{i}", "NA"))]
