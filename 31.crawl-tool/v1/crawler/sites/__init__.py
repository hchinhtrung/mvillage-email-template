# -*- coding: utf-8 -*-
"""Site adapter registry."""
from .agoda import AgodaAdapter
from .trip import TripAdapter

_REGISTRY = {
    "agoda": AgodaAdapter,
    "trip": TripAdapter,
}


def get_adapter(site, cfg):
    key = (site or "").strip().lower()
    if key not in _REGISTRY:
        raise ValueError(f"unknown site {site!r}; choose from {sorted(_REGISTRY)}")
    return _REGISTRY[key](cfg)


__all__ = ["get_adapter", "AgodaAdapter", "TripAdapter"]
