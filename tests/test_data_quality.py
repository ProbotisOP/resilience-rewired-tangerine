"""
Integration tests for raw datasets and relational integrity.
"""

from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import compute_official_baseline

def test_data_integrity():
    repo = LocalDataRepository.get_instance()
    
    # 1. Accounts
    assert len(repo.accounts) == 4500
    assert repo.accounts["account_id"].nunique() == 4500

    # 2. Loans
    assert len(repo.loans) == 682
    assert repo.loans["loan_id"].nunique() == 682
    assert repo.loans["status"].isin(["C", "D"]).sum() == 448  # Active at end of 2025

    # 3. Monthly Summary
    assert len(repo.monthly_summary) == 185326
    assert repo.monthly_summary["account_id"].nunique() == 4500

    # 4. Check an arbitrary real account (Account 20111)
    acc_id = 20111
    acc_meta = repo.get_account_meta(acc_id)
    assert acc_meta is not None
    assert acc_meta["has_loan"] is True
    assert acc_meta["loan_status"] in ["C", "D"]
    assert bool(acc_meta["loan_is_running_2025"]) is True

    monthly_df = repo.get_monthly_summary(acc_id)
    assert len(monthly_df) >= 6

    baseline = compute_official_baseline(acc_id, monthly_df, acc_meta)
    assert baseline.I == 6339.39
    assert baseline.F == 2330.06
    assert baseline.S == 8599.60
    assert baseline.P == 2330.19
    assert baseline.baseline_runway == 7.8

if __name__ == "__main__":
    test_data_integrity()
    print("Data integrity tests passed successfully!")
