import pandas as pd
import pytest

from engine.mappers import MAPPERS, get_mapper, map_to_canonical
from engine.schema import SchemaError
from tests.conftest import fill


def test_registry_has_only_canonical_for_now():
    assert set(MAPPERS) == {"canonical"}


def test_canonical_mapper_validates_and_keeps_warnings():
    raw = pd.DataFrame([fill("10:00", "BUY", 75, 100)])
    out = get_mapper("canonical")(raw)
    assert out["fill_id"].tolist() == [0]
    assert any("gross" in w for w in out.attrs["warnings"])


def test_map_to_canonical_defaults_to_canonical():
    raw = pd.DataFrame([fill("10:00", "BUY", 75, 100)])
    assert len(map_to_canonical(raw)) == 1


def test_canonical_mapper_propagates_schema_errors():
    with pytest.raises(SchemaError):
        map_to_canonical(pd.DataFrame())


def test_unknown_mapper_lists_available():
    with pytest.raises(KeyError, match="canonical"):
        get_mapper("groww")
