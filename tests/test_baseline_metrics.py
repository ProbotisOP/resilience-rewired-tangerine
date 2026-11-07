"""
Unit tests for deterministic official baseline metrics.
"""

import pytest
import pandas as pd
import numpy as np

from src.services.baseline_metrics import compute_official_baseline

def test_baseline_formulas():
    # Construct synthetic monthly summary with known properties
    # 8 months of data
    data = {
        "account_id": [99999] * 8,
        "month": [f"2025-0{i}" for i in range(1, 9)],
        "money_in": [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000],  # Median = (4000+5000)/2 = 4500
        "money_out": [800, 900, 1000, 1100, 1200, 1300, 1400, 1500],  # Median = 1150
        "household_bills": [200, 200, 250, 250, 300, 300, 350, 350],  # Median = 275
        "insurance": [50, 50, 50, 50, 50, 50, 50, 50],
        "loan_payments": [100, 100, 100, 100, 100, 100, 100, 100],
        "cash_deposits": [500] * 8,
        "cash_withdrawals_genuine": [600] * 8,
        "days_below_zero": [0] * 8,
        "bank_fees": [10] * 8,
        "avg_daily_balance": [10000, 11000, 12000, 13000, 14000, 15000, 16000, 17000]
    }
    df = pd.DataFrame(data)
    
    # Active running loan
    loan_dict = {
        "has_loan": True,
        "loan_status": "C",
        "loan_monthly_payment": 100.0
    }

    metrics = compute_official_baseline(99999, df, loan_dict)

    # 1. I is median
    assert metrics.I == 4500.0

    # 2. S is median
    assert metrics.S == 1150.0

    # 3. F is row-wise sum first, then median
    # Row sums: bills + ins + loan = [350, 350, 400, 400, 450, 450, 500, 500]
    # Median of row sums = (400 + 450)/2 = 425.0
    assert metrics.F == 425.0

    # 4. H is median
    assert metrics.H == 275.0

    # 5. Buffer (B) is mean of exactly the last 6 rows:
    # Last 6 rows avg_daily_balance: [12000, 13000, 14000, 15000, 16000, 17000]
    # Mean = 87000 / 6 = 14500.0
    assert metrics.B == 14500.0

    # 6. Active Loan P
    assert metrics.P == 100.0

    # 7. Gap and runway
    # S < I -> gap = 1150 - 4500 = -3350 -> no shortfall
    assert metrics.gap == -3350.0
    assert metrics.baseline_runway == 120.0
    assert "no shortfall" in metrics.baseline_runway_label

def test_repaid_loan_p_is_zero():
    df = pd.DataFrame({
        "account_id": [88888] * 6,
        "month": [f"2025-0{i}" for i in range(1, 7)],
        "money_in": [5000] * 6,
        "money_out": [4000] * 6,
        "household_bills": [500] * 6,
        "insurance": [100] * 6,
        "loan_payments": [200] * 6,
        "cash_deposits": [2000] * 6,
        "cash_withdrawals_genuine": [2000] * 6,
        "days_below_zero": [0] * 6,
        "bank_fees": [5] * 6,
        "avg_daily_balance": [10000] * 6
    })
    # Status A (finished, repaid) -> P must be 0.0
    loan_dict = {
        "has_loan": True,
        "loan_status": "A",
        "loan_monthly_payment": 200.0
    }
    metrics = compute_official_baseline(88888, df, loan_dict)
    assert metrics.P == 0.0
    assert metrics.has_running_loan is False

if __name__ == "__main__":
    test_baseline_formulas()
    test_repaid_loan_p_is_zero()
    print("Baseline unit tests passed successfully!")
