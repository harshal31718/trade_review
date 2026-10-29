"""Fixed nudge templates, one per detector (SPEC section 9).

Behaviour only: no instrument, no direction, no advice on what to trade.
Any rupee counterfactual carries the word "estimate". Tone is kind and non-judgmental.
"""
from __future__ import annotations

from engine.detectors import (
    EXPIRY_CHEAP, FEE_DRAG, LOSER_HOLDING, OVERSIZING, REVENGE, DetectorResult,
)

DESCRIPTIONS: dict[str, str] = {
    REVENGE: "Trades opened soon after a loss, at the same or a larger size.",
    EXPIRY_CHEAP: "Low-premium trades opened on expiry day.",
    OVERSIZING: "Trades opened at a much larger size than your usual.",
    LOSER_HOLDING: "Losing trades held for much more time than your winning trades.",
    FEE_DRAG: "Charges taking a large share of what your trades moved.",
}

COUNTERFACTUAL = " If avoided (estimate): +INR {estimate}, assuming nothing else changes."

TEMPLATES: dict[str, str] = {
    REVENGE: (
        "{n} trades were opened within {W} minutes of a loss, at equal or larger size, "
        "and lost INR {loss} net. A fixed pause after a loss is one way people interrupt this pattern."
    ),
    EXPIRY_CHEAP: (
        "{n} trades were opened on expiry day at a low premium ({cheap_rule}) and lost INR {loss} net. "
        "Cheap premiums can look attractive on expiry day; writing down a size limit for these "
        "trades beforehand is one way people keep them contained."
    ),
    OVERSIZING: (
        "{n} trades were opened at more than {K} times your usual size and lost INR {loss} net. "
        "Setting a maximum size before the session starts is one way people keep position size steady."
    ),
    LOSER_HOLDING: (
        "{n} losing trades were held for more than {H} times the usual time of your winning trades, "
        "and lost INR {loss} net. Noting an exit time or level when you open a trade "
        "is one way people stop a loss from drifting."
    ),
    FEE_DRAG: (
        "Charges of INR {loss} across {n} trades were {ratio} of your gross profit-and-loss turnover. "
        "Reviewing how often orders are placed is one way people lower this."
    ),
}

NO_COUNTERFACTUAL = frozenset({LOSER_HOLDING, FEE_DRAG})


def _inr(value: float) -> str:
    return f"{abs(value):,.0f}"


def _cheap_rule(result: DetectorResult, config: dict) -> str:
    if result.method == "spot_moneyness":
        return f"at least {config['OTM_PCT']:.0%} away from the market price"
    return f"INR {config['P']:g} or less"


def _ratio(result: DetectorResult) -> str:
    for note in result.notes:
        if note.startswith("Fees were "):
            return note.split("Fees were ")[1].split(" of")[0]
    return "a large share"


def render_nudge(result: DetectorResult, config: dict, estimate: float | None) -> str:
    """Fill the fixed template for a reportable habit."""
    text = TEMPLATES[result.name].format(
        n=result.n_flagged, loss=_inr(result.observed_pnl),
        W=f"{config['W']:g}", K=f"{config['K']:g}", H=f"{config['H']:g}",
        cheap_rule=_cheap_rule(result, config) if result.name == EXPIRY_CHEAP else "",
        ratio=_ratio(result) if result.name == FEE_DRAG else "",
    )
    if result.name not in NO_COUNTERFACTUAL and estimate is not None:
        text += COUNTERFACTUAL.format(estimate=_inr(estimate))
    return text
