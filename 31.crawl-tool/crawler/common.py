# -*- coding: utf-8 -*-
"""Site-agnostic pure helpers. No network, no heavy imports — safe to import anywhere."""
import re


def to_int(s):
    """Strip everything non-digit -> int, or None."""
    n = re.sub(r"[^\d]", "", str(s) if s is not None else "")
    return int(n) if n else None


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def tokens(s):
    return set(t for t in norm(s).split() if t)


def is_real(v):
    """A cell holds a real price (not missing, not a sold-out marker)."""
    return v not in (None, "", "NA", "nan") and not str(v).startswith("SOLD OUT")
