"""Seeded synthetic traders (SPEC section 11): planted archetypes, a clean control, hard negatives.

Synthetic data tests implementation correctness, not real-world validity. The same
seed always gives the same fills. No randomness outside ``random.Random(seed)``.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from engine.detectors import EXPIRY_CHEAP, LOSER_HOLDING, OVERSIZING, REVENGE

START = date(2026, 10, 1)
END = date(2026, 10, 30)
TUESDAY = 1                       # weekly expiry weekday used by the generator
BASE_QTY = 75
SLOT_A = (570, 600)               # entry minute-of-day range, 09:30-10:00
SLOT_B = (765, 795)               # 12:45-13:15
CHEAP_ENTRY_MINUTES = (585, 660)  # 09:45 and 11:00 on expiry day
STRIKES = (24400, 24500, 24600)


@dataclass(frozen=True)
class SyntheticUser:
    name: str
    seed: int
    fills: pd.DataFrame
    planted: frozenset[str]                         # habits deliberately planted
    planted_trades: dict[str, frozenset[str]] = field(default_factory=dict)  # habit -> entry "YYYY-MM-DD HH:MM"


def trading_days() -> list[date]:
    days, d = [], START
    while d <= END:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def expiry_for(day: date) -> date:
    return day + timedelta(days=(TUESDAY - day.weekday()) % 7)


def _hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


class _Book:
    def __init__(self, rng: random.Random):
        self.rng = rng
        self.rows: list[dict] = []
        self.labels: dict[str, set[str]] = {}

    def trip(self, day: date, entry_min: int, hold: int, qty: int, entry_price: float,
             exit_price: float, label: str | None = None, strike: int | None = None,
             option_type: str | None = None) -> int:
        """Add a BUY then SELL round trip; returns the exit minute-of-day."""
        strike = strike or self.rng.choice(STRIKES)
        option_type = option_type or self.rng.choice(("CE", "PE"))
        common = {
            "underlying": "NIFTY", "option_type": option_type, "strike": strike,
            "expiry": expiry_for(day).isoformat(), "qty": qty,
        }
        exit_min = entry_min + hold
        self.rows.append({"ts": f"{day} {_hhmm(entry_min)}:00", "side": "BUY", "price": round(entry_price, 2), **common})
        self.rows.append({"ts": f"{day} {_hhmm(exit_min)}:00", "side": "SELL", "price": round(exit_price, 2), **common})
        if label:
            self.labels.setdefault(label, set()).add(f"{day} {_hhmm(entry_min)}")
        return exit_min

    def outcome(self, entry_price: float, force: str | None = None) -> float:
        """Exit price: a win (+8..15%) or a loss (-6..12%); ``force`` fixes the side, a plain loss is -10..20%."""
        win = (self.rng.random() < 0.5) if force is None else force == "win"
        if win:
            return entry_price * (1 + self.rng.uniform(0.08, 0.15))
        spread = (0.06, 0.12) if force is None else (0.10, 0.20)
        return entry_price * (1 - self.rng.uniform(*spread))

    def normal(self, day: date, slot: tuple[int, int], *, qty: int = BASE_QTY,
               force: str | None = None, hold: int | None = None, label: str | None = None) -> tuple[int, float]:
        entry = self.rng.uniform(80, 150)
        start = self.rng.randint(*slot)
        hold = self.rng.randint(15, 40) if hold is None else hold
        exit_min = self.trip(day, start, hold, qty, entry, self.outcome(entry, force), label)
        return exit_min, entry


def _pick(days: list[date], indices: list[int]) -> set[date]:
    return {days[i] for i in indices if i < len(days)}


def _build(name: str, seed: int, habits: tuple[str, ...], *, big_all: bool = False,
           late_reentry: bool = False, profitable_expiry: bool = False) -> SyntheticUser:
    rng = random.Random(f"{name}-{seed}")
    book = _Book(rng)
    days = trading_days()
    plain = [d for d in days if d.weekday() != TUESDAY]
    expiry_days = [d for d in days if d.weekday() == TUESDAY]
    plan: dict[date, str] = {}
    if REVENGE in habits:
        for d in _pick(plain, [2, 4, 6, 8, 10, 12, 14, 16] if len(habits) == 1 else [2, 4, 6, 8, 10, 12]):
            plan[d] = "revenge"
    if late_reentry:
        for d in _pick(plain, [2, 4, 6, 8, 10, 12, 14, 16]):
            plan[d] = "late"
    if OVERSIZING in habits:
        for d in _pick(plain, [10, 12, 14, 15, 16, 17] if len(habits) == 1 else [13, 14, 15, 16, 17, 18]):
            plan[d] = "oversize"
    if LOSER_HOLDING in habits:
        for d in _pick(plain, [3, 6, 9, 12, 15, 18]):
            plan[d] = "holdloser"
    qty = 300 if big_all else BASE_QTY
    cheap_results = ["loss", "loss", "win", "loss", "loss", "loss", "win", "loss"]
    cheap_i = 0
    for day in days:
        kind = plan.get(day)
        if day in expiry_days and (EXPIRY_CHEAP in habits or profitable_expiry):
            for start in CHEAP_ENTRY_MINUTES:
                price = rng.uniform(6, 20)
                if profitable_expiry:
                    exit_price = price * rng.uniform(1.5, 2.5)
                else:
                    win = cheap_results[cheap_i % len(cheap_results)] == "win"
                    exit_price = price * (rng.uniform(1.4, 2.0) if win else rng.uniform(0.1, 0.5))
                    cheap_i += 1
                book.trip(day, start, rng.randint(20, 40), 150, price, exit_price, EXPIRY_CHEAP, 25000, "CE")
        elif kind == "revenge":
            exit_min, price = book.normal(day, SLOT_A, force="loss")
            gap = rng.randint(3, 10)
            p2 = price * rng.uniform(0.9, 1.1)
            book.trip(day, exit_min + gap, rng.randint(15, 30), 100, p2, book.outcome(p2, "loss"), REVENGE)
        elif kind == "late":
            exit_min, price = book.normal(day, SLOT_A, force="loss")
            p2 = price * rng.uniform(0.9, 1.1)
            book.trip(day, exit_min + 45, rng.randint(15, 30), 100, p2, book.outcome(p2))
        elif kind == "oversize":
            book.normal(day, SLOT_A, qty=300, force="loss", label=OVERSIZING)
        elif kind == "holdloser":
            book.normal(day, SLOT_A, force="loss", hold=rng.randint(70, 100), label=LOSER_HOLDING)
        else:
            book.normal(day, SLOT_A, qty=qty)
        book.normal(day, SLOT_B, qty=qty)

    planted = set(habits)
    fills = pd.DataFrame(book.rows).sort_values("ts", kind="stable").reset_index(drop=True)
    fills = fills[["ts", "underlying", "option_type", "strike", "expiry", "side", "qty", "price"]]
    return SyntheticUser(
        name=name, seed=seed, fills=fills, planted=frozenset(planted),
        planted_trades={h: frozenset(book.labels.get(h, set())) for h in planted},
    )


def make_users(seed: int = 0) -> dict[str, SyntheticUser]:
    """Every archetype for one seed: planted habits, clean control, hard negatives."""
    specs = {
        "revenge_trader": dict(habits=(REVENGE,)),
        "expiry_gambler": dict(habits=(EXPIRY_CHEAP,)),
        "oversizer": dict(habits=(OVERSIZING,)),
        "loser_holder": dict(habits=(LOSER_HOLDING,)),
        "combined": dict(habits=(REVENGE, EXPIRY_CHEAP, OVERSIZING)),
        "clean_control": dict(habits=()),
        "hn_late_reentry": dict(habits=(), late_reentry=True),
        "hn_consistent_large": dict(habits=(), big_all=True),
        "hn_profitable_expiry": dict(habits=(), profitable_expiry=True),
    }
    return {name: _build(name, seed, **spec) for name, spec in specs.items()}


if __name__ == "__main__":  # python -m engine.synthetic -> bundled sample for the app
    from pathlib import Path

    out = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "sample_trades.csv"
    make_users(0)["combined"].fills.to_csv(out, index=False)
    print(f"wrote {out}")
