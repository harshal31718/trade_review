"""A new deploy must never be served a Review cached by older engine code."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import engine.review
import engine.version
from engine.version import code_version

APP = str(Path(__file__).resolve().parent.parent / "app" / "main.py")


def test_code_version_changes_when_engine_code_changes(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    before = code_version(tmp_path)
    assert code_version(tmp_path) == before
    (tmp_path / "a.py").write_text("x = 2\n")
    assert code_version(tmp_path) != before


def test_code_version_tracks_the_real_engine_package():
    assert len(code_version()) == 16


@pytest.fixture
def counted_analyse(monkeypatch):
    calls = []
    real = engine.review.analyse
    monkeypatch.setattr(engine.review, "analyse", lambda *a, **k: calls.append(1) or real(*a, **k))
    st.cache_data.clear()
    yield calls
    st.cache_data.clear()


def test_new_code_version_recomputes_instead_of_serving_stale_review(monkeypatch, counted_analyse):
    monkeypatch.setattr(engine.version, "code_version", lambda *a, **k: "old-code")
    AppTest.from_file(APP, default_timeout=60).run()
    first = len(counted_analyse)
    AppTest.from_file(APP, default_timeout=60).run()
    assert len(counted_analyse) == first          # same code version: cache is used
    monkeypatch.setattr(engine.version, "code_version", lambda *a, **k: "new-code")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert len(counted_analyse) == first + 1      # new code version: recomputed
    assert not at.exception
