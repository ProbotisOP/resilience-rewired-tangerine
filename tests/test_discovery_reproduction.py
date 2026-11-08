"""Independent raw-CSV references for portfolio and discovery outputs."""

from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import DATA_DIR
from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import compute_portfolio_account_metrics
from src.services.baseline_metrics import compute_official_baseline
from src.services.shock_engine import simulate_shock
from config.scenarios import OFFICIAL_PRESETS
from src.services.discovery_engine import (
    get_behavioral_association_tables,
    get_income_decile_discovery,
    get_portfolio_scenario_runways,
    get_population_scenario_distributions,
    get_population_summary,
    get_preloan_early_warning_data,
)


EXPECTED_ROWS = {
    "accounts.csv": 4500,
    "cards.csv": 892,
    "clients.csv": 5369,
    "dispositions.csv": 5369,
    "districts.csv": 77,
    "loans.csv": 682,
    "monthly_summary.csv": 185326,
    "standing_orders.csv": 6471,
    "transactions.csv": 1056320,
}


def _raw_account_reference():
    monthly = pd.read_csv(DATA_DIR / "monthly_summary.csv")
    monthly = monthly.sort_values(["account_id", "month"]).copy()
    monthly["fixed"] = (
        monthly["household_bills"] + monthly["insurance"] + monthly["loan_payments"]
    )
    reference = monthly.groupby("account_id").agg(
        I=("money_in", "median"),
        S=("money_out", "median"),
        F=("fixed", "median"),
        H=("household_bills", "median"),
    )
    reference["B"] = (
        monthly.groupby("account_id")
        .tail(6)
        .groupby("account_id")["avg_daily_balance"]
        .mean()
    )
    return monthly, reference


def _reference_runway(buffer, income, spending, one_off=0.0):
    remaining = round(round(buffer, 2) - round(one_off, 2), 2)
    gap = round(round(spending, 2) - round(income, 2), 2)
    if remaining <= 0:
        return 0.0
    if gap <= 0:
        return 120.0
    return round(min(remaining / gap, 120.0), 1)


def test_source_directory_has_all_nine_expected_csvs_and_account_ids():
    for filename, expected_rows in EXPECTED_ROWS.items():
        path = Path(DATA_DIR) / filename
        assert path.is_file()
        if filename == "transactions.csv":
            actual_rows = len(pd.read_csv(path, usecols=["transaction_id"]))
        else:
            actual_rows = len(pd.read_csv(path))
        assert actual_rows == expected_rows

    accounts = pd.read_csv(DATA_DIR / "accounts.csv")
    monthly = pd.read_csv(DATA_DIR / "monthly_summary.csv")
    calculated = compute_portfolio_account_metrics(monthly)
    account_ids = set(accounts["account_id"])
    assert len(account_ids) == 4500
    assert set(calculated.index) == account_ids
    assert (monthly.groupby("account_id").size().reindex(account_ids) >= 6).all()


def test_all_account_baselines_match_independent_monthly_row_calculations():
    monthly, reference = _raw_account_reference()
    actual = compute_portfolio_account_metrics(monthly)
    assert set(actual.index) == set(reference.index)
    for metric in ("I", "S", "F", "H", "B"):
        assert np.allclose(actual[metric].sort_index(), reference[metric].sort_index())

    expected_runways = [
        _reference_runway(row.B, row.I, row.S)
        for row in reference.itertuples()
    ]
    assert np.array_equal(
        actual.sort_index()["baseline_runway"].to_numpy(),
        np.asarray(expected_runways),
    )


def test_portfolio_summary_matches_independent_account_level_csv_reference():
    repo = LocalDataRepository.get_instance()
    _, reference = _raw_account_reference()
    summary = get_population_summary(repo)
    assert summary.total_accounts == 4500
    assert summary.median_I == round(reference["I"].median(), 2)
    assert summary.median_S == round(float(reference["S"].median()), 2)
    assert summary.median_F == round(reference["F"].median(), 2)
    assert summary.median_H == round(reference["H"].median(), 2)
    assert summary.median_B == round(reference["B"].median(), 2)
    assert summary.accounts_in_deficit == int(
        (reference["S"].round(2) - reference["I"].round(2) > 0).sum()
    )
    assert summary.accounts_with_negative_buffer == int((reference["B"] <= 0).sum())
    assert summary.median_H == 1536.68
    assert summary.median_F == 1774.16
    assert summary.median_S == 7388.65


