"""Post-trade review: Streamlit front end. All logic lives in engine/; this file only shows results."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from engine.loader import MAX_ROWS, MAX_UPLOAD_BYTES, load_fills  # noqa: E402
from engine.nudges import TITLES  # noqa: E402
from engine.review import analyse  # noqa: E402
from engine.schema import SchemaError  # noqa: E402
from engine.version import code_version  # noqa: E402

SAMPLE_PATH = ROOT / "data" / "synthetic" / "sample_trades.csv"
DISCLAIMER = "For demo purposes only. Not investment advice."
SAMPLE_NOTE = "Showing built-in sample data (synthetic, not a real trader)."

st.set_page_config(page_title="Post-trade review", layout="wide")


def inr(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}INR {abs(value):,.0f}"


@st.cache_data(show_spinner=False)
def run(data: bytes, config: tuple, version: str):
    """``version`` is only part of the cache key: new engine code must never reuse an old cached Review."""
    fills = load_fills(data)
    return analyse(fills, dict(config))


def threshold_controls() -> dict:
    with st.expander("Adjust thresholds (optional)"):
        c = st.columns(5)
        return {
            "W": c[0].slider("Re-entry window (min)", 5, 60, 15, 5),
            "R": c[1].slider("Re-entry size ratio", 0.5, 2.0, 1.0, 0.1),
            "P": c[2].slider("Cheap premium (INR)", 10, 100, 30, 5),
            "K": c[3].slider("Size vs usual (x)", 1.5, 4.0, 2.0, 0.5),
            "H": c[4].slider("Hold vs winners (x)", 1.0, 4.0, 2.0, 0.5),
        }


def choose_data() -> tuple[bytes, str]:
    st.session_state.setdefault("upload_n", 0)
    left, right = st.columns([3, 1], vertical_alignment="bottom")
    uploaded = left.file_uploader(
        "Upload your trades (CSV)", type="csv", key=f"upload_{st.session_state.upload_n}",
        help=f"Up to {MAX_UPLOAD_BYTES // 1_000_000} MB and {MAX_ROWS:,} rows.",
    )
    if right.button("Load sample", use_container_width=True):
        st.session_state.upload_n += 1
        st.rerun()
    if uploaded is not None:
        return uploaded.getvalue(), f"Showing {uploaded.name}."
    return SAMPLE_PATH.read_bytes(), SAMPLE_NOTE


def show_header(review) -> None:
    cols = st.columns(4)
    period = f"{review.period_start:%d %b} to {review.period_end:%d %b %Y}" if review.period_start else "n/a"
    cols[0].metric("Period", period)
    cols[1].metric("Completed trades", review.n_trips)
    cols[2].metric(f"Net P&L ({review.pnl_label})", inr(review.net_pnl))
    cols[3].metric("Win rate", f"{review.win_rate:.0%}" if review.win_rate is not None else "n/a")


def show_habit(habit) -> None:
    with st.container(border=True):
        st.subheader(TITLES[habit.name])
        st.caption(habit.description)
        st.metric(f"{habit.n_flagged} of {habit.n_total} trades", inr(habit.observed_pnl))
        if habit.flagged_avg_pnl is not None and habit.unflagged_avg_pnl is not None:
            st.write(f"Average per trade: **{inr(habit.flagged_avg_pnl)}** here vs "
                     f"**{inr(habit.unflagged_avg_pnl)}** on other trades.")
        st.info(habit.nudge)
        ev = habit.evidence.assign(entry_ts=habit.evidence["entry_ts"].dt.strftime("%d %b %H:%M"))
        st.dataframe(
            ev[["entry_ts", "instrument", "size", "pnl"]].rename(
                columns={"entry_ts": "Time", "instrument": "Instrument", "size": "Size (INR)", "pnl": "P&L (INR)"}),
            hide_index=True, use_container_width=True,
            column_config={"Size (INR)": st.column_config.NumberColumn(format="%.0f"),
                           "P&L (INR)": st.column_config.NumberColumn(format="%.0f")},
        )


def _pct(value) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _ratio(value) -> str:
    return "n/a (no losing trades)" if value is None else f"{value:.2f}"


def show_stats(review) -> None:
    stats = review.stats
    if stats is None:
        return
    with st.expander("Trade statistics"):
        st.caption("Descriptive only, from this file. Not a forecast or advice. "
                   f"P&L is {review.pnl_label}.")
        if stats.n_multi_leg_excluded:
            st.caption(f"({stats.n_multi_leg_excluded} multi-leg trades excluded)")
        st.markdown("**Performance**")
        a = st.columns(4)
        a[0].metric("Net P&L", inr(stats.net_pnl), help="Sum of profit and loss over all completed trades.")
        a[1].metric("Win rate", _pct(stats.win_rate), help="Winning trades divided by all completed trades.")
        a[2].metric("Average win", inr(stats.avg_win), help="Average profit of the winning trades.")
        a[3].metric("Average loss", "n/a" if stats.avg_loss is None else inr(stats.avg_loss),
                    help="Average size of the losing trades, as a positive amount.")
        b = st.columns(3)
        b[0].metric("Largest win", inr(stats.largest_win), help="The single best trade.")
        b[1].metric("Largest loss", inr(stats.largest_loss), help="The single worst trade, shown as a positive amount.")
        b[2].metric("Expectancy per trade", inr(stats.expectancy),
                    help="Average profit or loss per trade: win rate x average win minus loss rate x average loss.")
        st.markdown("**Risk and ratios**")
        c = st.columns(4)
        c[0].metric("Realised reward:risk", _ratio(stats.payoff_ratio),
                    help="Average win divided by average loss. Planned reward:risk is not in the file, so this is what was realised.")
        if stats.payoff_ratio_after_charges is not None:
            c[0].caption(f"after charges: {_ratio(stats.payoff_ratio_after_charges)}")
        c[1].metric("Profit factor", _ratio(stats.profit_factor),
                    help="Total profit of winning trades divided by total loss of losing trades.")
        c[2].metric("Breakeven win rate", _pct(stats.breakeven_win_rate),
                    help="The win rate needed to break even at your average win and loss: 1 / (1 + reward:risk), before charges.")
        c[3].metric("Max drawdown", inr(stats.max_drawdown),
                    help="Largest fall from a peak of cumulative profit to the next low, in rupees.")
        d = st.columns(3)
        d[0].metric("Longest losing streak", stats.longest_losing_streak, help="Most losing trades in a row.")
        d[1].metric("Longest winning streak", stats.longest_winning_streak, help="Most winning trades in a row.")
        d[2].metric("Average trade size", inr(stats.avg_trade_size),
                    help="Average premium paid per trade: quantity x entry price.")
        if stats.breakeven_win_rate is not None:
            st.write(f"At your average win and loss you break even at a {stats.breakeven_win_rate:.0%} win rate; "
                     f"yours is {stats.win_rate:.0%}.")


def main() -> None:
    st.title("Post-trade review")
    st.caption(f"{DISCLAIMER} A quick look at which repeat habits cost the most in your month of trades.")
    data, source_note = choose_data()
    config = threshold_controls()
    try:
        review = run(data, tuple(sorted(config.items())), code_version())
    except SchemaError as exc:
        st.error(str(exc))
        st.stop()
    st.caption(source_note)
    show_header(review)
    if review.habits:
        for col, habit in zip(st.columns(len(review.habits)), review.habits):
            with col:
                show_habit(habit)
        st.caption("Habits can overlap, so these rupee figures should not be added together.")
    else:
        st.success(review.no_habit_message)
    show_stats(review)
    if review.warnings:
        with st.expander(f"Notes and warnings ({len(review.warnings)})"):
            for warning in review.warnings:
                st.write(f"- {warning}")
    st.caption(DISCLAIMER)


main()
