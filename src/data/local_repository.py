"""
Local Repository: High-Performance Data Ingestion and Query Layer
"""

import os
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List

from config.settings import DATA_DIR

class LocalDataRepository:
    _instance = None

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.accounts: Optional[pd.DataFrame] = None
        self.clients: Optional[pd.DataFrame] = None
        self.dispositions: Optional[pd.DataFrame] = None
        self.cards: Optional[pd.DataFrame] = None
        self.districts: Optional[pd.DataFrame] = None
        self.loans: Optional[pd.DataFrame] = None
        self.standing_orders: Optional[pd.DataFrame] = None
        self.monthly_summary: Optional[pd.DataFrame] = None
        self.transactions: Optional[pd.DataFrame] = None
        
        # Precomputed caches
        self._account_baselines: Optional[pd.DataFrame] = None
        self._analysis_cache: Dict[str, Any] = {}
        self._is_loaded = False

    @classmethod
    def get_instance(cls, data_dir: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = cls(data_dir)
            cls._instance.load_all()
        return cls._instance

    def load_all(self):
        """Loads and indexes all nine relational tables."""
        if self._is_loaded:
            return

        required_files = (
            "accounts.csv",
            "clients.csv",
            "dispositions.csv",
            "cards.csv",
            "districts.csv",
            "loans.csv",
            "standing_orders.csv",
            "monthly_summary.csv",
            "transactions.csv",
        )
        missing = [name for name in required_files if not (self.data_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(
                f"Required dataset file(s) missing from {self.data_dir}: {', '.join(missing)}"
            )

        print(f"Loading datasets from {self.data_dir}...")
        
        # 1. Accounts
        acc_path = self.data_dir / "accounts.csv"
        self.accounts = pd.read_csv(acc_path)
        
        # 2. Clients
        cli_path = self.data_dir / "clients.csv"
        self.clients = pd.read_csv(cli_path)

        # 3. Dispositions
        disp_path = self.data_dir / "dispositions.csv"
        self.dispositions = pd.read_csv(disp_path)

        # 4. Cards
        card_path = self.data_dir / "cards.csv"
        self.cards = pd.read_csv(card_path)

        # 5. Districts
        dist_path = self.data_dir / "districts.csv"
        self.districts = pd.read_csv(dist_path)

        # 6. Loans
        loan_path = self.data_dir / "loans.csv"
        self.loans = pd.read_csv(loan_path)

        # 7. Standing Orders
        so_path = self.data_dir / "standing_orders.csv"
        self.standing_orders = pd.read_csv(so_path)

        # 8. Monthly Summary
        ms_path = self.data_dir / "monthly_summary.csv"
        self.monthly_summary = pd.read_csv(ms_path)
        self._prepare_frames()

        self._is_loaded = True
        print("All base datasets loaded successfully.")

    def _prepare_frames(self):
        """Add derived columns shared by every backend that fills the raw tables."""
        self.clients['birth_date_dt'] = pd.to_datetime(self.clients['birth_date'])
        self.clients['age_2025'] = ((pd.to_datetime('2025-12-31') - self.clients['birth_date_dt']).dt.days / 365.25).round(1)
        # Running at end of 2025 if status C or D
        self.loans['is_running_end_2025'] = self.loans['status'].isin(['C', 'D'])
        self.monthly_summary['fixed_costs_row'] = (
            self.monthly_summary['household_bills'] +
            self.monthly_summary['insurance'] +
            self.monthly_summary['loan_payments']
        )
        self.monthly_summary = self.monthly_summary.sort_values(['account_id', 'month'])

    def get_monthly_summary(self, account_id: int) -> pd.DataFrame:
        """Returns sorted monthly summary rows for a specific account."""
        if not self._is_loaded:
            self.load_all()
        return self.monthly_summary[self.monthly_summary['account_id'] == account_id].copy()

    def get_transactions(self, account_id: int) -> pd.DataFrame:
        """Lazy loads transactions for a specific account to optimize memory."""
        tx_path = self.data_dir / "transactions.csv"
        # If full table loaded, filter; otherwise stream or read with chunking/filter
        if self.transactions is not None:
            return self.transactions[self.transactions['account_id'] == account_id].copy()
        
        # Read with filter
        # Since transactions.csv is ~98MB, reading with pyarrow is fast (<1 sec)
        tx = pd.read_csv(tx_path, low_memory=False)
        return tx[tx['account_id'] == account_id].copy()

    def get_account_meta(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Returns customer ownership, branch, and demographic context."""
        if not self._is_loaded:
            self.load_all()
            
        acc_row = self.accounts[self.accounts['account_id'] == account_id]
        if acc_row.empty:
            return None
        acc_dict = acc_row.iloc[0].to_dict()

        # Primary Owner Disposition
        owner_disp = self.dispositions[
            (self.dispositions['account_id'] == account_id) & 
            (self.dispositions['type'] == 'owner')
        ]
        if not owner_disp.empty:
            owner_id = owner_disp.iloc[0]['client_id']
            disp_id = owner_disp.iloc[0]['disposition_id']
            acc_dict['owner_client_id'] = owner_id
            acc_dict['disposition_id'] = disp_id
            
            # Client details
            cli_row = self.clients[self.clients['client_id'] == owner_id]
            if not cli_row.empty:
                cli = cli_row.iloc[0]
                acc_dict['owner_gender'] = cli['gender']
                acc_dict['owner_age'] = cli['age_2025']
                acc_dict['home_district_id'] = cli['district_id']

            # Card details
            card_row = self.cards[self.cards['disposition_id'] == disp_id]
            if not card_row.empty:
                acc_dict['has_card'] = True
                acc_dict['card_type'] = card_row.iloc[0]['card_type']
                acc_dict['card_issued'] = card_row.iloc[0]['issued']
            else:
                acc_dict['has_card'] = False
                acc_dict['card_type'] = 'No Card'
                acc_dict['card_issued'] = None
        else:
            acc_dict['owner_client_id'] = None
            acc_dict['has_card'] = False
            acc_dict['card_type'] = 'No Card'

        # Authorized users are account-access roles, not relationship labels.
        users = self.dispositions[
            (self.dispositions['account_id'] == account_id) & 
            (self.dispositions['type'] == 'authorized user')
        ]
        acc_dict['has_authorized_user'] = not users.empty
        acc_dict['authorized_user_count'] = len(users)

        # Branch District Details
        branch_dist = self.districts[self.districts['district_id'] == acc_dict['district_id']]
        if not branch_dist.empty:
            acc_dict['branch_district_name'] = branch_dist.iloc[0]['district_name']
            acc_dict['branch_region'] = branch_dist.iloc[0]['region']
            acc_dict['branch_avg_salary'] = branch_dist.iloc[0]['average_salary']
            acc_dict['branch_unemployment_2023'] = branch_dist.iloc[0]['unemployment_rate_2023']

        # Loan Details
        loan_row = self.loans[self.loans['account_id'] == account_id]
        if not loan_row.empty:
            lr = loan_row.iloc[0]
            acc_dict['has_loan'] = True
            acc_dict['loan_id'] = lr['loan_id']
            acc_dict['loan_amount'] = lr['amount']
            acc_dict['loan_duration_months'] = lr['duration_months']
            acc_dict['loan_monthly_payment'] = lr['monthly_payment']
            acc_dict['loan_status'] = lr['status']
            acc_dict['loan_status_meaning'] = lr['status_meaning']
            acc_dict['loan_defaulted'] = lr['defaulted']
            acc_dict['loan_is_running_2025'] = lr['is_running_end_2025']
        else:
            acc_dict['has_loan'] = False
            acc_dict['loan_monthly_payment'] = 0.0
            acc_dict['loan_status'] = 'None'
            acc_dict['loan_is_running_2025'] = False

        # Standing Orders
        so_rows = self.standing_orders[self.standing_orders['account_id'] == account_id]
        acc_dict['standing_orders_count'] = len(so_rows)
        acc_dict['standing_orders_total'] = so_rows['amount'].sum() if not so_rows.empty else 0.0
        acc_dict['has_leasing_labelled_order'] = (
            (so_rows['purpose'] == 'leasing').any() if not so_rows.empty else False
        )

        return acc_dict

    def get_all_accounts(self) -> List[int]:
        """Returns a list of all 4,500 account IDs."""
        if not self._is_loaded:
            self.load_all()
        return sorted(self.accounts['account_id'].unique().tolist())

    def get_portfolio_account_metrics(self) -> pd.DataFrame:
        """Return cached shared account-level metrics for the loaded monthly table."""
        if not self._is_loaded:
            self.load_all()
        if self._account_baselines is None:
            from src.services.baseline_metrics import compute_portfolio_account_metrics

            self._account_baselines = compute_portfolio_account_metrics(self.monthly_summary)
        return self._account_baselines.copy()
