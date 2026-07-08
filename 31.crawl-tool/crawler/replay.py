# -*- coding: utf-8 -*-
"""Direct replay: re-issue the captured room-API request with only the dates shifted."""
import re
from datetime import datetime, timedelta

from .session import build_headers

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def shift_dates(text, delta_days):
    """Shift EVERY YYYY-MM-DD in `text` by delta_days.

    Both checkIn AND checkOut move together so the length-of-stay window stays valid.
    Shifting only checkIn would make checkOut < checkIn -> server returns empty -> a FALSE
    'SOLD OUT'. (Confirmed on Agoda during prototype development.)
    """
    if not text or delta_days == 0:
        return text

    def repl(m):
        try:
            return (datetime.strptime(m.group(0), "%Y-%m-%d")
                    + timedelta(days=delta_days)).strftime("%Y-%m-%d")
        except Exception:
            return m.group(0)

    return _DATE_RE.sub(repl, text)


def parameterize(cap_req, orig_checkin, new_checkin):
    """Return (method, url, headers, data) for the request re-dated to new_checkin."""
    try:
        delta = (datetime.strptime(new_checkin, "%Y-%m-%d")
                 - datetime.strptime(orig_checkin, "%Y-%m-%d")).days
    except Exception:
        delta = 0
    method = cap_req["method"]
    url = shift_dates(cap_req["url"], delta)
    headers = build_headers(cap_req.get("headers"))
    data = shift_dates(cap_req.get("post_data"), delta)
    return method, url, headers, data


async def query_via_capture(sess, cap, checkin, timeout=30):
    """Issue one replayed request for `checkin`. Returns (status_code, json_or_None)."""
    method, url, headers, data = parameterize(cap["req"], cap["checkin"],
                                              checkin.strftime("%Y-%m-%d"))
    try:
        if method.upper() == "POST":
            resp = await sess.post(url, headers=headers, data=data, timeout=timeout)
        else:
            resp = await sess.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        return None, {"_error": str(e)}
    try:
        j = resp.json()
    except Exception:
        j = None
    return resp.status_code, j
