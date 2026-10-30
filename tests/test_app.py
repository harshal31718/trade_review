"""Headless UI tests with Streamlit's AppTest (runs app/main.py without a browser)."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


def fresh():
    return AppTest.from_file(APP, default_timeout=30).run()


def test_sample_preloaded_shows_disclaimer_and_up_to_three_habits():
    at = fresh()
    assert not at.exception
    text = " ".join(c.value for c in at.caption)
    assert "For demo purposes only. Not investment advice." in text
    assert 1 <= len(at.subheader) <= 3          # habit cards
    assert len(at.metric) >= 4 + 1              # header metrics + at least one habit metric
    assert any("INR" in m.value for m in at.metric)


def test_every_shown_habit_has_a_rupee_figure_and_nudge():
    at = fresh()
    assert len(at.info) == len(at.subheader)
    assert all("INR" in i.value for i in at.info)


def test_changing_a_threshold_reruns_cleanly():
    at = fresh()
    at.slider[0].set_value(5).run()
    assert not at.exception
