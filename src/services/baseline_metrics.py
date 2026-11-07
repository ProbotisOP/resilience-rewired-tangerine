"""
Deterministic Baseline Metrics Engine
Strictly adheres to Tangerine Sheridan Datathon 2026 specifications.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

@dataclass
class BaselineMetrics:
    account_id: int
    I: float  # Typical monthly money in
    F: float  # Typical fixed costs
    S: float  # Typical monthly spending
    B: float  # Buffer (mean avg_daily_balance over last 6 months)
    H: float  # Household bills
    P: float  # Active loan payment (status C or D)
    gap: float  # S - I
    baseline_runway: float  # Numeric value (capped at 120.0)
    baseline_runway_label: str  # Display string (e.g. "no shortfall (120+)")
    history_months: int
    has_running_loan: bool
    last_6_months_summary: pd.DataFrame
    
    # Financial health indicators
    is_in_deficit: bool
    buffer_exhausted: bool
    cash_inflow_ratio: float
    cash_outflow_ratio: float
    months_with_overdraft: int
    total_bank_fees: float

def compute_official_baseline(account_id: int, monthly_df: pd.DataFrame, loan_dict: Optional[Dict[str, Any]] = None) -> BaselineMetrics:
    """
    Computes exact official metrics for any customer account:
    - Typical monthly money in (I) = median(money_in)
    - Typical fixed costs (F) = median(household_bills + insurance + loan_payments)
    - Typical monthly spending (S) = median(money_out)
    - Buffer (B) = mean(avg_daily_balance) over last 6 chronological rows
    - Household bills (H) = median(household_bills)
    - Loan payment (P) = monthly_payment if loan running at end of 2025, else 0
    """
    if monthly_df.empty:
        raise ValueError(f"No monthly summary data found for account_id {account_id}")

    # Ensure chronological sort
    monthly_sorted = monthly_df.sort_values("month").copy()
    history_len = len(monthly_sorted)

    # 1. Typical monthly money in (I)
    I = float(monthly_sorted["money_in"].median())

    # 2. Typical fixed costs (F) - row-wise sum first, then median
    if "fixed_costs_row" not in monthly_sorted.columns:
        monthly_sorted["fixed_costs_row"] = (
            monthly_sorted["household_bills"] +
            monthly_sorted["insurance"] +
            monthly_sorted["loan_payments"]
        )
    F = float(monthly_sorted["fixed_costs_row"].median())

    # 3. Typical monthly spending (S)
    S = float(monthly_sorted["money_out"].median())

    # 4. Household bills (H)
    H = float(monthly_sorted["household_bills"].median())

    # 5. Buffer (B) - exactly last 6 chronological rows
    last_6_df = monthly_sorted.tail(6)
    B = float(last_6_df["avg_daily_balance"].mean())

    # 6. Active Loan Payment (P)
    P = 0.0
    has_running = False
    if loan_dict and loan_dict.get("has_loan"):
        # Running at end of 2025 if status is 'C' or 'D'
        if loan_dict.get("loan_status") in ["C", "D"]:
            P = float(loan_dict.get("loan_monthly_payment", 0.0))
            has_running = True

    # 7. Baseline Gap & Runway
    gap = S - I
    buffer_left = B

    if buffer_left <= 0:
        runway = 0.0
        runway_label = "0.0 (Buffer Depleted)"
    elif gap <= 0:
        runway = 120.0
        runway_label = "no shortfall (120+)"
    else:
        runway = round(min(buffer_left / gap, 120.0), 1)
        runway_label = f"{runway:.1f} months"

    # Additional diagnostic ratios
    tot_in = monthly_sorted["money_in"].sum()
    tot_out = monthly_sorted["money_out"].sum()
    cash_in_ratio = float(monthly_sorted["cash_deposits"].sum() / (tot_in + 1e-6))
    cash_out_ratio = float(monthly_sorted["cash_withdrawals_genuine"].sum() / (tot_out + 1e-6))
    months_overdraft = int((monthly_sorted["days_below_zero"] > 0).sum())
    total_fees = float(monthly_sorted["bank_fees"].sum())

    return BaselineMetrics(
        account_id=account_id,
        I=round(I, 2),
        F=round(F, 2),
        S=round(S, 2),
        B=round(B, 2),
        H=round(H, 2),
        P=round(P, 2),
        gap=round(gap, 2),
        baseline_runway=runway,
        baseline_runway_label=runway_label,
        history_months=history_len,
        has_running_loan=has_running,
        last_6_months_summary=last_6_df,
        is_in_deficit=(gap > 0),
        buffer_exhausted=(B <= 0),
        cash_inflow_ratio=round(cash_in_ratio, 3),
        cash_outflow_ratio=round(cash_out_ratio, 3),
        months_with_overdraft=months_overdraft,
        total_bank_fees=round(total_fees, 2)
    )
