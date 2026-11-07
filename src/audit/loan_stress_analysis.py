import os
import pandas as pd
import numpy as np

# Dynamic path to data directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'tangerine', 'data')

def loan_and_stress_analysis():
    loans = pd.read_csv(os.path.join(DATA_DIR, 'loans.csv'))
    ms = pd.read_csv(os.path.join(DATA_DIR, 'monthly_summary.csv'))
    acc = pd.read_csv(os.path.join(DATA_DIR, 'accounts.csv'))
    tx = pd.read_csv(os.path.join(DATA_DIR, 'transactions.csv'), low_memory=False)

    # 1. Defaults vs Negative Balances
    ms_stress = ms.groupby('account_id').agg(
        months_total=('month', 'count'),
        months_below_zero=('days_below_zero', lambda s: (s > 0).sum()),
        total_days_below_zero=('days_below_zero', 'sum'),
        min_balance_ever=('min_balance', 'min'),
        avg_monthly_in=('money_in', 'mean'),
        avg_monthly_out=('money_out', 'mean'),
        std_monthly_in=('money_in', 'std'),
        std_monthly_out=('money_out', 'std')
    ).reset_index()

    loans_stress = loans.merge(ms_stress, on='account_id', how='left')
    print("=== LOANS VS FINANCIAL STRESS ===")
    print(loans_stress.groupby('status').agg(
        count=('loan_id', 'count'),
        pct_had_negative_balance=('months_below_zero', lambda s: (s > 0).mean() * 100),
        avg_days_below_zero=('total_days_below_zero', 'mean'),
        median_min_bal=('min_balance_ever', 'median'),
        mean_amount=('amount', 'mean'),
        mean_monthly_payment=('monthly_payment', 'mean')
    ))

    # Cross-tab of status vs months_below_zero > 0
    loans_stress['has_neg_bal'] = loans_stress['months_below_zero'] > 0
    print("\nStatus vs had negative balance:")
    print(pd.crosstab(loans_stress['status'], loans_stress['has_neg_bal'], normalize='index') * 100)

    # Non-loan accounts with negative balances
    non_loan_accs = ms_stress[~ms_stress['account_id'].isin(loans['account_id'])]
    print(f"\nNon-loan accounts total: {len(non_loan_accs)}")
    print(f"Non-loan accounts with negative balance: {(non_loan_accs['months_below_zero'] > 0).sum()} ({(non_loan_accs['months_below_zero'] > 0).mean()*100:.2f}%)")

    # Timing: Did negative balances happen BEFORE loan start date?
    # Let's inspect loan_start vs month of first negative balance!
    neg_ms = ms[ms['days_below_zero'] > 0].copy()
    first_neg = neg_ms.groupby('account_id')['month'].min().rename('first_neg_month')
    loans_with_first_neg = loans.merge(first_neg, on='account_id', how='left')
    loans_with_first_neg['loan_start_month'] = loans_with_first_neg['loan_start'].str.slice(0, 7)
    
    # Compare first_neg_month vs loan_start_month
    has_neg = loans_with_first_neg.dropna(subset=['first_neg_month']).copy()
    has_neg['neg_before_loan'] = has_neg['first_neg_month'] < has_neg['loan_start_month']
    has_neg['neg_same_month'] = has_neg['first_neg_month'] == has_neg['loan_start_month']
    has_neg['neg_after_loan'] = has_neg['first_neg_month'] > has_neg['loan_start_month']
    
    print("\nFor loan accounts that experienced negative balances:")
    print(has_neg.groupby('status').agg(
        total=('loan_id', 'count'),
        neg_before_loan=('neg_before_loan', 'sum'),
        neg_same_month=('neg_same_month', 'sum'),
        neg_after_loan=('neg_after_loan', 'sum')
    ))

if __name__ == '__main__':
    loan_and_stress_analysis()
