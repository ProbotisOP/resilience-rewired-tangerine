"""Reproduce supported portfolio outputs from the supplied source CSVs."""

from pathlib import Path
import sys
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATA_DIR
from src.data.local_repository import LocalDataRepository
from src.services.discovery_engine import (
    get_behavioral_association_tables,
    get_income_decile_discovery,
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


def run_all_discoveries() -> None:
    """Print reproducible estimates and denominators; omit unsupported interpretations."""
    data_dir = Path(DATA_DIR)
    print("SOURCE DATA ROW COUNTS")
    for filename, expected in EXPECTED_ROWS.items():
        columns = ["transaction_id"] if filename == "transactions.csv" else None
        count = len(pd.read_csv(data_dir / filename, usecols=columns))
        print(f"{filename}: {count:,} rows (expected {expected:,})")
        if count != expected:
            raise ValueError(f"{filename} contains {count} rows; expected {expected}")

    repo = LocalDataRepository(data_dir)
    repo.load_all()
    summary = get_population_summary(repo)
    print("\nACCOUNT-LEVEL BASELINE STATISTICS")
    print(f"Account denominator: {summary.total_accounts:,}")
    print(
        "Medians I/S/F/H/B: "
        f"${summary.median_I:,.2f} / ${summary.median_S:,.2f} / "
        f"${summary.median_F:,.2f} / ${summary.median_H:,.2f} / "
        f"${summary.median_B:,.2f}"
    )
    print(
        f"Median spending exceeds median money-in: {summary.accounts_in_deficit:,} "
        f"({summary.pct_in_deficit:.1f}%)"
    )
    print(f"Accounts with B <= 0: {summary.accounts_with_negative_buffer:,}")

    print("\nONE-DECIMAL JUDGE MATCH RUNWAY THRESHOLDS")
    print(get_population_scenario_distributions(repo).to_string(index=False))

    print("\nSIMULATED EI 55% RESULTS BY DYNAMIC MONEY-IN DECILE")
    print(get_income_decile_discovery(repo).to_string(index=False))

    preloan = get_preloan_early_warning_data(repo)
    print(
        f"\nPRE-ORIGINATION ASSOCIATION: {preloan['cohort_size']:,} of "
        f"{preloan.get('eligible_loan_count', 0):,} loans with six available pre-start rows"
    )
    print(preloan["quartile_summary"].to_string(index=False))
    print(preloan["overdraft_summary"].to_string(index=False))

    associations = get_behavioral_association_tables(repo)
    for key in ("authorized_user", "statement_frequency", "card", "cash_deposit_reliance", "leasing_order"):
        print(f"\nDESCRIPTIVE ASSOCIATION: {key}")
        print(associations[key].to_string(index=False))
    print("\nEXTERNAL-DESTINATION PAYMENT INSTRUCTIONS")
    print(associations["external_destination_instructions"].to_string(index=False))
    print(
        "\nNot reproduced as findings: causal penalty-fee claims, 48–72-hour payday "
        "sequencing, or treating cash withdrawals as discretionary."
    )


if __name__ == "__main__":
    run_all_discoveries()
