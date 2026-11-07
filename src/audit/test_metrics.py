import os
import pandas as pd
import numpy as np

# Dynamic path to data directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'tangerine', 'data')

def test_judging_metrics():
    loans = pd.read_csv(os.path.join(DATA_DIR, 'loans.csv'))
    ms = pd.read_csv(os.path.join(DATA_DIR, 'monthly_summary.csv'))
    
    # Check running loans at end of 2025
    # The README states: "monthly_payment in loans.csv if the loan is still running at the end of 2025, otherwise 0"
    # Statuses: C = running, OK so far; D = running, client in debt.
    # What about loan_start + duration_months? Let's check!
    loans['loan_start_dt'] = pd.to_datetime(loans['loan_start'])
    # In loans.csv: duration_months is 12, 24, 36, 48, 60.
    # When does a loan end?
    loans['end_date_approx'] = loans['loan_start_dt'] + pd.to_timedelta(loans['duration_months'] * 30.4375, unit='D')
    print("Loans status breakdown:")
    print(loans.groupby('status').agg(
        count=('loan_id', 'count'),
        min_start=('loan_start', 'min'),
        max_start=('loan_start', 'max'),
        min_end=('end_date_approx', 'min'),
        max_end=('end_date_approx', 'max')
    ))
    
    # Are status C and D strictly those running at end of 2025?
    # Let's inspect status A and B vs C and D end dates:
    print("\nStatus C and D loan end dates compared to 2025-12-31:")
    print(f"Status C min end date: {loans[loans['status']=='C']['end_date_approx'].min()}")
    print(f"Status C max end date: {loans[loans['status']=='C']['end_date_approx'].max()}")
    print(f"Status D min end date: {loans[loans['status']=='D']['end_date_approx'].min()}")
    print(f"Status D max end date: {loans[loans['status']=='D']['end_date_approx'].max()}")
    print(f"Status A max end date: {loans[loans['status']=='A']['end_date_approx'].max()}")
    print(f"Status B max end date: {loans[loans['status']=='B']['end_date_approx'].max()}")

    # Now calculate baseline judging metrics for all 4,500 accounts
    # Sort monthly_summary by account_id and month
    ms_sorted = ms.sort_values(['account_id', 'month'])
    
    # 1. Typical monthly money in (I) = median money_in
    # 2. Typical fixed costs (F) = median(household_bills + insurance + loan_payments)
    # 3. Typical monthly spending (S) = median money_out
    # 4. Household bills (H) = median household_bills
    # 5. Buffer (B) = mean of avg_daily_balance over the account's last 6 rows, sorted by month
    
    ms_sorted['fixed_costs'] = ms_sorted['household_bills'] + ms_sorted['insurance'] + ms_sorted['loan_payments']
    
    agg_medians = ms_sorted.groupby('account_id').agg(
        I=('money_in', 'median'),
        F=('fixed_costs', 'median'),
        S=('money_out', 'median'),
        H=('household_bills', 'median'),
        months_count=('month', 'count')
    )
    
    # Buffer: last 6 rows
    last6 = ms_sorted.groupby('account_id').tail(6)
    buffers = last6.groupby('account_id')['avg_daily_balance'].mean().rename('B')
    
    # Running loan payment:
    running_loans = loans[loans['status'].isin(['C', 'D'])].set_index('account_id')['monthly_payment']
    
    baseline_df = agg_medians.join(buffers).join(running_loans).rename(columns={'monthly_payment': 'P'})
    baseline_df['P'] = baseline_df['P'].fillna(0.0)
    
    print("\nBaseline judging metrics distribution across 4,500 accounts:")
    print(baseline_df[['I', 'F', 'S', 'H', 'B', 'P']].describe())
    
    # Baseline runway (no shock, one_off_costs = 0, income = I, spending = S)
    # gap = S - I
    baseline_df['gap'] = baseline_df['S'] - baseline_df['I']
    
    # Runway calculation
    def calc_runway(b, gap):
        if b <= 0:
            return 0.0
        elif gap <= 0:
            return 120.0 # "no shortfall (120+)"
        else:
            return round(min(b / gap, 120.0), 1)
            
    baseline_df['baseline_runway'] = [calc_runway(b, g) for b, g in zip(baseline_df['B'], baseline_df['gap'])]
    print("\nBaseline runway distribution:")
    print(baseline_df['baseline_runway'].value_counts(bins=[-0.1, 0, 1, 3, 6, 12, 24, 60, 119.9, 120.1]))
    
    # Accounts with negative buffer
    neg_buffers = (baseline_df['B'] <= 0).sum()
    print(f"\nAccounts with Buffer <= 0: {neg_buffers} ({(neg_buffers/4500)*100:.2f}%)")
    
    # Accounts spending more than income at baseline
    deficit_accounts = (baseline_df['gap'] > 0).sum()
    print(f"Accounts with S > I at baseline: {deficit_accounts} ({(deficit_accounts/4500)*100:.2f}%)")

if __name__ == '__main__':
    test_judging_metrics()
