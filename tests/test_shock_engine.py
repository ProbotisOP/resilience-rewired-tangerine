"""
Unit tests for deterministic shock engine and official Judge Match Runway.
"""

from config.scenarios import OFFICIAL_PRESETS, PRESET_DICT
from src.services.baseline_metrics import BaselineMetrics
from src.services.shock_engine import calculate_judge_runway, simulate_shock
from src.services.timeline_projection import project_shock_timeline
from src.ui.shock_simulator import _timeline_duration, _timeline_figure
import pandas as pd

def test_runway_edge_cases():
    # Edge Case 1: buffer_left <= 0 -> runway is 0.0 even if gap <= 0
    res1 = calculate_judge_runway(buffer=0.0, income_after_shock=5000, spending_after_shock=3000, one_off_costs=0.0)
    assert res1["runway"] == 0.0
    assert "Buffer Exhausted" in res1["runway_label"]

    res1b = calculate_judge_runway(buffer=-500.0, income_after_shock=5000, spending_after_shock=3000, one_off_costs=0.0)
    assert res1b["runway"] == 0.0

    # Edge Case 2: One-off expense exceeds buffer -> runway 0.0
    res2 = calculate_judge_runway(buffer=4000.0, income_after_shock=5000, spending_after_shock=4500, one_off_costs=5000.0)
    assert res2["runway"] == 0.0

    # Edge Case 3: Positive buffer and gap <= 0 -> "no shortfall (120+)"
    res3 = calculate_judge_runway(buffer=15000.0, income_after_shock=6000, spending_after_shock=5000, one_off_costs=0.0)
    assert res3["runway"] == 120.0
    assert "no shortfall (120+)" in res3["runway_label"]

    # Edge Case 4: Positive buffer and positive gap -> min(B / gap, 120)
    # B = 10000, gap = 2000 -> 10000 / 2000 = 5.0 months
    res4 = calculate_judge_runway(buffer=10000.0, income_after_shock=3000, spending_after_shock=5000, one_off_costs=0.0)
    assert res4["runway"] == 5.0
    assert res4["runway_label"] == "5.0 months"

    # Edge Case 5: Cap at 120 months
    # B = 50000, gap = 100 -> 500 months -> capped at 120.0
    res5 = calculate_judge_runway(buffer=50000.0, income_after_shock=4900, spending_after_shock=5000, one_off_costs=0.0)
    assert res5["runway"] == 120.0

def test_official_presets_simulation():
    # Setup test baseline customer
    baseline = BaselineMetrics(
        account_id=12345,
        I=10000.0,
        F=2500.0,
        S=8000.0,
        B=20000.0,
        H=1500.0,
        P=500.0,
        gap=-2000.0,
        baseline_runway=120.0,
        baseline_runway_label="no shortfall (120+)",
        history_months=36,
        has_running_loan=True,
        last_6_months_summary=pd.DataFrame(),
        is_in_deficit=False,
        buffer_exhausted=False,
        cash_inflow_ratio=0.5,
        cash_outflow_ratio=0.7,
        months_with_overdraft=0,
        total_bank_fees=50.0
    )

    # Twist 1: Job Loss (EI 55%)
    # income_after = 0.55 * 10000 = 5500. S = 8000. gap = 2500. buffer = 20000. runway = 20000/2500 = 8.0
    s1 = PRESET_DICT["JOB_LOSS_EI_55"]
    res_s1 = simulate_shock(baseline, s1)
    assert res_s1.income_after_shock == 5500.0
    assert res_s1.spending_after_shock == 8000.0
    assert res_s1.monthly_gap == 2500.0
    assert res_s1.runway_months == 8.0

    # Twist 2: Furnace Repair (one off = S = 8000)
    # buffer_left = 20000 - 8000 = 12000. gap = 8000 - 10000 = -2000 (no shortfall) -> runway 120.0
    s2 = PRESET_DICT["FURNACE_REPAIR"]
    res_s2 = simulate_shock(baseline, s2)
    assert res_s2.one_off_costs == 8000.0
    assert res_s2.buffer_left == 12000.0
    assert res_s2.runway_months == 120.0

    # Twist 3: Combined Shock (EI 55% + Bills +15%)
    # income = 5500. spending = 8000 + 0.15 * 1500 = 8000 + 225 = 8225.
    # gap = 8225 - 5500 = 2725.
    # runway = 20000 / 2725 = 7.339 -> 7.3 months
    s3 = PRESET_DICT["COMBINED_SHOCK"]
    res_s3 = simulate_shock(baseline, s3)
    assert res_s3.income_after_shock == 5500.0
    assert res_s3.spending_after_shock == 8225.0
    assert res_s3.monthly_gap == 2725.0
    assert res_s3.runway_months == 7.3


def test_what_if_timeline_reaches_the_calculated_runway():
    baseline = BaselineMetrics(
        account_id=12345,
        I=10000.0,
        F=2500.0,
        S=8000.0,
        B=20000.0,
        H=1500.0,
        P=500.0,
        gap=-2000.0,
        baseline_runway=120.0,
        baseline_runway_label="no shortfall (120+)",
        history_months=36,
        has_running_loan=True,
        last_6_months_summary=pd.DataFrame(),
        is_in_deficit=False,
        buffer_exhausted=False,
        cash_inflow_ratio=0.5,
        cash_outflow_ratio=0.7,
        months_with_overdraft=0,
        total_bank_fees=50.0,
    )
    shock = simulate_shock(baseline, PRESET_DICT["JOB_LOSS_EI_55"])
    duration = _timeline_duration(shock, no_shortfall_duration=6)
    projection = project_shock_timeline(
        baseline, shock, duration_months=duration, adaptive_mode=False
    )
    adjusted_projection = project_shock_timeline(
        baseline, shock, duration_months=duration, adaptive_mode=True
    )

    assert shock.runway_months == 8.0
    assert duration == 8
    fig, runway, depletion_step = _timeline_figure(
        baseline, shock, projection, adjusted_projection, frame=duration
    )
    assert runway == 8.0
    assert depletion_step == 8
    assert fig.data[0].x[-1] == "Challenge runway · 8.0 mo"
    assert fig.data[0].y[-1] == 0.0


def test_what_if_timeline_uses_preview_duration_when_there_is_no_gap():
    baseline = BaselineMetrics(
        account_id=12345,
        I=10000.0,
        F=2500.0,
        S=8000.0,
        B=20000.0,
        H=1500.0,
        P=500.0,
        gap=-2000.0,
        baseline_runway=120.0,
        baseline_runway_label="no shortfall (120+)",
        history_months=36,
        has_running_loan=True,
        last_6_months_summary=pd.DataFrame(),
        is_in_deficit=False,
        buffer_exhausted=False,
        cash_inflow_ratio=0.5,
        cash_outflow_ratio=0.7,
        months_with_overdraft=0,
        total_bank_fees=50.0,
    )
    shock = simulate_shock(baseline, PRESET_DICT["BASELINE"])
    assert _timeline_duration(shock, no_shortfall_duration=6) == 6

if __name__ == "__main__":
    test_runway_edge_cases()
    test_official_presets_simulation()
    print("Shock engine unit tests passed successfully!")
