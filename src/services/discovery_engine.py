"""Reproducible portfolio calculations and descriptive discovery cohorts."""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import (
    summarize_portfolio_account_metrics,
    calculate_runway_details,
)


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


def _portfolio_metrics(repo: LocalDataRepository) -> pd.DataFrame:
    return repo.get_portfolio_account_metrics()


def get_population_summary(repo: Optional[LocalDataRepository] = None) -> PopulationSummary:
    """Return portfolio metrics using the account-baseline calculation source of truth."""
    repo = repo or LocalDataRepository.get_instance()
    stats = summarize_portfolio_account_metrics(_portfolio_metrics(repo))
    loans = repo.loans
    total_loans = len(loans)
    defaults = int(loans["defaulted"].sum())
    return PopulationSummary(
        total_accounts=stats.total_accounts,
        median_I=stats.median_I,
        median_S=stats.median_S,
        median_F=stats.median_F,
        median_H=stats.median_H,
        median_B=stats.median_B,
        accounts_in_deficit=stats.accounts_in_deficit,
        pct_in_deficit=stats.pct_in_deficit,
        accounts_with_negative_buffer=stats.accounts_with_negative_buffer,
        total_loans=total_loans,
        active_loans_end_2025=int(loans["status"].isin(["C", "D"]).sum()),
        defaulted_loans=defaults,
        portfolio_default_rate=round(defaults / total_loans * 100, 2),
    )


def get_population_scenario_distributions(
    repo: Optional[LocalDataRepository] = None,
) -> pd.DataFrame:
    """Count accounts below thresholds using one-decimal official runway values."""
    repo = repo or LocalDataRepository.get_instance()
    metrics = _portfolio_metrics(repo)
    cases = [
        ("Baseline (Status Quo)", 1.0, 0.0, 0.0),
        ("Job Loss (EI @ 55%)", 0.55, 0.0, 0.0),
        ("Emergency Repair (Cost = S)", 1.0, 0.0, 1.0),
        ("Combined Shock (EI 55% + Bills +15%)", 0.55, 0.15, 0.0),
    ]
    rows = []
    denominator = len(metrics)
    for label, income_multiplier, bill_increase, one_off_multiplier in cases:
        runways = _scenario_runways(
            metrics, income_multiplier, bill_increase, one_off_multiplier
        )
        row: Dict[str, Any] = {"Scenario": label, "Accounts": denominator}
        for threshold in (3, 6, 12):
            count = int((runways < threshold).sum())
            row[f"Below {threshold}M"] = count
            row[f"Below {threshold}M (%)"] = round(count / denominator * 100, 1)
        rows.append(row)
    return pd.DataFrame(rows)


def _scenario_runways(
    metrics: pd.DataFrame,
    income_multiplier: float,
    household_bill_change: float,
    one_off_spend_multiplier: float,
) -> np.ndarray:
    """Apply the shared deterministic shock/runway formula to account metrics."""
    return np.array(
        [
            calculate_runway_details(
                round(buffer, 2),
                round(income_multiplier * round(income, 2), 2),
                round(round(spending, 2) + household_bill_change * round(bills, 2), 2),
                round(one_off_spend_multiplier * round(spending, 2), 2),
            )["runway"]
            for buffer, income, spending, bills in zip(
                metrics["B"], metrics["I"], metrics["S"], metrics["H"]
            )
        ],
        dtype=float,
    )


def get_portfolio_scenario_runways(
    repo: Optional[LocalDataRepository] = None,
    *,
    income_multiplier: float,
    household_bill_change: float = 0.0,
    one_off_spend_multiplier: float = 0.0,
) -> pd.DataFrame:
    """Return one-decimal scenario runway per account for interactive portfolio what-ifs."""
    if income_multiplier < 0:
        raise ValueError("income_multiplier cannot be negative")
    if household_bill_change < -1:
        raise ValueError("household_bill_change cannot reduce bills below zero")
    if one_off_spend_multiplier < 0:
        raise ValueError("one_off_spend_multiplier cannot be negative")

    repo = repo or LocalDataRepository.get_instance()
    metrics = _portfolio_metrics(repo)
    return pd.DataFrame(
        {
            "account_id": metrics.index,
            "runway_months": _scenario_runways(
                metrics,
                income_multiplier,
                household_bill_change,
                one_off_spend_multiplier,
            ),
        }
    )