def test_scenario_thresholds_match_independent_rounded_runway_reference():
    repo = LocalDataRepository.get_instance()
    _, reference = _raw_account_reference()
    cases = [
        ("Baseline (Status Quo)", 1.0, 0.0, 0.0),
        ("Job Loss (EI @ 55%)", 0.55, 0.0, 0.0),
        ("Emergency Repair (Cost = S)", 1.0, 0.0, 1.0),
        ("Combined Shock (EI 55% + Bills +15%)", 0.55, 0.15, 0.0),
    ]
    actual = get_population_scenario_distributions(repo).set_index("Scenario")
    for label, income_rate, bill_rate, one_off_rate in cases:
        runways = [
            _reference_runway(
                row.B,
                round(income_rate * round(row.I, 2), 2),
                round(round(row.S, 2) + bill_rate * round(row.H, 2), 2),
                round(one_off_rate * round(row.S, 2), 2),
            )
            for row in reference.itertuples()
        ]
        assert int(actual.loc[label, "Accounts"]) == len(reference)
        for threshold in (3, 6, 12):
            count = sum(value < threshold for value in runways)
            assert int(actual.loc[label, f"Below {threshold}M"]) == count
            assert actual.loc[label, f"Below {threshold}M (%)"] == round(
                count / len(reference) * 100, 1
            )

    assert int(actual.loc["Job Loss (EI @ 55%)", "Below 6M"]) == 1578
    assert int(actual.loc["Combined Shock (EI 55% + Bills +15%)", "Below 6M"]) == 1740


def test_income_decile_discovery_matches_independent_simulation():
    repo = LocalDataRepository.get_instance()
    _, reference = _raw_account_reference()
    labels = [f"D{i}" for i in range(1, 11)]
    deciles = pd.qcut(reference["I"], 10, labels=labels)
    runways = [
        _reference_runway(row.B, round(0.55 * round(row.I, 2), 2), round(row.S, 2))
        for row in reference.itertuples()
    ]
    expected = pd.DataFrame(
        {
            "decile": deciles,
            "income": reference["I"],
            "runway": runways,
        }
    ).groupby("decile", observed=False).agg(
        accounts=("income", "size"),
        median_income=("income", "median"),
        median_runway=("runway", "median"),
        below_six=("runway", lambda values: int((values < 6).sum())),
        pct_below_six=("runway", lambda values: round((values < 6).mean() * 100, 1)),
    )
    actual = get_income_decile_discovery(repo).set_index("Income Decile")
    for decile in labels:
        assert int(actual.loc[decile, "Accounts"]) == expected.loc[decile, "accounts"]
        assert actual.loc[decile, "Median Income"] == expected.loc[decile, "median_income"]
        assert actual.loc[decile, "Median Runway (EI 55%)"] == expected.loc[
            decile, "median_runway"
        ]
        assert int(actual.loc[decile, "Accounts Below 6 Months"]) == expected.loc[
            decile, "below_six"
        ]
        assert actual.loc[decile, "% Below 6 Months"] == expected.loc[
            decile, "pct_below_six"
        ]


def test_interactive_portfolio_scenario_matches_independent_csv_reference():
    repo = LocalDataRepository.get_instance()
    _, reference = _raw_account_reference()
    actual = get_portfolio_scenario_runways(
        repo,
        income_multiplier=0.55,
        household_bill_change=0.15,
        one_off_spend_multiplier=0.5,
    ).set_index("account_id")["runway_months"]

    expected = []
    for row in reference.itertuples():
        income = round(0.55 * round(row.I, 2), 2)
        spending = round(round(row.S, 2) + 0.15 * round(row.H, 2), 2)
        one_off = round(0.5 * round(row.S, 2), 2)
        expected.append(_reference_runway(row.B, income, spending, one_off))
    expected_series = pd.Series(expected, index=reference.index).sort_index()

    pd.testing.assert_series_equal(
        actual.sort_index().astype(float),
        expected_series.astype(float),
        check_names=False,
    )


def test_preloan_cohort_matches_independent_six_available_row_reference():
    repo = LocalDataRepository.get_instance()
    monthly = pd.read_csv(DATA_DIR / "monthly_summary.csv")
    monthly_by_account = {
        account_id: rows.sort_values("month")
        for account_id, rows in monthly.groupby("account_id")
    }
    loans = pd.read_csv(DATA_DIR / "loans.csv")
    cohort = []
    for loan in loans.itertuples():
        pre = monthly_by_account[loan.account_id]
        pre = pre[pre["month"] < str(loan.loan_start)[:7]]
        if len(pre) >= 6:
            last_six = pre.tail(6)
            cohort.append(
                {
                    "loan_id": loan.loan_id,
                    "defaulted": int(loan.defaulted),
                    "had_pre_overdraft": bool((last_six["days_below_zero"] > 0).any()),
                    "pre_buffer": last_six["avg_daily_balance"].mean(),
                }
            )
    expected = pd.DataFrame(cohort)
    actual = get_preloan_early_warning_data(repo)
    assert actual["cohort_size"] == len(expected)
    assert actual["eligible_loan_count"] == len(loans)
    assert actual["window_months"] == 6

    expected["quartile"] = pd.qcut(
        expected["pre_buffer"],
        4,
        labels=["Q1 (Lowest Buffer)", "Q2", "Q3", "Q4 (Highest Buffer)"],
    )
    expected_q = expected.groupby("quartile", observed=False).agg(
        loans=("loan_id", "size"),
        defaults=("defaulted", "sum"),
    )
    actual_q = actual["quartile_summary"].set_index("buffer_quartile")
    pd.testing.assert_series_equal(
        actual_q["loans"].astype(int), expected_q["loans"].astype(int), check_names=False
    )
    pd.testing.assert_series_equal(
        actual_q["defaults"].astype(int), expected_q["defaults"].astype(int), check_names=False
    )


