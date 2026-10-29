"""Mapper registry: {name -> function(raw_df) -> canonical_df} (SPEC section 4).

A mapper turns a broker export into the canonical schema. Warnings (dropped
rows, missing fees) travel on ``canonical_df.attrs["warnings"]``.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from engine.mappers.canonical import canonical

Mapper = Callable[[pd.DataFrame], pd.DataFrame]

MAPPERS: dict[str, Mapper] = {
    "canonical": canonical,
}


def get_mapper(name: str) -> Mapper:
    try:
        return MAPPERS[name]
    except KeyError:
        known = ", ".join(sorted(MAPPERS))
        raise KeyError(f"Unknown mapper '{name}'. Available: {known}.") from None


def map_to_canonical(raw: pd.DataFrame, mapper: str = "canonical") -> pd.DataFrame:
    return get_mapper(mapper)(raw)
