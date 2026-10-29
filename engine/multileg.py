"""Multi-leg tagging (SPEC section 6): warn and exclude, never analyse."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

WINDOW_SECONDS = 60


@dataclass(frozen=True)
class MultiLegResult:
    fills: pd.DataFrame
    n_groups: int
    warnings: list[str] = field(default_factory=list)


def _is_leg_pair(a, b) -> bool:
    """Two near-simultaneous fills on one underlying+expiry that look like legs of one strategy."""
    if a.option_type != b.option_type:
        return True
    return a.side != b.side and a.strike != b.strike


def _find(parent: dict[int, int], x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _group_ids(fills: pd.DataFrame) -> dict[int, int]:
    """Map fill_id -> group root for every fill that is part of a multi-leg cluster."""
    parent: dict[int, int] = {}
    for _, grp in fills.groupby(["underlying", "expiry"], sort=False):
        rows = list(grp.sort_values(["ts", "fill_id"], kind="stable").itertuples(index=False))
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if (b.ts - a.ts).total_seconds() > WINDOW_SECONDS:
                    break
                if not _is_leg_pair(a, b):
                    continue
                for fid in (a.fill_id, b.fill_id):
                    parent.setdefault(fid, fid)
                parent[_find(parent, a.fill_id)] = _find(parent, b.fill_id)
    return {fid: _find(parent, fid) for fid in parent}


def tag_multileg(fills: pd.DataFrame) -> MultiLegResult:
    """Return a copy of ``fills`` with a boolean ``possible_multi_leg`` column."""
    groups = _group_ids(fills)
    tagged = fills.copy()
    tagged["possible_multi_leg"] = tagged["fill_id"].isin(groups.keys())
    n_groups = len(set(groups.values()))
    warnings = []
    if n_groups:
        warnings.append(
            f"{n_groups} possible multi-leg group(s) detected ({len(groups)} fills); "
            "trips containing them are excluded from habit detection."
        )
    return MultiLegResult(fills=tagged, n_groups=n_groups, warnings=warnings)


def flag_trips(trips: pd.DataFrame, tagged_fills: pd.DataFrame) -> pd.DataFrame:
    """Return ``trips`` with ``possible_multi_leg`` True if any of the trip's fills is tagged."""
    tagged_ids = set(tagged_fills.loc[tagged_fills["possible_multi_leg"], "fill_id"])
    out = trips.copy()
    out["possible_multi_leg"] = [
        any(fid in tagged_ids for fid in ids) for ids in out["fill_ids"]
    ]
    return out
