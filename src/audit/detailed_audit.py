import os
import pandas as pd
import numpy as np

# Dynamic path to data directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'tangerine', 'data')

def detailed_audit():
    accounts = pd.read_csv(os.path.join(DATA_DIR, 'accounts.csv'))
    clients = pd.read_csv(os.path.join(DATA_DIR, 'clients.csv'))
    dispositions = pd.read_csv(os.path.join(DATA_DIR, 'dispositions.csv'))
    cards = pd.read_csv(os.path.join(DATA_DIR, 'cards.csv'))
    districts = pd.read_csv(os.path.join(DATA_DIR, 'districts.csv'))
    loans = pd.read_csv(os.path.join(DATA_DIR, 'loans.csv'))
    standing_orders = pd.read_csv(os.path.join(DATA_DIR, 'standing_orders.csv'))
    ms = pd.read_csv(os.path.join(DATA_DIR, 'monthly_summary.csv'))
    tx = pd.read_csv(os.path.join(DATA_DIR, 'transactions.csv'))

    print("=== 1. DATA QUALITY & EDGE CASES ===")
    
    # 1. Accounts audit
    print("\n[Accounts]")
    print(f"Missing values:\n{accounts.isnull().sum()}")
    print(f"Date range of account_opened: {accounts['account_opened'].min()} to {accounts['account_opened'].max()}")
    print("Frequency distribution:\n", accounts['frequency'].value_counts())
    
    # 2. Clients audit
    print("\n[Clients]")
    clients['birth_date_dt'] = pd.to_datetime(clients['birth_date'])
    # Age as of end of 2025:
    clients['age_at_2025'] = (pd.to_datetime('2025-12-31') - clients['birth_date_dt']).dt.days / 365.25
    print(f"Age summary (as of 2025-12-31):\n{clients['age_at_2025'].describe()}")
    
    # 3. Dispositions audit
    print("\n[Dispositions]")
    disp_with_clients = dispositions.merge(clients, on='client_id', how='left')
    disp_with_acc = disp_with_clients.merge(accounts[['account_id', 'district_id']], on='account_id', suffixes=('_client_home', '_acc_branch'))
    diff_districts = (disp_with_acc['district_id_client_home'] != disp_with_acc['district_id_acc_branch']).sum()
    print(f"Clients living in a different district from account branch: {diff_districts} / {len(disp_with_acc)} ({diff_districts/len(disp_with_acc)*100:.1f}%)")
    
    authorized_account_count = dispositions.loc[
        dispositions["type"] == "authorized user", "account_id"
    ].nunique()
    print(f"Accounts with at least one authorized user: {authorized_account_count}")
    print(
        "An authorized-user disposition records account access; it does not identify "
        "a spouse, partner, household member or co-borrower."
    )

    # 4. Cards audit
    print("\n[Cards]")
    cards_disp = cards.merge(dispositions, on='disposition_id', how='left')
    print(f"Cards held by role:\n{cards_disp['type'].value_counts()}")
    print(f"Cards by card_type:\n{cards_disp['card_type'].value_counts()}")

    # 5. Districts audit
    print("\n[Districts]")
    print(districts.describe().T[['mean', 'std', 'min', '50%', 'max']])
    d69 = districts[districts['district_id'] == 69]
    print(f"District 69 row:\n{d69.to_dict(orient='records')}")

    # 6. Monthly summary audit
    print("\n[Monthly Summary]")
    print(f"Total months: {ms['month'].nunique()} ({ms['month'].min()} to {ms['month'].max()})")
    acc_month_counts = ms.groupby('account_id')['month'].count()
    print(f"Months per account distribution:\n{acc_month_counts.describe()}")
    
    # Are there negative balances?
    print(f"Rows with min_balance < 0: {(ms['min_balance'] < 0).sum()} ({(ms['min_balance'] < 0).sum()/len(ms)*100:.2f}%)")
    print(f"Rows with month_end_balance < 0: {(ms['month_end_balance'] < 0).sum()} ({(ms['month_end_balance'] < 0).sum()/len(ms)*100:.2f}%)")
    print(f"Rows with days_below_zero > 0: {(ms['days_below_zero'] > 0).sum()} ({(ms['days_below_zero'] > 0).sum()/len(ms)*100:.2f}%)")
    print(f"Unique accounts that ever had days_below_zero > 0: {ms[ms['days_below_zero'] > 0]['account_id'].nunique()}")
    
    # 7. Transactions audit
    print("\n[Transactions]")
    print(f"Negative balance transactions count: {(tx['balance'] < 0).sum()}")
    print(f"Accounts with negative tx balance: {tx[tx['balance'] < 0]['account_id'].nunique()}")
    print("Negative balance penalty interest transactions:")
    penalty = tx[tx['purpose'] == 'penalty interest (negative balance)']
    print(f"  Count: {len(penalty)}")
    print(f"  Unique accounts hit by penalties: {penalty['account_id'].nunique()}")
    print(f"  Penalty amount stats:\n{penalty['amount'].describe()}")

    # 8. Standing orders audit
    print("\n[Standing Orders]")
    print(f"Accounts with standing orders: {standing_orders['account_id'].nunique()} / 4500")
    so_per_acc = standing_orders.groupby('account_id').size()
    print(f"Standing orders per account:\n{so_per_acc.describe()}")

if __name__ == '__main__':
    detailed_audit()
