"""Audit entry point for the shared baseline and official scenario calculations."""

from src.data.local_repository import LocalDataRepository
from src.services.discovery_engine import (
    get_population_scenario_distributions,
    get_population_summary,
)


def test_judging_metrics():
    repo = LocalDataRepository.get_instance()
    summary = get_population_summary(repo)
    print("Account-level portfolio medians across the supplied records:")
    print(
        f"Accounts: {summary.total_accounts:,}; I=${summary.median_I:,.2f}; "
        f"S=${summary.median_S:,.2f}; F=${summary.median_F:,.2f}; "
        f"H=${summary.median_H:,.2f}; B=${summary.median_B:,.2f}"
    )
    print(
        f"Accounts with S > I: {summary.accounts_in_deficit:,} / "
        f"{summary.total_accounts:,}"
    )
    print(
        "Runway threshold counts use one-decimal official Judge Match values:"
    )
    print(get_population_scenario_distributions(repo).to_string(index=False))


if __name__ == "__main__":
    test_judging_metrics()
