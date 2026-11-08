"""Tests for explicit reserve assumptions and the deterministic gap optimizer."""

import pandas as pd
import pytest

from config.scenarios import PRESET_DICT
from src.services.baseline_metrics import BaselineMetrics
from src.services.recovery_planner import (
    build_backup_plan,
    build_goal_plan,
    build_resilience_gap_plan,
)
from src.services.shock_engine import simulate_shock


def make_baseline(
    *,
    fixed_costs=2000.0,
    buffer=5000.0,
    income=6000.0,
    spending=5000.0,
    running_loan=False,
):
    recent = pd.DataFrame(
        {
            "money_in": [6100, 6200, 5800, 6000, 6300, 5900],
            "money_out": [5000, 5100, 5200, 4900, 5150, 5000],
        }
    )
    return BaselineMetrics(
        account_id=77777,
        I=income,
        F=fixed_costs,
        S=spending,
        B=buffer,
        H=1000.0,
        P=500.0 if running_loan else 0.0,
        gap=spending - income,
        baseline_runway=120.0,
        baseline_runway_label="no shortfall (120+)",
        history_months=36,
        has_running_loan=running_loan,
        last_6_months_summary=recent,
        is_in_deficit=spending > income,
        buffer_exhausted=buffer <= 0,
        cash_inflow_ratio=0.4,
        cash_outflow_ratio=0.6,
        months_with_overdraft=0,
        total_bank_fees=0.0,
    )


def test_goal_plan_uses_recent_net_cash_flow_and_customer_assumptions():
    baseline = make_baseline()
    goal = build_goal_plan(
        baseline,
        target_months=3,
        custom_monthly_savings=400.0,
    )
    assert goal.essential_monthly_cost == 2000.0
    assert goal.emergency_target == 6000.0
    assert goal.funding_gap == 1000.0
    assert goal.recent_six_month_median_net_cash_flow == 1100.0
    assert goal.recommended_monthly_deposit == 400.0
    assert goal.months_to_goal == 3


def test_goal_plan_does_not_invent_missing_fixed_costs():
    goal = build_goal_plan(make_baseline(fixed_costs=0.0))
    assert goal.is_f_unobserved is True
    assert goal.essential_monthly_cost is None
    assert goal.emergency_target is None
    assert goal.months_to_goal is None

    confirmed = build_goal_plan(
        make_baseline(fixed_costs=0.0),
        essential_monthly_cost=1200.0,
        custom_monthly_savings=0.0,
    )
    assert confirmed.emergency_target == 3600.0
    assert confirmed.months_to_goal == 0


def test_resilience_gap_optimizer_calculates_selected_duration_and_adjustment():
    plan = build_resilience_gap_plan(
        buffer=6000.0,
        monthly_gap=2000.0,
        target_months=6,
        selected_monthly_adjustment=1200.0,
    )
    assert plan.required_monthly_improvement == 1000.0
    assert plan.proposed_monthly_gap == 800.0
    assert plan.current_runway_months == 3.0
    assert plan.proposed_runway_months == 7.5


def test_optimizer_validates_inputs():
    with pytest.raises(ValueError):
        build_resilience_gap_plan(1000, 500, 0)
    with pytest.raises(ValueError):
        build_resilience_gap_plan(1000, 500, 3, -1)


def test_backup_plan_separates_depleted_buffer_from_monthly_improvement():
    plan = build_resilience_gap_plan(
        buffer=-1500.0,
        monthly_gap=2000.0,
        target_months=6,
        selected_monthly_adjustment=1000.0,
    )
    assert plan.required_monthly_improvement == 2000.0
    assert plan.additional_buffer_needed == 7500.0
    assert plan.proposed_runway_months == 0.0


def test_backup_plan_does_not_assume_cash_is_discretionary_or_relief_is_approved():
    baseline = make_baseline(running_loan=True)
    shock = simulate_shock(baseline, PRESET_DICT["JOB_LOSS_EI_55"])
    backup = build_backup_plan(
        baseline,
        shock,
        {"has_leasing_labelled_order": True, "standing_orders_total": 5000.0, "loan_id": 101},
    )
    assert len(backup.actions) == 2
    assert all(action.monthly_dollar_impact == 0 for action in backup.actions)
    assert backup.total_mitigation_capacity == 0
    assert backup.post_mitigation_gap == backup.monthly_shortfall
    assert "not proof" in backup.actions[0].description
    assert "No deferral" in backup.actions[1].description