def test_behavioral_association_tables_match_raw_table_joins():
    repo = LocalDataRepository.get_instance()
    accounts = pd.read_csv(DATA_DIR / "accounts.csv")
    dispositions = pd.read_csv(DATA_DIR / "dispositions.csv")
    cards = pd.read_csv(DATA_DIR / "cards.csv")
    loans = pd.read_csv(DATA_DIR / "loans.csv")
    standing_orders = pd.read_csv(DATA_DIR / "standing_orders.csv")
    monthly = pd.read_csv(DATA_DIR / "monthly_summary.csv")
    monthly_flags = monthly.groupby("account_id")["days_below_zero"].apply(
        lambda values: bool((values > 0).any())
    )
    reference = accounts.set_index("account_id")[["frequency"]].join(monthly_flags.rename("had_negative"))
    reference["has_authorized_user"] = reference.index.isin(
        dispositions.loc[dispositions["type"] == "authorized user", "account_id"]
    )
    owner_dispositions = dispositions.loc[
        dispositions["type"] == "owner", ["account_id", "disposition_id"]
    ]
    reference["has_card"] = reference.index.isin(
        cards.merge(owner_dispositions, on="disposition_id")["account_id"]
    )
    reference["has_leasing_order"] = reference.index.isin(
        standing_orders.loc[standing_orders["purpose"] == "leasing", "account_id"]
    )
    reference["has_loan"] = reference.index.isin(loans["account_id"])
    reference = reference.join(loans.set_index("account_id")[["defaulted"]])
    reference["defaulted"] = reference["defaulted"].fillna(0).astype(int)

    actual = get_behavioral_association_tables(repo)
    for output_key, group_key in (
        ("authorized_user", "has_authorized_user"),
        ("statement_frequency", "frequency"),
        ("card", "has_card"),
        ("leasing_order", "has_leasing_order"),
    ):
        expected = reference.groupby(group_key).agg(
            accounts=("had_negative", "size"),
            accounts_with_negative_balance_days=("had_negative", "sum"),
            loans=("has_loan", "sum"),
            defaults=("defaulted", "sum"),
        )
        observed = actual[output_key].set_index(group_key)
        for field in expected:
            pd.testing.assert_series_equal(
                observed[field].sort_index().astype(int),
                expected[field].sort_index().astype(int),
                check_names=False,
            )

    expected_external = standing_orders[
        standing_orders["purpose"] == "loan payment"
    ]
    external = actual["external_destination_instructions"].iloc[0]
    assert int(external["standing_order_rows"]) == len(expected_external)
    assert int(external["accounts_with_instruction"]) == expected_external["account_id"].nunique()
    assert int(external["accounts_without_internal_loan"]) == expected_external.loc[
        ~expected_external["account_id"].isin(loans["account_id"]), "account_id"
    ].nunique()


def test_sample_account_live_shocks_match_independent_formula():
    repo = LocalDataRepository.get_instance()
    source_monthly, _ = _raw_account_reference()
    sample_accounts = [20111, 55447, 62236, 74958]
    scenarios = [OFFICIAL_PRESETS[1], OFFICIAL_PRESETS[2], OFFICIAL_PRESETS[3]]

    for account_id in sample_accounts:
        rows = source_monthly[source_monthly["account_id"] == account_id]
        income = round(float(rows["money_in"].median()), 2)
        spending = round(float(rows["money_out"].median()), 2)
        bills = round(float(rows["household_bills"].median()), 2)
        buffer = round(float(rows.tail(6)["avg_daily_balance"].mean()), 2)
        baseline = compute_official_baseline(
            account_id,
            repo.get_monthly_summary(account_id),
            repo.get_account_meta(account_id),
        )
        for scenario in scenarios:
            result = simulate_shock(baseline, scenario)
            expected_income = round(scenario.income_multiplier * income, 2)
            expected_spending = round(
                spending + scenario.household_bills_pct * bills, 2
            )
            one_off = round(
                scenario.one_off_spend_multiplier * spending
                + scenario.one_off_fixed_amount,
                2,
            )
            assert result.income_after_shock == expected_income
            assert result.spending_after_shock == expected_spending
            assert result.one_off_costs == one_off
            assert result.runway_months == _reference_runway(
                buffer, expected_income, expected_spending, one_off
            )
