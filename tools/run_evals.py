"""Run the evals and print/write the results table. Usage: python tools/run_evals.py

Ship bar (written BEFORE the first run, from SPEC s11):
  1. Every case in the table passes (Clarity is manual and reported as NOT RUN until done).
  2. The clean control surfaces 0 habits on every seed.
  3. User-level recall >= 0.8 across planted archetypes.
  4. <= 1 false habit in total across all hard-negative users.
Caveat: synthetic data tests implementation correctness, not real-world validity.
"""
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from engine.detectors import EXPIRY_CHEAP, LOSER_HOLDING, OVERSIZING, REVENGE  # noqa: E402
from engine.loader import load_fills  # noqa: E402
from engine.nudges import DESCRIPTIONS, TEMPLATES, TITLES  # noqa: E402
from engine.review import NO_HABIT_MESSAGE, analyse, analyse_detailed  # noqa: E402
from engine.schema import SchemaError, validate_trades  # noqa: E402
from engine.synthetic import make_users  # noqa: E402

SEEDS = range(10)
RECALL_BAR = 0.8
MAX_FALSE_HABITS_HARD_NEG = 1
HARD_NEGATIVES = ["hn_late_reentry", "hn_consistent_large", "hn_profitable_expiry"]
DETECTORS = [REVENGE, EXPIRY_CHEAP, OVERSIZING, LOSER_HOLDING]
OUT_PATH = ROOT / "data" / "synthetic" / "eval_results.md"
BANNED = ["buy", "sell", "short", "long", "call", "put", "bullish", "bearish",
          "gambled", "reckless", "stupid", "nifty", "banknifty"]


def fills(*rows):
    base = {"underlying": "NIFTY", "option_type": "CE", "strike": 24500, "expiry": "2026-11-04"}
    return validate_trades(pd.DataFrame([{**base, **r} for r in rows]))


def leg(ts, side, qty, price, **kw):
    return {"ts": ts, "side": side, "qty": qty, "price": price, **kw}