def get_income_decile_discovery(
    repo: Optional[LocalDataRepository] = None,
) -> pd.DataFrame:
    """Calculate EI-55% simulated runway results for current account-income deciles."""
    repo = repo or LocalDataRepository.get_instance()
    metrics = _portfolio_metrics(repo)
    decile = pd.qcut(
        metrics["I"],
        10,
        labels=[f"D{i}" for i in range(1, 11)],
        duplicates="drop",
    )
    runways = _scenario_runways(
        metrics,
        income_multiplier=0.55,
        household_bill_change=0.0,
        one_off_spend_multiplier=0.0,
    )
    data = pd.DataFrame(
        {
            "Income Decile": decile,
            "Income": metrics["I"].to_numpy(),
            "Judge Match Runway": runways,
        }
    )
    data["Below 6 Months"] = data["Judge Match Runway"] < 6
    return (
        data.groupby("Income Decile", observed=False)
        .agg(
            Accounts=("Income", "size"),
            **{
                "Median Income": ("Income", "median"),
                "Median Runway (EI 55%)": ("Judge Match Runway", "median"),
                "Accounts Below 6 Months": ("Below 6 Months", "sum"),
                "% Below 6 Months": (
                    "Below 6 Months",
                    lambda values: round(values.mean() * 100, 1),
                ),
            },
        )
        .reset_index()
    )


def get_behavioral_association_tables(
    repo: Optional[LocalDataRepository] = None,
) -> Dict[str, pd.DataFrame]:
    """Return denominator-explicit account/loan associations without causal claims."""
    repo = repo or LocalDataRepository.get_instance()
    metrics = _portfolio_metrics(repo)
    accounts = repo.accounts.set_index("account_id")[["frequency"]].join(metrics)

    authorized_ids = set(
        repo.dispositions.loc[
            repo.dispositions["type"] == "authorized user", "account_id"
        ]
    )
    owner_disp = repo.dispositions.loc[
        repo.dispositions["type"] == "owner", ["account_id", "disposition_id"]
    ]
    card_ids = set(
        repo.cards.merge(owner_disp, on="disposition_id")["account_id"]
    )
    leases = repo.standing_orders.loc[
        repo.standing_orders["purpose"] == "leasing", "account_id"
    ]
    loan_outcomes = repo.loans.set_index("account_id")[["defaulted"]]
    accounts["has_authorized_user"] = accounts.index.isin(authorized_ids)
    accounts["has_card"] = accounts.index.isin(card_ids)
    accounts["has_leasing_order"] = accounts.index.isin(set(leases))
    accounts = accounts.join(loan_outcomes)
    accounts["defaulted"] = accounts["defaulted"].fillna(0).astype(int)
    accounts["has_loan"] = accounts.index.isin(repo.loans["account_id"])
    accounts["had_negative_balance_days"] = accounts["months_with_overdraft"] > 0

    tables: Dict[str, pd.DataFrame] = {}
    for label, feature in (
        ("authorized_user", "has_authorized_user"),
        ("statement_frequency", "frequency"),
        ("card", "has_card"),
        ("leasing_order", "has_leasing_order"),
    ):
        tables[label] = (
            accounts.groupby(feature, dropna=False)
            .agg(
                accounts=("I", "size"),
                accounts_with_negative_balance_days=("had_negative_balance_days", "sum"),
                loans=("has_loan", "sum"),
                defaults=("defaulted", "sum"),
            )
            .reset_index()
        )
        tables[label]["negative_balance_account_rate_pct"] = (
            tables[label]["accounts_with_negative_balance_days"]
            / tables[label]["accounts"]
            * 100
        )
        tables[label]["loan_default_rate_pct"] = (
            tables[label]["defaults"]
            / tables[label]["loans"].where(tables[label]["loans"] > 0)
            * 100
        )
    borrower_accounts = accounts.loc[accounts["has_loan"]].copy()
    borrower_accounts["cash_deposit_reliance_quartile"] = pd.qcut(
        borrower_accounts["cash_inflow_ratio"],
        4,
        labels=["Q1 (Lowest)", "Q2", "Q3", "Q4 (Highest)"],
        duplicates="drop",
    )
    tables["cash_deposit_reliance"] = (
        borrower_accounts.groupby("cash_deposit_reliance_quartile", observed=False)
        .agg(
            loans=("defaulted", "size"),
            defaults=("defaulted", "sum"),
            median_cash_deposit_share=("cash_inflow_ratio", "median"),
        )
        .reset_index()
    )
    tables["cash_deposit_reliance"]["default_rate_pct"] = (
        tables["cash_deposit_reliance"]["defaults"]
        / tables["cash_deposit_reliance"]["loans"]
        * 100
    )

    loan_instruction_rows = repo.standing_orders[
        repo.standing_orders["purpose"] == "loan payment"
    ]
    internal_loan_accounts = set(repo.loans["account_id"])
    tables["external_destination_instructions"] = pd.DataFrame(
        [
            {
                "standing_order_rows": len(loan_instruction_rows),
                "accounts_with_instruction": loan_instruction_rows["account_id"].nunique(),
                "accounts_without_internal_loan": loan_instruction_rows.loc[
                    ~loan_instruction_rows["account_id"].isin(internal_loan_accounts),
                    "account_id",
                ].nunique(),
            }
        ]
    )
    return tables


