"""
Population Discovery & Pre-Loan Early Warning Analytics Engine
Provides validated portfolio evidence, scenario distributions, and risk cohorts.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from src.data.local_repository import LocalDataRepository

@dataclass
class PopulationSummary:
    total_accounts: int
    median_I: float
    median_S: float
    median_F: float
    median_H: float
    median_B: float
    accounts_in_deficit: int
    pct_in_deficit: float
    accounts_with_negative_buffer: int
    total_loans: int
    active_loans_end_2025: int
    defaulted_loans: int
    portfolio_default_rate: float

def get_population_summary(repo: Optional[LocalDataRepository] = None) -> PopulationSummary:
    """Computes exact portfolio-wide baseline metrics."""
    if repo is None:
        repo = LocalDataRepository.get_instance()

    ms = repo.monthly_summary
    loans = repo.loans

    ms_sorted = ms.sort_values(["account_id", "month"])
    
    # Account level medians
    acc_medians = ms_sorted.groupby("account_id").agg(
        I=("money_in", "median"),
        S=("money_out", "median"),
        F=("fixed_costs_row", "median"),
        H=("household_bills", "median")
    )
    
    # 6-row buffers
    last6 = ms_sorted.groupby("account_id").tail(6)
    buffers = last6.groupby("account_id")["avg_daily_balance"].mean().rename("B")
    
    acc_medians = acc_medians.join(buffers)
    
    total_accs = len(acc_medians)
    deficit_count = int((acc_medians["S"] > acc_medians["I"]).sum())
    neg_b_count = int((acc_medians["B"] <= 0).sum())

    total_loans = len(loans)
    active_loans = int(loans["status"].isin(["C", "D"]).sum())
    defaults = int(loans["defaulted"].sum())
    default_rate = round((defaults / total_loans) * 100, 2)

    return PopulationSummary(
        total_accounts=total_accs,
        median_I=round(float(acc_medians["I"].median()), 2),
        median_S=round(float(acc_medians["S"].median()), 2),
        median_F=round(float(acc_medians["F"].median()), 2),
        median_H=round(float(acc_medians["H"].median()), 2),
        median_B=round(float(acc_medians["B"].median()), 2),
        accounts_in_deficit=deficit_count,
        pct_in_deficit=round((deficit_count / total_accs) * 100, 1),
        accounts_with_negative_buffer=neg_b_count,
        total_loans=total_loans,
        active_loans_end_2025=active_loans,
        defaulted_loans=defaults,
        portfolio_default_rate=default_rate
    )

def get_population_scenario_distributions(repo: Optional[LocalDataRepository] = None) -> pd.DataFrame:
    """
    Computes exact portfolio runway distributions across official scenarios:
    1. Baseline
    2. EI 55%
    3. Furnace Repair (S)
    4. Combined (EI 55% + 15% Bills)
    """
    if repo is None:
        repo = LocalDataRepository.get_instance()

    ms = repo.monthly_summary
    ms_sorted = ms.sort_values(["account_id", "month"])
    
    acc_medians = ms_sorted.groupby("account_id").agg(
        I=("money_in", "median"),
        S=("money_out", "median"),
        H=("household_bills", "median")
    )
    last6 = ms_sorted.groupby("account_id").tail(6)
    buffers = last6.groupby("account_id")["avg_daily_balance"].mean().rename("B")
    df = acc_medians.join(buffers)

    def calc_rw(b_left, gap):
        if b_left <= 0:
            return 0.0
        elif gap <= 0:
            return 120.0
        else:
            return round(min(b_left / gap, 120.0), 1)

    # 1. Baseline
    rw_base = [calc_rw(b, s - i) for b, s, i in zip(df["B"], df["S"], df["I"])]
    # 2. EI 55%
    rw_ei = [calc_rw(b, s - 0.55 * i) for b, s, i in zip(df["B"], df["S"], df["I"])]
    # 3. Furnace Repair (one off = S)
    rw_repair = [calc_rw(b - s, s - i) for b, s, i in zip(df["B"], df["S"], df["I"])]
    # 4. Combined
    rw_comb = [calc_rw(b, (s + 0.15 * h) - 0.55 * i) for b, s, h, i in zip(df["B"], df["S"], df["H"], df["I"])]

    df["rw_base"] = rw_base
    df["rw_ei"] = rw_ei
    df["rw_repair"] = rw_repair
    df["rw_comb"] = rw_comb

    scenarios = [
        {"Scenario": "Baseline (Status Quo)", "Below 3M": (df["rw_base"] < 3.0).sum(), "Below 6M": (df["rw_base"] < 6.0).sum(), "Below 12M": (df["rw_base"] < 12.0).sum()},
        {"Scenario": "Job Loss (EI @ 55%)", "Below 3M": (df["rw_ei"] < 3.0).sum(), "Below 6M": (df["rw_ei"] < 6.0).sum(), "Below 12M": (df["rw_ei"] < 12.0).sum()},
        {"Scenario": "Emergency Repair (Cost = S)", "Below 3M": (df["rw_repair"] < 3.0).sum(), "Below 6M": (df["rw_repair"] < 6.0).sum(), "Below 12M": (df["rw_repair"] < 12.0).sum()},
        {"Scenario": "Combined Shock (EI 55% + Bills +15%)", "Below 3M": (df["rw_comb"] < 3.0).sum(), "Below 6M": (df["rw_comb"] < 6.0).sum(), "Below 12M": (df["rw_comb"] < 12.0).sum()}
    ]

    res = pd.DataFrame(scenarios)
    tot = len(df)
    res["Below 3M (%)"] = (res["Below 3M"] / tot * 100).round(1)
    res["Below 6M (%)"] = (res["Below 6M"] / tot * 100).round(1)
    res["Below 12M (%)"] = (res["Below 12M"] / tot * 100).round(1)
    return res

def get_preloan_early_warning_data(repo: Optional[LocalDataRepository] = None) -> Dict[str, Any]:
    """
    Computes pre-origination loan risk evidence using strictly pre-loan history.
    615 accounts with >= 6 complete months before loan_start.
    """
    if repo is None:
        repo = LocalDataRepository.get_instance()

    loans = repo.loans.copy()
    ms = repo.monthly_summary.copy()
    loans["loan_start_month"] = loans["loan_start"].str.slice(0, 7)

    cohort = []
    for _, row in loans.iterrows():
        acc_id = row["account_id"]
        start_m = row["loan_start_month"]
        pre_rows = ms[(ms["account_id"] == acc_id) & (ms["month"] < start_m)].sort_values("month")
        if len(pre_rows) >= 6:
            last6 = pre_rows.tail(6)
            pre_b = last6["avg_daily_balance"].mean()
            pre_in_med = last6["money_in"].median()
            in_mean = last6["money_in"].mean()
            in_std = last6["money_in"].std()
            cv = in_std / (in_mean + 1e-6)
            had_neg = (last6["days_below_zero"] > 0).any()
            cohort.append({
                "account_id": acc_id,
                "loan_id": row["loan_id"],
                "status": row["status"],
                "defaulted": row["defaulted"],
                "amount": row["amount"],
                "pre_buffer": pre_b,
                "pre_money_in": pre_in_med,
                "pre_in_cv": cv,
                "had_pre_overdraft": had_neg
            })

    cdf = pd.DataFrame(cohort)
    cdf["buffer_quartile"] = pd.qcut(cdf["pre_buffer"], 4, labels=["Q1 (Lowest Buffer)", "Q2", "Q3", "Q4 (Highest Buffer)"])
    
    q_summary = cdf.groupby("buffer_quartile", observed=False).agg(
        total_loans=("loan_id", "count"),
        defaults=("defaulted", "sum"),
        default_rate=("defaulted", lambda s: round(s.mean() * 100, 2)),
        median_buffer=("pre_buffer", "median")
    ).reset_index()

    # Pre-loan overdraft contingency
    od_summary = cdf.groupby("had_pre_overdraft").agg(
        total=("loan_id", "count"),
        defaults=("defaulted", "sum"),
        default_rate=("defaulted", lambda s: round(s.mean() * 100, 2))
    ).reset_index()

    return {
        "cohort_size": len(cdf),
        "quartile_summary": q_summary,
        "overdraft_summary": od_summary,
        "default_median_volatility": round(float(cdf[cdf["defaulted"] == 1]["pre_in_cv"].median()), 3),
        "healthy_median_volatility": round(float(cdf[cdf["defaulted"] == 0]["pre_in_cv"].median()), 3)
    }