def clock(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"


# ------------------------------------------------------------------ table cases
def case_fifo():
    f = fills(leg("2026-10-28 10:00", "BUY", 100, 50), leg("2026-10-28 10:05", "BUY", 100, 60),
              leg("2026-10-28 10:20", "SELL", 150, 70), leg("2026-10-28 10:40", "SELL", 50, 40))
    _, trips, _ = analyse_detailed(f)
    pnl = trips["pnl"].iloc[0] if len(trips) else float("nan")
    return ("Correctness", "F2: BUY 100@50, BUY 100@60, SELL 150@70, SELL 50@40 (hand calc 100*20 + 50*10 + 50*(40-60))",
            "1 trip, pnl 1,500", f"{len(trips)} trip, pnl {pnl:,.0f}", len(trips) == 1 and abs(pnl - 1500) < 1e-6)


def case_revenge_rupees():
    rows = []
    for d in ("2026-10-26", "2026-10-27", "2026-10-28"):
        rows += [leg(f"{d} 10:00", "BUY", 75, 100), leg(f"{d} 10:10", "SELL", 75, 80),
                 leg(f"{d} 10:20", "BUY", 150, 90), leg(f"{d} 10:50", "SELL", 150, 70)]
    review = analyse(fills(*rows))
    h = next((x for x in review.habits if x.name == REVENGE), None)
    actual = (f"{h.n_flagged} flagged, observed {h.observed_pnl:,.0f}, estimate +{h.estimate_pnl:,.0f}"
              if h else "not reported")
    ok = bool(h) and h.n_flagged == 3 and abs(h.observed_pnl + 9000) < 1e-6 and abs(h.estimate_pnl - 9000) < 1e-6
    return ("Correctness", "F4 on 3 days: 75@100->80 (-1,500), then 150@90->70 (-3,000) 10 min later; hand calc 3 x -3,000",
            "re-entry habit reported, 3 flagged, observed -9,000, estimate +9,000", actual, ok)


def case_loser_holding():
    rows, t = [], 9 * 60
    for hold, exit_price in [(10, 110), (12, 110), (14, 110), (30, 90), (20, 90)]:
        rows += [leg(f"2026-10-28 {clock(t)}", "BUY", 75, 100), leg(f"2026-10-28 {clock(t + hold)}", "SELL", 75, exit_price)]
        t += 60
    r = analyse_detailed(fills(*rows))[2]["loser_holding"]
    return ("Correctness", "F8: winners held 10/12/14 min (median 12), losers held 30 and 20 min, each loser 75*(90-100)",
            "1 flagged (the 30-min loser), observed -750", f"{r.n_flagged} flagged, observed {r.observed_pnl:,.0f}",
            r.n_flagged == 1 and abs(r.observed_pnl + 750) < 1e-6)


def case_expiry_cheap():
    r = analyse_detailed(fills(leg("2026-11-04 10:00", "BUY", 75, 12), leg("2026-11-04 14:00", "SELL", 75, 0)))[2][EXPIRY_CHEAP]
    return ("Correctness", "F6: BUY 75@12 on expiry day, expires at 0 (hand calc 75*(0-12))",
            "flagged by the expiry check, pnl -900", f"{r.n_flagged} flagged, observed {r.observed_pnl:,.0f}",
            r.n_flagged == 1 and abs(r.observed_pnl + 900) < 1e-6)


def case_clean():
    review = analyse(validate_trades(make_users(0)["clean_control"].fills))
    return ("Edge", "Clean synthetic trader, no planted habit (seed 0)",
            f'0 habits and "{NO_HABIT_MESSAGE}"', f"{len(review.habits)} habits; message: {review.no_habit_message}",
            not review.habits and review.no_habit_message == NO_HABIT_MESSAGE)


def case_empty():
    try:
        load_fills(b"")
        actual, ok = "no error", False
    except SchemaError as exc:
        actual, ok = f"SchemaError: {exc}", "empty" in str(exc)
    return ("Edge", "Empty file (F10)", "Clear 'file is empty' message, no crash", actual, ok)


def case_missing_column():
    csv = b"ts,underlying,option_type,strike,expiry,side,qty\n2026-10-28 10:00,NIFTY,CE,24500,2026-11-04,BUY,75\n"
    try:
        load_fills(csv)
        actual, ok = "no error", False
    except SchemaError as exc:
        actual, ok = f"SchemaError: {exc}", "price" in str(exc)
    return ("Edge", "CSV without the price column (F10)", "Error that names 'price'", actual, ok)


def case_small_sample():
    rows = []
    for d in ("2026-10-27", "2026-10-28"):
        rows += [leg(f"{d} 10:00", "BUY", 75, 100), leg(f"{d} 10:10", "SELL", 75, 80),
                 leg(f"{d} 10:20", "BUY", 150, 90), leg(f"{d} 10:50", "SELL", 150, 70)]
    review, _, results = analyse_detailed(fills(*rows))
    n = results[REVENGE].n_flagged
    reported = [h.name for h in review.habits]
    return ("Edge", "Only 2 quick re-entries in the month (each loses 3,000)",
            "2 flagged but NOT reported (needs >= 3)", f"{n} flagged; reported: {reported or 'none'}",
            n == 2 and REVENGE not in reported)


def case_open_position():
    review = analyse(fills(leg("2026-10-28 10:00", "BUY", 75, 100)))
    warned = [w[:46] for w in review.warnings if "open" in w]
    return ("Edge", "F5: one BUY, never closed", "0 trips and a warning about 1 open/unmatched position",
            f"{review.n_trips} trips; warning: {warned}",
            review.n_trips == 0 and any(w.startswith("1 open/unmatched") for w in review.warnings))


def case_safety():
    texts = list(TEMPLATES.values()) + list(DESCRIPTIONS.values()) + list(TITLES.values())
    for user in make_users(0).values():
        texts += [h.nudge for h in analyse(validate_trades(user.fills)).habits]
    hits = sorted({w for t in texts for w in BANNED if re.search(rf"\b{w}\b", t, re.I)})
    bad_cf = [t for t in texts if "+INR" in t and "estimate" not in t]
    return ("Safety", f"{len(texts)} nudge/description/title strings (templates + habits shown for 9 synthetic users)",
            "No banned word or instrument name; every rupee counterfactual says 'estimate'",
            f"banned hits: {hits or 'none'}; counterfactuals missing 'estimate': {len(bad_cf)}", not hits and not bad_cf)


CASES = [case_fifo, case_revenge_rupees, case_loser_holding, case_expiry_cheap, case_clean,
         case_empty, case_missing_column, case_small_sample, case_open_position, case_safety]


def table() -> tuple[str, bool]:
    lines = ["| # | Type | Input | Expected | Actual | Pass/Fail | Fix |", "|---|---|---|---|---|---|---|"]
    all_ok = True
    for i, case in enumerate(CASES, 1):
        kind, inp, expected, actual, ok = case()
        all_ok &= ok
        lines.append(f"| {i} | {kind} | {inp} | {expected} | {actual} | {'PASS' if ok else 'FAIL'} | {'-' if ok else 'TBD'} |")
    lines.append(f"| {len(CASES) + 1} | Clarity | 1-2 non-traders use the app on a phone and note where they get stuck | "
                 "Can find the main habit and what to do in under a minute | Not run yet (manual) | NOT RUN | - |")
    return "\n".join(lines), all_ok


# ------------------------------------------------------------------ supplement
def surfaced(user, config=None) -> set[str]:
    return {h.name for h in analyse(validate_trades(user.fills), config).habits}


def trade_level() -> pd.DataFrame:
    tp, fp, fn = (dict.fromkeys(DETECTORS, 0) for _ in range(3))
    for seed in SEEDS:
        for user in make_users(seed).values():
            _, trips, results = analyse_detailed(validate_trades(user.fills))
            entries = trips.set_index("trip_id")["entry_ts"].dt.strftime("%Y-%m-%d %H:%M")
            for det in DETECTORS:
                flagged = {entries[i] for i in results[det].flagged_trip_ids}
                truth = set(user.planted_trades.get(det, ()))
                tp[det] += len(flagged & truth)
                fp[det] += len(flagged - truth)
                fn[det] += len(truth - flagged)
    rows = []
    for d in DETECTORS:
        prec = tp[d] / (tp[d] + fp[d]) if tp[d] + fp[d] else float("nan")
        rec = tp[d] / (tp[d] + fn[d]) if tp[d] + fn[d] else float("nan")
        rows.append((d, tp[d], fp[d], fn[d], f"{prec:.2f}", f"{rec:.2f}"))
    return pd.DataFrame(rows, columns=["detector", "TP", "FP", "FN", "precision", "recall"])


def user_level() -> dict:
    planted_total = planted_hit = control_false = hn_false = 0
    misses: list[tuple[str, int, str]] = []
    for seed in SEEDS:
        for name, user in make_users(seed).items():
            got = surfaced(user)
            planted_total += len(user.planted)
            planted_hit += len(got & user.planted)
            misses += [(name, seed, h) for h in sorted(user.planted - got)]
            if name == "clean_control":
                control_false += len(got)
            elif name in HARD_NEGATIVES:
                hn_false += len(got)
    return {"recall": planted_hit / planted_total, "planted": planted_total, "hit": planted_hit,
            "control_false": control_false, "hn_false": hn_false, "misses": misses}


SWEEPS = {"W": [5, 10, 15, 30, 45], "R": [0.5, 1.0, 1.5, 2.0], "P": [10, 20, 30, 50, 80], "K": [1.5, 2.0, 3.0, 4.0]}
DEFAULTS = {"W": 15, "R": 1.0, "P": 30, "K": 2.0}
SWEEP_USER = {"W": "revenge_trader", "R": "revenge_trader", "P": "expiry_gambler", "K": "oversizer"}
SWEEP_HABIT = {"W": REVENGE, "R": REVENGE, "P": EXPIRY_CHEAP, "K": OVERSIZING}


def sweep() -> str:
    lines = ["| Param | Value | Planted habit surfaced | False habits (control + hard negatives) |", "|---|---|---|---|"]
    for param, values in SWEEPS.items():
        for v in values:
            hit = false = 0
            for seed in SEEDS:
                users = make_users(seed)
                hit += SWEEP_HABIT[param] in surfaced(users[SWEEP_USER[param]], {param: v})
                false += sum(len(surfaced(users[n], {param: v})) for n in ["clean_control", *HARD_NEGATIVES])
            mark = " (default)" if v == DEFAULTS[param] else ""
            lines.append(f"| {param} | {v}{mark} | {hit}/{len(SEEDS)} seeds | {false} |")
    return "\n".join(lines)


def main() -> int:
    buf = io.StringIO()

    def out(s=""):
        print(s, file=buf)

    out("# Eval results (generated by tools/run_evals.py)")
    out("Caveat: synthetic data tests implementation correctness, not real-world validity.\n")
    out("## Ship bar (fixed before running)")
    out(f"1. All table cases pass. 2. Clean control surfaces 0 habits on all {len(SEEDS)} seeds. "
        f"3. User-level recall >= {RECALL_BAR}. 4. <= {MAX_FALSE_HABITS_HARD_NEG} false habit across all hard-negative users.\n")
    out("## Cases")
    tbl, cases_ok = table()
    out(tbl)
    ul = user_level()
    out(f"\n## Supplement: synthetic archetypes, seeds 0-{len(SEEDS) - 1} ({len(SEEDS) * 9} users)")
    out(f"- User-level recall (planted habit surfaced): {ul['hit']}/{ul['planted']} = {ul['recall']:.2f}")
    out(f"- Clean control false habits (all seeds): {ul['control_false']}")
    out(f"- Hard-negative false habits (all seeds): {ul['hn_false']}\n")
    out("## Known limitations")
    known = [m for m in ul["misses"] if m[0] == "combined" and m[2] == EXPIRY_CHEAP]
    out(f"- Rupees-per-trade comparison (SPEC s13) under-measures cheap-premium habits in a mixed trader; "
        f"fix = compare return on premium. Attributed misses: {len(known)} of {len(ul['misses'])} "
        f"(combined archetype, expiry-day habit, seeds {sorted(m[1] for m in known)}).")
    other = [m for m in ul["misses"] if m not in known]
    out(f"- Misses NOT explained by this limitation: {len(other)}" + (f" {other}" if other else ""))
    out()
    out("Trade-level (planted trades vs flagged trips, all users):\n")
    out(trade_level().to_string(index=False))
    out("\n## Threshold sweep (one parameter at a time, others at default)")
    out(sweep())
    bar = [("All table cases pass", cases_ok), ("Control surfaces 0 habits", ul["control_false"] == 0),
           (f"Recall >= {RECALL_BAR}", ul["recall"] >= RECALL_BAR),
           (f"<= {MAX_FALSE_HABITS_HARD_NEG} false habit on hard negatives", ul["hn_false"] <= MAX_FALSE_HABITS_HARD_NEG)]
    out("\n## Ship bar verdict")
    for label, ok in bar:
        out(f"- {'PASS' if ok else 'FAIL'}: {label}")
    text = buf.getvalue()
    OUT_PATH.write_text(text, encoding="utf-8")
    print(text.encode("ascii", "replace").decode())
    return 0 if all(ok for _, ok in bar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
