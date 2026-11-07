import os
import pandas as pd
import numpy as np

# Dynamic path to data directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'tangerine', 'data')

def inspect_all():
    print("=" * 80)
    print("PHASE 1: COMPREHENSIVE DATA RECONNAISSANCE")
    print("=" * 80)
    
    files = {
        'accounts': 'accounts.csv',
        'clients': 'clients.csv',
        'dispositions': 'dispositions.csv',
        'cards': 'cards.csv',
        'districts': 'districts.csv',
        'loans': 'loans.csv',
        'standing_orders': 'standing_orders.csv',
        'monthly_summary': 'monthly_summary.csv',
        'transactions': 'transactions.csv'
    }
    
    dfs = {}
    for name, fname in files.items():
        path = os.path.join(DATA_DIR, fname)
        # for transactions, let's load or sample/inspect types
        print(f"\n--- Loading {fname} ---")
        df = pd.read_csv(path, low_memory=False)
        dfs[name] = df
        print(f"Shape: {df.shape[0]:,} rows x {df.shape[1]} cols")
        print(f"Columns & dtypes: {dict(df.dtypes)}")
        print(f"Missing values:\n{df.isnull().sum()[df.isnull().sum() > 0]}")
        print(f"Duplicate rows: {df.duplicated().sum()}")
        print(f"Sample row:\n{df.head(1).to_dict(orient='records')}")

    print("\n" + "=" * 80)
    print("RELATIONAL INTEGRITY & KEY RELATIONSHIPS")
    print("=" * 80)

    acc = dfs['accounts']
    cli = dfs['clients']
    disp = dfs['dispositions']
    cards = dfs['cards']
    dist = dfs['districts']
    loans = dfs['loans']
    so = dfs['standing_orders']
    ms = dfs['monthly_summary']
    tx = dfs['transactions']

    # Accounts
    print(f"Accounts unique account_id: {acc['account_id'].nunique()} (Total rows: {len(acc)})")
    print(f"Account opening dates: {acc['account_opened'].min()} to {acc['account_opened'].max()}")
    print(f"Account frequencies: {acc['frequency'].value_counts().to_dict()}")

    # Clients & Dispositions
    print(f"Clients unique client_id: {cli['client_id'].nunique()}")
    print(f"Clients gender dist: {cli['gender'].value_counts().to_dict()}")
    print(f"Clients birth_date range: {cli['birth_date'].min()} to {cli['birth_date'].max()}")
    print(f"Dispositions unique disposition_id: {disp['disposition_id'].nunique()}")
    print(f"Dispositions types: {disp['type'].value_counts().to_dict()}")
    print(f"Dispositions account_id in accounts: {disp['account_id'].isin(acc['account_id']).all()}")
    print(f"Dispositions client_id in clients: {disp['client_id'].isin(cli['client_id']).all()}")

    # Accounts per owner / user
    disp_acc_counts = disp.groupby('account_id')['type'].value_counts().unstack(fill_value=0)
    print(f"Account disposition profile (owner count distribution):\n{disp_acc_counts['owner'].value_counts()}")
    if 'authorized user' in disp_acc_counts:
        print(f"Accounts with authorized users:\n{disp_acc_counts['authorized user'].value_counts()}")

    # Cards
    print(f"Cards count: {len(cards)}, unique card_id: {cards['card_id'].nunique()}")
    print(f"Cards types: {cards['card_type'].value_counts().to_dict()}")
    print(f"Cards disposition_id in disp: {cards['disposition_id'].isin(disp['disposition_id']).all()}")
    print(f"Cards issue date range: {cards['issued'].min()} to {cards['issued'].max()}")

    # Districts
    print(f"Districts count: {len(dist)}, unique district_id: {dist['district_id'].nunique()}")
    print(f"Districts in accounts covered by districts: {acc['district_id'].isin(dist['district_id']).all()}")
    print(f"Districts in clients covered by districts: {cli['district_id'].isin(dist['district_id']).all()}")

    # Loans
    print(f"Loans count: {len(loans)}, unique loan_id: {loans['loan_id'].nunique()}, unique account_id: {loans['account_id'].nunique()}")
    print(f"Loans account_id in accounts: {loans['account_id'].isin(acc['account_id']).all()}")
    print(f"Loans status distribution:\n{loans['status'].value_counts()}")
    print(f"Loans status_meaning distribution:\n{loans['status_meaning'].value_counts()}")
    print(f"Loans defaulted distribution:\n{loans['defaulted'].value_counts()}")
    print(f"Loans start dates: {loans['loan_start'].min()} to {loans['loan_start'].max()}")
    print(f"Loans duration months: {loans['duration_months'].value_counts().to_dict()}")
    
    # Check loan running at end of 2025
    # Loan running at end of 2025: status C or D?
    print(f"Status C loans (running OK): {sum(loans['status'] == 'C')}")
    print(f"Status D loans (running debt): {sum(loans['status'] == 'D')}")
    print(f"Status A (finished repaid): {sum(loans['status'] == 'A')}")
    print(f"Status B (finished defaulted): {sum(loans['status'] == 'B')}")

    # Monthly summary
    print(f"Monthly summary count: {len(ms)}, unique account_id: {ms['account_id'].nunique()}")
    print(f"Monthly summary month range: {ms['month'].min()} to {ms['month'].max()}")
    print(f"All accounts in accounts have monthly summary? {acc['account_id'].isin(ms['account_id']).all()}")
    print(f"All accounts in monthly summary in accounts? {ms['account_id'].isin(acc['account_id']).all()}")

    # Check monthly summary formula components:
    # cash_deposits + transfers_in + pension_in + interest_in == money_in
    in_sum = ms['cash_deposits'] + ms['transfers_in'] + ms['pension_in'] + ms['interest_in']
    diff_in = (in_sum - ms['money_in']).abs()
    print(f"Max abs diff between parts and money_in: {diff_in.max()}")

    # spending parts: household_bills, insurance, loan_payments, bank_fees, cash_withdrawals_genuine, card_withdrawals, transfers_out_other
    out_parts = ['household_bills', 'insurance', 'loan_payments', 'bank_fees', 'cash_withdrawals_genuine', 'card_withdrawals', 'transfers_out_other']
    out_sum = ms[out_parts].sum(axis=1)
    diff_out = (out_sum - ms['money_out']).abs()
    print(f"Max abs diff between parts and money_out: {diff_out.max()}")

    # Transactions
    print(f"Transactions count: {len(tx)}, unique account_id: {tx['account_id'].nunique()}")
    print(f"Transactions date range: {tx['date'].min()} to {tx['date'].max()}")
    print(f"All tx account_id in accounts? {tx['account_id'].isin(acc['account_id']).all()}")
    print(f"Transactions operations:\n{tx['operation'].value_counts()}")
    print(f"Transactions purposes:\n{tx['purpose'].value_counts(dropna=False)}")

    # Standing orders
    print(f"Standing orders count: {len(so)}, unique account_id: {so['account_id'].nunique()}")
    print(f"Standing orders purpose:\n{so['purpose'].value_counts(dropna=False)}")

if __name__ == '__main__':
    inspect_all()
