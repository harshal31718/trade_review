import pytest

from engine.review import analyse
from engine.schema import validate_trades
from engine.synthetic import make_users

SEEDS = range(5)
PLANTED = ["revenge_trader", "expiry_gambler", "oversizer", "loser_holder", "combined"]
NEGATIVES = ["clean_control", "hn_late_reentry", "hn_consistent_large", "hn_profitable_expiry"]


def surfaced(user):
    return {h.name for h in analyse(validate_trades(user.fills)).habits}


def test_same_seed_gives_identical_fills():
    a, b = make_users(3), make_users(3)
    assert a["combined"].fills.equals(b["combined"].fills)


def test_different_seeds_differ():
    assert not make_users(1)["combined"].fills.equals(make_users(2)["combined"].fills)


def test_generated_files_validate():
    for user in make_users(0).values():
        assert len(validate_trades(user.fills)) > 20


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("name", PLANTED)
def test_planted_habits_are_surfaced(name, seed):
    user = make_users(seed)[name]
    assert surfaced(user) == set(user.planted)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("name", NEGATIVES)
def test_control_and_hard_negatives_surface_nothing(name, seed):
    assert surfaced(make_users(seed)[name]) == set()


def test_planted_trade_labels_exist_for_each_planted_habit():
    user = make_users(0)["combined"]
    assert all(len(user.planted_trades[h]) >= 3 for h in user.planted)
