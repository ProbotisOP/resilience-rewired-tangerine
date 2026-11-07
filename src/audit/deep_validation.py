import os
import pandas as pd
import numpy as np

# Dynamic path to data directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'tangerine', 'data')

def deep_data_validation():
    ms = pd.read_csv(os.path.join(DATA_DIR, 'monthly_summary.csv'))
    tx = pd.read_csv(os.path.join(DATA_DIR, 'transactions.csv'), low_memory=False)
    loans = pd.read_csv(os.path.join(DATA_DIR, 'loans.csv'))

    # Check 1: Monthly balance continuity
    # month_end_balance of previous month + money_in - money_out == month_end_balance of current month?
    ms_sorted = ms.sort_values(['account_id', 'month']).copy()
    ms_sorted['prev_end_bal'] = ms_sorted.groupby('account_id')['month_end_balance'].shift(1)
    
    # Exclude first month of each account
    valid_subsequent = ms_sorted.dropna(subset=['prev_end_bal']).copy()
    valid_subsequent['expected_end_bal'] = valid_subsequent['prev_end_bal'] + valid_subsequent['money_in'] - valid_subsequent['money_out']
    bal_diff = (valid_subsequent['expected_end_bal'] - valid_subsequent['month_end_balance']).abs()
    print(f"Subsequent months evaluated: {len(valid_subsequent):,}")
    print(f"Max discrepancy between (prev_balance + money_in - money_out) and month_end_balance: {bal_diff.max():.6f}")
    print(f"Discrepancies > $0.05: {(bal_diff > 0.05).sum()}")

    # Check 2: Transaction aggregation comparison for sample accounts
    # Take 5 random accounts and compare monthly sum of tx signed_amount to monthly_summary net flow
    sample_accs = [20111, 55447, 74958, 62236, 1]
    # Check if these accounts are in tx
    sample_accs = [a for a in sample_accs if a in tx['account_id'].values]
    print(f"\nChecking transaction sum vs monthly_summary for accounts: {sample_accs}")
    for a in sample_accs:
        sub_tx = tx[tx['account_id'] == a].copy()
        sub_tx['month'] = sub_tx['date'].str.slice(0, 7)
        tx_agg = sub_tx.groupby('month').agg(
            tx_in=('amount', lambda s: s[sub_tx.loc[s.index, 'direction'] == 'credit (money in)'].sum()),
            tx_out=('amount', lambda s: s[sub_tx.loc[s.index, 'direction'] == 'debit (money out)'].sum()),
            tx_count=('transaction_id', 'count')
        ).reset_index()
        
        sub_ms = ms[ms['account_id'] == a][['month', 'money_in', 'money_out']].copy()
        merged = sub_ms.merge(tx_agg, on='month', how='left').fillna(0)
        in_diff = (merged['money_in'] - merged['tx_in']).abs().max()
        out_diff = (merged['money_out'] - merged['tx_out']).abs().max()
        print(f"Account {a}: {len(merged)} months. Max In diff: {in_diff:.4f}, Max Out diff: {out_diff:.4f}")

    # Check 3: Check loan payments in monthly summary vs loans.csv
    # In monthly_summary, column 'loan_payments'
    ms_loans = ms.groupby('account_id')['loan_payments'].sum()
    accounts_with_loan_payments_in_ms = ms_loans[ms_loans > 0].index
    print(f"\nAccounts with 'loan_payments' > 0 in monthly_summary: {len(accounts_with_loan_payments_in_ms)}")
    print(f"Accounts in loans.csv: {loans['account_id'].nunique()}")
    print(f"Are all accounts in loans.csv having loan payments in monthly_summary? {loans['account_id'].isin(accounts_with_loan_payments_in_ms).all()}")
    print(f"Accounts with loan payments in monthly_summary but NOT in loans.csv: {set(accounts_with_loan_payments_in_ms) - set(loans['account_id'])}")

    # Check 4: Buffer <= 0 accounts profile
    # Let's inspect the 23 accounts with Buffer <= 0
    last6 = ms_sorted.groupby('account_id').tail(6)
    buffers = last6.groupby('account_id')['avg_daily_balance'].mean().rename('B')
    neg_b_accs = buffers[buffers <= 0].index
    neg_b_loans = loans[loans['account_id'].isin(neg_b_accs)]
    print(f"\nOf the 23 accounts with Buffer <= 0, how many have loans?: {len(neg_b_loans)}")
    print("Their loan status:\n", neg_b_loans['status'].value_counts())

if __name__ == '__main__':
    deep_data_validation()