def get_preloan_early_warning_data(
    repo: Optional[LocalDataRepository] = None,
) -> Dict[str, Any]:
    """Describe loan outcomes by the latest six available pre-origination months."""
    repo = repo or LocalDataRepository.get_instance()
    cached = repo._analysis_cache.get("preloan_early_warning")
    if cached is not None:
        return {
            key: value.copy() if isinstance(value, pd.DataFrame) else value
            for key, value in cached.items()
        }

    loans = repo.loans.copy()
    ms = repo.monthly_summary
    loans["loan_start_month"] = loans["loan_start"].astype(str).str.slice(0, 7)
    monthly_by_account = {
        account_id: rows.sort_values("month")
        for account_id, rows in ms.groupby("account_id", sort=False)
    }

    cohort: List[Dict[str, Any]] = []
    for _, loan in loans.iterrows():
        account_rows = monthly_by_account.get(loan["account_id"])
        if account_rows is None:
            continue
        pre_rows = account_rows[account_rows["month"] < loan["loan_start_month"]]
        if len(pre_rows) < 6:
            continue
        last_six = pre_rows.tail(6)
        mean_in = last_six["money_in"].mean()
        cohort.append(
            {
                "account_id": loan["account_id"],
                "loan_id": loan["loan_id"],
                "status": loan["status"],
                "defaulted": int(loan["defaulted"]),
                "pre_buffer": last_six["avg_daily_balance"].mean(),
                "pre_in_cv": last_six["money_in"].std() / (mean_in + 1e-6),
                "had_pre_overdraft": bool((last_six["days_below_zero"] > 0).any()),
                "window_start": last_six["month"].iloc[0],
                "window_end": last_six["month"].iloc[-1],
            }
        )

    cohort_df = pd.DataFrame(cohort)
    if cohort_df.empty:
        empty = pd.DataFrame()
        result = {
            "cohort_size": 0,
            "window_months": 6,
            "quartile_summary": empty,
            "overdraft_summary": empty,
            "default_median_volatility": None,
            "healthy_median_volatility": None,
        }
        repo._analysis_cache["preloan_early_warning"] = result
        return result

    cohort_df["buffer_quartile"] = pd.qcut(
        cohort_df["pre_buffer"],
        4,
        labels=["Q1 (Lowest Buffer)", "Q2", "Q3", "Q4 (Highest Buffer)"],
        duplicates="drop",
    )
    quartiles = cohort_df.groupby("buffer_quartile", observed=False).agg(
        loans=("loan_id", "count"),
        defaults=("defaulted", "sum"),
        default_rate=("defaulted", lambda values: values.mean() * 100),
        median_buffer=("pre_buffer", "median"),
    ).reset_index()
    overdraft = cohort_df.groupby("had_pre_overdraft", observed=False).agg(
        loans=("loan_id", "count"),
        defaults=("defaulted", "sum"),
        default_rate=("defaulted", lambda values: values.mean() * 100),
    ).reset_index()

    result = {
        "cohort_size": len(cohort_df),
        "eligible_loan_count": len(loans),
        "window_months": 6,
        "window_start": cohort_df["window_start"].min(),
        "window_end": cohort_df["window_end"].max(),
        "quartile_summary": quartiles,
        "overdraft_summary": overdraft,
        "default_median_volatility": round(
            float(cohort_df.loc[cohort_df["defaulted"] == 1, "pre_in_cv"].median()), 3
        ),
        "healthy_median_volatility": round(
            float(cohort_df.loc[cohort_df["defaulted"] == 0, "pre_in_cv"].median()), 3
        ),
    }
    repo._analysis_cache["preloan_early_warning"] = result
    return {
        key: value.copy() if isinstance(value, pd.DataFrame) else value
        for key, value in result.items()
    }
