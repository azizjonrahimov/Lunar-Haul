"""E46 (B-76) payment and sharing arithmetic in tools/atc/run_e46.py."""
import itertools
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "atc"))
import run_e46 as M  # noqa: E402


def _run():
    owners = {o: {"delay_usd": 100.0 * (i + 1), "delay_h": 1.0, "items": 1, "delivered": 1, "delivered_kg": 1.0}
              for i, o in enumerate(M.OWNERS)}
    jobs = [{"t": 0.0, "t_end": 5.0, "carriers": ["A"], "cost": 1000.0, "team": False,
             "items": [["B", 100.0, 0.5]], "alts": [["C", 1500.0], ["B", 1200.0]]},
            {"t": 1.0, "t_end": 9.0, "carriers": ["B", "C"], "cost": 2000.0, "team": True,
             "items": [["A", 900.0, 2.0]], "alts": []}]
    return {"eps": {"A": 1.0, "B": 1.0, "C": 1.0}, "horizon_h": 8.0, "members": list(M.OWNERS),
            "owners": owners, "jobs": jobs}


def test_first_price_pays_the_ask_and_scales_with_k():
    r = _run()
    a1 = M.money(r, "first", 100.0)["profit"]["A"]
    a2 = M.money(r, "first", 100.0, dev_owner="A", k=1.1)["profit"]["A"]
    assert a2 - a1 == pytest.approx(100.0)          # 10 % of A's 1,000 USD ask


def test_second_price_pays_lowest_competing_ask_or_the_tariff():
    r = _run()
    x = M.money(r, "second", 100.0)
    # job 1: A paid 1,200 (B's ask); job 2 has no competitor: tariff 100 x 2 tkm = 200, below the asks -> asks
    assert x["profit"]["A"] == pytest.approx(1200.0 - 1000.0 - 100.0 * 2.0 - 100.0)


def test_posted_budget_balances_and_audits_fine_shading():
    r = _run()
    assert M.money(r, "posted", 100.0)["budget"] == pytest.approx(0.0)
    f = M.money(r, "first", 100.0, dev_owner="A", k=1.2, q=0.2, m=3.0)["fines"]["A"]
    assert f == pytest.approx(0.2 * 3.0 * 200.0)


def test_shapley_is_efficient_and_symmetric():
    v = {frozenset(): 0.0, frozenset("A"): -10.0, frozenset("B"): -10.0, frozenset("C"): -30.0,
         frozenset("AB"): -12.0, frozenset("AC"): -25.0, frozenset("BC"): -25.0, frozenset("ABC"): -20.0}
    phi = M.shapley(v, M.OWNERS)
    assert sum(phi.values()) == pytest.approx(-20.0)
    assert phi["A"] == pytest.approx(phi["B"])


def test_plan_has_36_runs_per_seed():
    assert len(M.plan(seeds=[1])) == 36
    assert len(M.plan()) == 1080
