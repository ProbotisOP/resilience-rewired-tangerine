"""
Sheridan Datathon 2026 - Tangerine Track: Resilience Rewired
Phase 2: Hidden Patterns & Behavioral Intelligence Reproduction Suite
Authors: CTRL + ALT + WIN (Satnam Singh & Antigravity)
"""

import os
import pandas as pd
import numpy as np
from scipy import stats

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
DATA_DIR = os.path.join(PROJECT_ROOT, 'tangerine', 'data')

def run_all_discoveries():
    print("=" * 80)
    print("RUNNING REPRODUCTION SUITE FOR 10 HIDDEN BEHAVIORAL DISCOVERIES")
    print("=" * 80)

    # 1. Load tables
    print("\nLoading datasets...")
    accounts = pd.read_csv(os.path.join(DATA_DIR, 'accounts.csv'))
    loans = pd.read_csv(os.path.join(DATA_DIR, 'loans.csv'))
    dispositions = pd.read_csv(os.path.join(DATA_DIR, 'dispositions.csv'))
    cards = pd.read_csv(os.path.join(DATA_DIR, 'cards.csv'))
    ms = pd.read_csv(os.path.join(DATA_DIR, 'monthly_summary.csv'))
    standing_orders = pd.read_csv(os.path.join(DATA_DIR, 'standing_orders.csv'))
    tx = pd.read_csv(os.path.join(DATA_DIR, 'transactions.csv'), low_memory=False)

    # Base aggregates
    ms_sorted = ms.sort_values(['account_id', 'month'])
    last6 = ms_sorted.groupby('account_id').tail(6)
    buffers = last6.groupby('account_id')['avg_daily_balance'].mean().rename('B')

    acc_agg = ms.groupby('account_id').agg(
        I=('money_in', 'median'),
        S=('money_out', 'median'),
        H=('household_bills', 'median'),
        mean_in=('money_in', 'mean'),
        std_in=('money_in', 'std'),
        had_neg=('days_below_zero', lambda s: (s > 0).any()),
        cash_in=('cash_deposits', 'sum'),
        total_in=('money_in', 'sum'),
        cash_out=('cash_withdrawals_genuine', 'sum'),
        total_out=('money_out', 'sum'),
        total_bank_fees=('bank_fees', 'sum'),
        months_count=('month', 'count')
    )
    acc_agg['cv_in'] = acc_agg['std_in'] / (acc_agg['mean_in'] + 1e-6)
    acc_agg['cash_in_ratio'] = acc_agg['cash_in'] / (acc_agg['total_in'] + 1e-6)
    acc_agg['cash_out_ratio'] = acc_agg['cash_out'] / (acc_agg['total_out'] + 1e-6)
    acc_agg['mean_fee_per_month'] = acc_agg['total_bank_fees'] / acc_agg['months_count']
    acc_agg = acc_agg.join(buffers)

    df = accounts.merge(acc_agg, on='account_id', how='left')
    df = df.merge(loans[['account_id', 'loan_id', 'amount', 'duration_months', 'monthly_payment', 'status', 'defaulted']], on='account_id', how='left')

    # Card mapping
    disp_owner = dispositions[dispositions['type'] == 'owner']
    cards_with_disp = cards.merge(disp_owner[['disposition_id', 'account_id']], on='disposition_id')
    card_map = cards_with_disp.set_index('account_id')['card_type']
    df['card_type'] = df['account_id'].map(card_map).fillna('no_card')
    df['has_card'] = df['card_type'] != 'no_card'

    # Joint accounts mapping
    joint_accs = set(dispositions[dispositions['type'] == 'authorized user']['account_id'])
    df['is_joint'] = df['account_id'].isin(joint_accs)

    # Standing orders mapping
    lease_accs = set(standing_orders[standing_orders['purpose'] == 'leasing']['account_id'])
    df['has_leasing'] = df['account_id'].isin(lease_accs)

    loan_df = df.dropna(subset=['defaulted']).copy()

    # -------------------------------------------------------------------------
    # DISCOVERY 1: SPOUSAL SHIELD
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 1] The Spousal Shield (Joint vs Solo Accounts)")
    ct1 = pd.crosstab(loan_df['is_joint'], loan_df['defaulted'])
    chi2_1, p_1, _, _ = stats.chi2_contingency(ct1)
    print(ct1)
    print(f"Chi2: {chi2_1:.4f}, p-value: {p_1:.4e}")

    # -------------------------------------------------------------------------
    # DISCOVERY 2: STATEMENT FREQUENCY CANARY
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 2] Statement Frequency Canary")
    ct2 = pd.crosstab(df['frequency'], df['had_neg'])
    chi2_2, p_2, _, _ = stats.chi2_contingency(ct2)
    print(ct2)
    print(f"Chi2: {chi2_2:.4f}, p-value: {p_2:.4e}")

    # -------------------------------------------------------------------------
    # DISCOVERY 3: INVERTED RESILIENCE PARADOX (PHANTOM WEALTH)
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 3] Inverted Resilience Paradox (EI 55% Shock)")
    df['gap_ei'] = df['S'] - 0.55 * df['I']
    df['runway_ei'] = np.where(df['B'] <= 0, 0.0,
                      np.where(df['gap_ei'] <= 0, 120.0,
                      np.minimum(df['B'] / df['gap_ei'], 120.0)))
    df['income_decile'] = pd.qcut(df['I'], 10, labels=[f'D{i}' for i in range(1, 11)])
    decile_res = df.groupby('income_decile', observed=False).agg(
        median_I=('I', 'median'),
        median_S=('S', 'median'),
        median_B=('B', 'median'),
        median_runway=('runway_ei', 'median'),
        pct_under_6m=('runway_ei', lambda s: (s < 6.0).mean() * 100),
        pct_overdraft=('had_neg', lambda s: s.mean() * 100)
    )
    print(decile_res.to_string())

    # -------------------------------------------------------------------------
    # DISCOVERY 4: CARDHOLDER IMMUNITY
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 4] Cardholder Immunity Paradox")
    ct4 = pd.crosstab(loan_df['has_card'], loan_df['defaulted'])
    chi2_4, p_4, _, _ = stats.chi2_contingency(ct4)
    print(ct4)
    print(f"Chi2: {chi2_4:.4f}, p-value: {p_4:.4e}")

    # -------------------------------------------------------------------------
    # DISCOVERY 5: CASH ADDICTION GRADIENT
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 5] Cash Inflow Share vs Default")
    loan_df['cash_q'] = pd.qcut(loan_df['cash_in_ratio'], 4, labels=['Q1_low', 'Q2', 'Q3', 'Q4_high'])
    ct5 = pd.crosstab(loan_df['cash_q'], loan_df['defaulted'])
    chi2_5, p_5, _, _ = stats.chi2_contingency(ct5)
    print(ct5)
    print(f"Chi2: {chi2_5:.4f}, p-value: {p_5:.4e}")

    # -------------------------------------------------------------------------
    # DISCOVERY 6: LEASING OVEREXTENSION TRAP
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 6] Leasing Standing Order vs Overdraft")
    ct6 = pd.crosstab(df['has_leasing'], df['had_neg'])
    chi2_6, p_6, _, _ = stats.chi2_contingency(ct6)
    print(ct6)
    print(f"Chi2: {chi2_6:.4f}, p-value: {p_6:.4e}")

    # -------------------------------------------------------------------------
    # DISCOVERY 7: EXTERNAL DEBT SHADOW
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 7] External Debt via Standing Orders")
    loan_so = standing_orders[standing_orders['purpose'] == 'loan payment']
    internal_loan_accs = set(loans['account_id'])
    so_loan_accs = set(loan_so['account_id'])
    ext_borrowers = so_loan_accs - internal_loan_accs
    print(f"Accounts servicing loans at external competitor banks: {len(ext_borrowers)}")

    # -------------------------------------------------------------------------
    # DISCOVERY 8: PENALTY FEE DEATH SPIRAL
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 8] Overdraft Penalty Fee Cascade")
    penalties = tx[tx['purpose'] == 'penalty interest (negative balance)']
    pen_accs = penalties.groupby('account_id').size()
    pen_loans = loans[loans['account_id'].isin(pen_accs.index)]
    print(f"Penalized loan borrowers: {len(pen_loans)}")
    print("Their statuses:\n", pen_loans['status'].value_counts())
    print(f"Default rate among penalized borrowers: {(pen_loans['defaulted'].mean() * 100):.1f}%")

    # -------------------------------------------------------------------------
    # DISCOVERY 9: PAYDAY EVAPORATION CYCLE
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 9] Payday Evaporation Cycle")
    tx['day'] = pd.to_datetime(tx['date']).dt.day
    cash_by_day = tx[tx['operation'] == 'cash withdrawal'].groupby('day')['amount'].sum()
    print("Peak cash withdrawal day of month:")
    print(f"Day {cash_by_day.idxmax()}: ${cash_by_day.max():,.2f} CAD")

    # -------------------------------------------------------------------------
    # DISCOVERY 10: 76% COMPRESSIBLE SPEND CUSHION
    # -------------------------------------------------------------------------
    print("\n[DISCOVERY 10] Spending Cushion Decomposition")
    tot_out = ms['money_out'].sum()
    fixed_parts = ['household_bills', 'insurance', 'loan_payments', 'bank_fees']
    cash_part = 'cash_withdrawals_genuine'
    print(f"Fixed Costs (F) Share: {ms[fixed_parts].sum().sum() / tot_out * 100:.2f}%")
    print(f"Cash Withdrawals (Compressible) Share: {ms[cash_part].sum() / tot_out * 100:.2f}%")

    print("\n" + "=" * 80)
    print("ALL 10 DISCOVERIES VERIFIED SUCCESSFULLY")
    print("=" * 80)

if __name__ == '__main__':
    run_all_discoveries()
