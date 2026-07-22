# -*- coding: utf-8 -*-
"""SiteAdapter — the per-site surface the engine drives.

An adapter knows: which XHR carries the room list, how to rewrite the check-in date into
the hotel URL, how to tell a room-bearing response from an empty one, and how to turn a
response into a priced/sold-out/blocked/NA verdict. Everything else (warm, replay, pacing,
checkpoint, orchestration) is site-agnostic and lives in the core modules.
"""


class SiteAdapter:
    name = "base"
    api_hint = ""                 # substring identifying the room-list request URL
    direct_replay = False         # True once capture->replay is proven for the site
    price_prefix = ""             # cosmetic prefix already baked into extract()'s price

    def __init__(self, cfg):
        self.cfg = cfg

    # --- URL ---
    def update_url_checkin(self, url, checkin):
        """Return the hotel URL rewritten for a given check-in date."""
        raise NotImplementedError

    # --- response classification ---
    def response_has_rooms(self, resp_json):
        """True if the raw HTTP JSON carries an actual room list (not an empty skeleton)."""
        raise NotImplementedError

    def response_is_definitive(self, resp_json):
        """True if this response already carries the day's final verdict (rooms present, or an
        unambiguous full-property sold-out) — waiting longer cannot improve it. Lets the browser
        wait loops stop early instead of burning the full api_wait_timeout_s on sold-out days."""
        try:
            return self.response_has_rooms(resp_json)
        except NotImplementedError:
            return False

    def extract(self, resp_json, target_room):
        """Classify a raw HTTP JSON response for target_room. Returns one of:
          {found:True, price:<str>, room:<name>}         # priced
          {found:False, soldOut:True, ...}               # GENUINE sold-out
          {found:False, soldOut:False, blocked:True}     # soft-block -> retry, never a price
          {found:False, soldOut:False, rooms:[...]}      # room mismatch -> NA
        """
        raise NotImplementedError

    # --- optional browser-side DOM fallback (used only if the API is never captured) ---
    dom_extract_js = None

    def extract_from_dom(self, dom, target_room):
        return {"found": False, "soldOut": False}
