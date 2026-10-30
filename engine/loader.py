"""Read an uploaded or bundled CSV into canonical fills, with size and row caps."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from engine.mappers import map_to_canonical
from engine.schema import SchemaError

MAX_UPLOAD_BYTES = 2_000_000
MAX_ROWS = 5_000


def load_fills(data: bytes, mapper: str = "canonical",
               max_bytes: int = MAX_UPLOAD_BYTES, max_rows: int = MAX_ROWS) -> pd.DataFrame:
    """Parse CSV bytes and map to the canonical schema. Raises SchemaError with a user-facing message."""
    if len(data) > max_bytes:
        raise SchemaError(f"The file is {len(data) / 1e6:.1f} MB; the limit is {max_bytes / 1e6:.0f} MB.")
    if not data.strip():
        raise SchemaError("The file is empty: no trade rows were found.")
    try:
        raw = pd.read_csv(io.BytesIO(data))
    except UnicodeDecodeError:
        raise SchemaError("The file could not be read as text. Please upload a CSV file.") from None
    except pd.errors.EmptyDataError:
        raise SchemaError("The file is empty: no trade rows were found.") from None
    except pd.errors.ParserError as exc:
        raise SchemaError(f"The file is not a valid CSV: {exc}") from None
    if len(raw) > max_rows:
        raise SchemaError(f"The file has {len(raw):,} rows; the limit is {max_rows:,}.")
    return map_to_canonical(raw, mapper)


def load_path(path: Path, mapper: str = "canonical") -> pd.DataFrame:
    return load_fills(Path(path).read_bytes(), mapper)
