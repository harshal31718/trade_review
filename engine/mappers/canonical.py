"""Passthrough mapper: the file is already in the canonical schema."""
import pandas as pd

from engine.schema import validate_trades


def canonical(raw: pd.DataFrame) -> pd.DataFrame:
    return validate_trades(raw)
