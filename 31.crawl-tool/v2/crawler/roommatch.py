# -*- coding: utf-8 -*-
"""Room-name matching: pick the Agoda room dict that corresponds to a target room type.

The old matcher was exact-norm + Jaccard>=0.5. It false-NA'd whenever the sheet's room name
and Agoda's differed by LANGUAGE ("Chic Suite" sheet-side vs a vi-vn grid, "Deluxe" vs "Phòng
Loại Sang") or by phrasing. This module keeps that fast path and adds, in order:

  1. exact folded match
  2. bilingual-canonicalized match (VN<->EN synonym map collapses "loại sang"->"deluxe" etc.)
  3. containment + Jaccard on canonicalized tokens, with a first-token bonus
  4. optional LLM tie-break (opt-in; only when 1-3 all abstain) — cached per (target, rooms)

Everything except step 4 is free/offline/deterministic. Step 4 is off unless cfg.room_match_llm.

NOTE: common.norm() deletes Vietnamese diacritics outright (its class is [^a-z0-9]), which
destroys VN room words. This module folds diacritics to ASCII instead (giường->giuong,
loại->loai, đ->d) so the synonym map can bridge the two languages.
"""
import re
import unicodedata


def fold(s):
    """Lowercase + fold Vietnamese diacritics to ASCII + squash to space-separated tokens."""
    s = (s or "").lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# VN/EN room vocabulary -> a single canonical token (keys are ASCII-folded). Bidirectional:
# both the Agoda grid name and the sheet target run through the same collapse, so a match no
# longer depends on which language each side happens to be in.
_SYNONYMS = {
    # tiers
    "deluxe": "deluxe", "loai sang": "deluxe", "sang trong": "deluxe",
    "superior": "superior", "cao cap": "superior", "thuong hang": "superior",
    "standard": "standard", "tieu chuan": "standard",
    "premium": "premium", "premier": "premium", "hang sang": "premium",
    "executive": "executive", "dieu hanh": "executive",
    "suite": "suite", "grand": "grand", "junior": "junior",
    "family": "family", "gia dinh": "family",
    "studio": "studio", "penthouse": "penthouse", "president": "president", "tong thong": "president",
    "villa": "villa", "biet thu": "villa",
    "bungalow": "bungalow", "cottage": "cottage", "cabin": "cabin",
    # bedding
    "king": "king", "giuong king": "king", "giuong lon": "king",
    "queen": "queen", "giuong queen": "queen",
    "double": "double", "giuong doi": "double",
    "twin": "twin", "2 giuong": "twin", "hai giuong": "twin", "giuong don": "twin",
    "triple": "triple", "ba giuong": "triple",
    # views / features
    "sea view": "seaview", "ocean view": "seaview", "huong bien": "seaview",
    "pool view": "poolview", "huong be boi": "poolview", "huong ho boi": "poolview",
    "ho boi": "poolview", "be boi": "poolview",
    "garden view": "gardenview", "huong vuon": "gardenview",
    "city view": "cityview", "huong thanh pho": "cityview", "huong pho": "cityview",
    "mountain view": "mountainview", "huong nui": "mountainview",
    "river view": "riverview", "huong song": "riverview",
    "balcony": "balcony", "ban cong": "balcony",
    "terrace": "terrace", "san hien": "terrace",
    "breakfast": "breakfast", "an sang": "breakfast",
    # noise words worth dropping so they never dominate the token overlap
    "phong": "", "room": "", "voi": "", "kem": "", "co": "", "hoac": "",
    "and": "", "the": "", "of": "", "with": "", "or": "",
}

# Longest phrases first so "garden view" collapses before the bare "garden"/"view".
_PHRASES = sorted((k for k in _SYNONYMS if " " in k), key=len, reverse=True)


def canon(s):
    """Fold + collapse VN/EN synonyms to a canonical token bag (as a set)."""
    n = " " + fold(s) + " "
    for ph in _PHRASES:
        if ph in n:
            repl = _SYNONYMS[ph]
            n = n.replace(ph, f" {repl} " if repl else " ")
    out = set()
    for t in n.split():
        c = _SYNONYMS.get(t, t)
        if c:
            out.add(c)
    return out


def _score(ttok, ntok, tfirst, nfirst):
    if not ttok or not ntok:
        return 0.0
    inter = len(ttok & ntok)
    jacc = inter / len(ttok | ntok)
    # containment: sheet target fully inside the grid name (or vice versa) is a strong signal
    contain = inter / min(len(ttok), len(ntok))
    score = 0.6 * jacc + 0.4 * contain
    if tfirst and tfirst == nfirst:
        score += 0.15
    return score


def best_room(rooms, target, cfg=None):
    """Return (room_dict, method) or (None, reason). method/reason is a short label for logs."""
    named = [(rm, (rm.get("name") or "").strip()) for rm in rooms]
    named = [(rm, n) for rm, n in named if n]
    if not named:
        return None, "no-named-rooms"

    tfold = fold(target)
    for rm, n in named:                                  # 1) exact folded
        if fold(n) == tfold and tfold:
            return rm, "exact"

    tcan = canon(target)
    for rm, n in named:                                  # 2) canonical (synonym) exact
        if canon(n) == tcan and tcan:
            return rm, "canon-exact"

    tfirst = (tfold.split() or [""])[0]
    best, best_score = None, -1.0                        # 3) canonical containment + Jaccard
    for rm, n in named:
        ncan = canon(n)
        nfirst = (fold(n).split() or [""])[0]
        s = _score(tcan, ncan, tfirst, nfirst)
        if s > best_score:
            best_score, best = s, rm
    thr = getattr(cfg, "room_match_threshold", 0.5) if cfg else 0.5
    if best_score >= thr:
        return best, f"fuzzy:{best_score:.2f}"

    if cfg is not None and getattr(cfg, "room_match_llm", False):   # 4) opt-in LLM tie-break
        pick = _llm_pick(target, [n for _, n in named], cfg)
        if pick is not None:
            for rm, n in named:
                if n == pick:
                    return rm, "llm"

    return None, f"below-threshold:{best_score:.2f}"


# --- optional LLM fallback (opt-in; free default keeps everything above) -------------------
_llm_cache = {}


def _llm_pick(target, names, cfg):
    """Ask Claude to pick the matching room name, or None. Cached per (target, names).
    Requires ANTHROPIC_API_KEY + the `anthropic` package; any failure -> None (safe)."""
    key = (fold(target), tuple(sorted(fold(x) for x in names)))
    if key in _llm_cache:
        return _llm_cache[key]
    result = None
    try:
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("no ANTHROPIC_API_KEY")
        from anthropic import Anthropic
        client = Anthropic()
        listing = "\n".join(f"{i}. {n}" for i, n in enumerate(names))
        model = getattr(cfg, "room_match_llm_model", "claude-haiku-4-5-20251001")
        msg = client.messages.create(
            model=model, max_tokens=8,
            system=("You match hotel room names across Vietnamese and English. Reply with ONLY "
                    "the integer index of the room that best matches the target, or -1 if none "
                    "clearly matches. No other text."),
            messages=[{"role": "user",
                       "content": f"Target room: {target!r}\nCandidates:\n{listing}"}])
        txt = "".join(getattr(b, "text", "") for b in msg.content).strip()
        m = re.search(r"-?\d+", txt)
        if m:
            idx = int(m.group(0))
            if 0 <= idx < len(names):
                result = names[idx]
    except Exception:
        result = None
    _llm_cache[key] = result
    return result
