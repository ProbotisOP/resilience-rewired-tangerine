"""
Unit tests for emergency fund goal plan and backup action plan.
"""

from src.services.baseline_metrics import BaselineMetrics
from src.services.shock_engine import simulate_shock
from src.services.recovery_planner import build_goal_plan, build_backup_plan
from config.scenarios import PRESET_DICT
import pandas as pd

def test_goal_plan():
    # Customer with F = 2000, B = 5000, I = 6000, S = 5000
    baseline = BaselineMetrics(
        account_id=77777,
        I=6000.0,
        F=2000.0,
        S=5000.0,
        B=5000.0,
        H=1000.0,
        P=0.0,
        gap=-1000.0,
        baseline_runway=120.0,
        baseline_runway_label="no shortfall (120+)",
        history_months=36,
        has_running_loan=False,
        last_6_months_summary=pd.DataFrame(),
        is_in_deficit=False,
        buffer_exhausted=False,
        cash_inflow_ratio=0.4,
        cash_outflow_ratio=0.6,
        months_with_overdraft=0,
        total_bank_fees=0.0
    )

    # 3-month target = 3 * 2000 = 6000. Funding gap = 6000 - 5000 = 1000.
    # Historical capacity = I - S = 1000. Months to goal = 1 month!
    goal = build_goal_plan(baseline, target_months=3)
    assert goal.emergency_target == 6000.0
    assert goal.funding_gap == 1000.0
    assert goal.is_target_met is False
    assert goal.historical_savings_capacity == 1000.0
    assert goal.months_to_goal == 1

def test_backup_plan():
    baseline = BaselineMetrics(
        account_id=77777,
        I=6000.0,
        F=2000.0,
        S=5000.0,
        B=5000.0,
        H=1000.0,
        P=500.0,
        gap=-1000.0,
        baseline_runway=120.0,
        baseline_runway_label="no shortfall (120+)",
        history_months=36,
        has_running_loan=True,
        last_6_months_summary=pd.DataFrame(),
        is_in_deficit=False,
        buffer_exhausted=False,
        cash_inflow_ratio=0.4,
        cash_outflow_ratio=0.6,
        months_with_overdraft=0,
        total_bank_fees=0.0
    )

    # Shock: EI 55% -> Income = 3300. Spending = 5000. Gap = 1700.
    shock_res = simulate_shock(baseline, PRESET_DICT["JOB_LOSS_EI_55"])
    assert shock_res.monthly_gap == 1700.0

    account_meta = {"has_loan": True, "loan_id": 101, "loan_monthly_payment": 500.0}
    backup = build_backup_plan(baseline, shock_res, account_meta)

    assert backup.monthly_shortfall == 1700.0
    assert len(backup.actions) > 0
    # First action should be discretionary cash compression
    assert "Cash Compression" in backup.actions[0].action_type

if __name__ == "__main__":
    test_goal_plan()
    test_backup_plan()
    print("Recovery planner unit tests passed successfully!")
