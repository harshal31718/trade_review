"""Shared helpers for building canonical fill frames in tests."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.schema import validate_trades  # noqa: E402

DEFAULT_EXPIRY = "2026-11-04"
DEFAULT_DAY = "2026-10-28"


def fill(time, side, qty, price, *, day=DEFAULT_DAY, underlying="NIFTY",
         strike=24500, option_type="CE", expiry=DEFAULT_EXPIRY, **extra):
    """One raw fill row. ``time`` is 'HH:MM' or 'HH:MM:SS' IST on ``day``."""
    row = {
        "ts": f"{day} {time}", "underlying": underlying, "option_type": option_type,
        "strike": strike, "expiry": expiry, "side": side, "qty": qty, "price": price,
    }
    row.update(extra)
    return row


def fills_df(*rows):
    """Validated canonical frame from fill() rows."""
    return validate_trades(pd.DataFrame(list(rows)))
