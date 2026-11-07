"""
Deterministic Baseline Metrics Engine
Strictly adheres to Tangerine Sheridan Datathon 2026 specifications.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd

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


@dataclass
class PortfolioStatistics:
    total_accounts: int
    median_I: float
    median_S: float
    median_F: float
    median_H: float
    median_B: float
    accounts_in_deficit: int
    pct_in_deficit: float
    accounts_with_negative_buffer: int


def calculate_runway(buffer: float, gap: float) -> float:
    """Return the one-decimal official Judge Match runway, capped at 120 months."""
    if buffer <= 0:
        return 0.0
    if gap <= 0:
        return 120.0
    return round(min(buffer / gap, 120.0), 1)


def calculate_runway_details(
    buffer: float,
    income_after_shock: float,
    spending_after_shock: float,
    one_off_costs: float = 0.0,
) -> Dict[str, Any]:
    """Apply shared cent rounding and return the official runway values and label."""
    buffer_left = round(buffer - one_off_costs, 2)
    gap = round(spending_after_shock - income_after_shock, 2)
    runway = calculate_runway(buffer_left, gap)
    if buffer_left <= 0:
        label = "0.0 (Buffer Exhausted)"
    elif gap <= 0:
        label = "no shortfall (120+)"
    else:
        label = f"{runway:.1f} months"
    return {
        "buffer_left": buffer_left,
        "gap": gap,
        "runway": runway,
        "runway_label": label,
    }


def compute_portfolio_account_metrics(monthly_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate unrounded account-level I/F/S/H/B metrics from monthly rows."""
    if monthly_df.empty:
        raise ValueError("No monthly summary data found")

    ordered = monthly_df.sort_values(["account_id", "month"]).copy()
    if "fixed_costs_row" not in ordered:
        ordered["fixed_costs_row"] = (
            ordered["household_bills"] + ordered["insurance"] + ordered["loan_payments"]
        )
    grouped = ordered.groupby("account_id", sort=True)
    metrics = grouped.agg(
        I=("money_in", "median"),
        S=("money_out", "median"),
        F=("fixed_costs_row", "median"),
        H=("household_bills", "median"),
        total_money_in=("money_in", "sum"),
        total_money_out=("money_out", "sum"),
        total_cash_deposits=("cash_deposits", "sum"),
        total_cash_withdrawals=("cash_withdrawals_genuine", "sum"),
        total_bank_fees=("bank_fees", "sum"),
        months_with_overdraft=("days_below_zero", lambda values: int((values > 0).sum())),
        history_months=("month", "count"),
    )
    last_six = grouped.tail(6)
    buffers = last_six.groupby("account_id")["avg_daily_balance"].mean().rename("B")
    metrics = metrics.join(buffers)
    metrics["gap"] = metrics["S"].round(2) - metrics["I"].round(2)
    metrics["baseline_runway"] = [
        calculate_runway_details(
            round(buffer, 2), round(income, 2), round(spending, 2)
        )[
            "runway"
        ]
        for buffer, income, spending in zip(metrics["B"], metrics["I"], metrics["S"])
    ]
    metrics["cash_inflow_ratio"] = metrics["total_cash_deposits"] / (
        metrics["total_money_in"] + 1e-6
    )
    metrics["cash_outflow_ratio"] = metrics["total_cash_withdrawals"] / (
        metrics["total_money_out"] + 1e-6
    )
    return metrics


def compute_portfolio_statistics(monthly_df: pd.DataFrame) -> PortfolioStatistics:
    """Summarize account-level baseline metrics; this is the portfolio source of truth."""
    account_metrics = compute_portfolio_account_metrics(monthly_df)
    return summarize_portfolio_account_metrics(account_metrics)


def summarize_portfolio_account_metrics(
    account_metrics: pd.DataFrame,
) -> PortfolioStatistics:
    """Summarize an already calculated shared account-metric table."""
    total_accounts = len(account_metrics)
    deficit_count = int((account_metrics["gap"] > 0).sum())
    return PortfolioStatistics(
        total_accounts=total_accounts,
        median_I=round(float(account_metrics["I"].median()), 2),
        median_S=round(float(account_metrics["S"].median()), 2),
        median_F=round(float(account_metrics["F"].median()), 2),
        median_H=round(float(account_metrics["H"].median()), 2),
        median_B=round(float(account_metrics["B"].median()), 2),
        accounts_in_deficit=deficit_count,
        pct_in_deficit=round(deficit_count / total_accounts * 100, 1),
        accounts_with_negative_buffer=int((account_metrics["B"] <= 0).sum()),
    )


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

    account_metrics = compute_portfolio_account_metrics(monthly_df)
    if account_id not in account_metrics.index:
        raise ValueError(f"No monthly summary data found for account_id {account_id}")
    values = account_metrics.loc[account_id]
    monthly_sorted = monthly_df.sort_values("month").copy()
    last_6_df = monthly_sorted.tail(6)
    I, F, S, H, B = (float(values[key]) for key in ("I", "F", "S", "H", "B"))
    history_len = int(values["history_months"])

    # 6. Active Loan Payment (P)
    P = 0.0
    has_running = False
    if loan_dict and loan_dict.get("has_loan"):
        # Running at end of 2025 if status is 'C' or 'D'
        if loan_dict.get("loan_status") in ["C", "D"]:
            P = float(loan_dict.get("loan_monthly_payment", 0.0))
            has_running = True

    # 7. Baseline Gap & Runway
    gap = float(values["gap"])
    runway = float(values["baseline_runway"])
    runway_label = (
        "0.0 (Buffer Depleted)"
        if B <= 0
        else "no shortfall (120+)"
        if gap <= 0
        else f"{runway:.1f} months"
    )

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
        cash_inflow_ratio=round(float(values["cash_inflow_ratio"]), 3),
        cash_outflow_ratio=round(float(values["cash_outflow_ratio"]), 3),
        months_with_overdraft=int(values["months_with_overdraft"]),
        total_bank_fees=round(float(values["total_bank_fees"]), 2)
    )
