"""Customer profile and neutral indicators from observed account fields."""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import BaselineMetrics, compute_official_baseline

@dataclass
class CustomerProfile:
    account_id: int
    owner_client_id: Optional[int]
    gender: str
    age: Optional[float]
    age_bracket: str
    account_opened: str
    statement_frequency: str
    has_authorized_user: bool
    authorized_user_count: int
    has_card: bool
    card_type: str
    branch_district_id: Optional[int]
    branch_district_name: str
    branch_region: str
    home_district_id: Optional[int]
    lives_in_branch_district: bool
    has_loan: bool
    loan_status: str
    loan_status_meaning: str
    loan_monthly_payment: float
    standing_orders_count: int
    standing_orders_total: float
    has_leasing_labelled_order: bool
    primary_indicator: str
    indicator_description: str
    observed_indicators: List[str]

def identify_observed_indicators(
    acc_meta: Dict[str, Any], baseline: BaselineMetrics
) -> List[str]:
    """Return neutral fields observed in the supplied tables, not inferred traits."""
    indicators: List[str] = []
    authorized_users = int(acc_meta.get("authorized_user_count", 0))
    if authorized_users:
        indicators.append(f"{authorized_users} authorized user(s) listed")
    if acc_meta.get("frequency") == "statement after each transaction":
        indicators.append("Per-transaction statement frequency")
    if baseline.is_in_deficit:
        indicators.append("Median monthly spending exceeds median money-in")
    if baseline.cash_inflow_ratio >= 0.80:
        indicators.append("High cash-deposit share of recorded money-in")
    if acc_meta.get("has_leasing_labelled_order"):
        indicators.append("Leasing-labelled standing order in snapshot")
    if acc_meta.get("has_card"):
        indicators.append("Card recorded on owner disposition")
    return indicators

def get_customer_profile(
    account_id: int,
    repo: Optional[LocalDataRepository] = None,
    *,
    account_meta: Optional[Dict[str, Any]] = None,
    baseline: Optional[BaselineMetrics] = None,
) -> Optional[CustomerProfile]:
    """Builds and returns the comprehensive CustomerProfile for any account ID."""
    if repo is None:
        repo = LocalDataRepository.get_instance()

    acc_meta = account_meta if account_meta is not None else repo.get_account_meta(account_id)
    if not acc_meta:
        return None

    if baseline is None:
        monthly_df = repo.get_monthly_summary(account_id)
        baseline = compute_official_baseline(account_id, monthly_df, acc_meta)
    indicators = identify_observed_indicators(acc_meta, baseline)

    age = acc_meta.get("owner_age")
    if age is None:
        age_bracket = "Unavailable"
    elif age < 25:
        age_bracket = "Under 25"
    elif age < 35:
        age_bracket = "25-34"
    elif age < 50:
        age_bracket = "35-49"
    elif age < 65:
        age_bracket = "50-64"
    else:
        age_bracket = "65+"

    branch_dist_id = acc_meta.get("district_id")
    home_dist_id = acc_meta.get("home_district_id")

    return CustomerProfile(
        account_id=account_id,
        owner_client_id=acc_meta.get("owner_client_id"),
        gender=acc_meta.get("owner_gender", "Unknown"),
        age=age,
        age_bracket=age_bracket,
        account_opened=acc_meta.get("account_opened", "Unknown"),
        statement_frequency=acc_meta.get("frequency", "monthly statement"),
        has_authorized_user=acc_meta.get("has_authorized_user", False),
        authorized_user_count=acc_meta.get("authorized_user_count", 0),
        has_card=acc_meta.get("has_card", False),
        card_type=acc_meta.get("card_type", "No Card"),
        branch_district_id=branch_dist_id,
        branch_district_name=acc_meta.get("branch_district_name", "Unavailable"),
        branch_region=acc_meta.get("branch_region", "Unavailable"),
        home_district_id=home_dist_id,
        lives_in_branch_district=(
            branch_dist_id == home_dist_id
            if branch_dist_id is not None and home_dist_id is not None
            else False
        ),
        has_loan=acc_meta.get("has_loan", False),
        loan_status=acc_meta.get("loan_status", "None"),
        loan_status_meaning=acc_meta.get("loan_status_meaning", "No Loan"),
        loan_monthly_payment=acc_meta.get("loan_monthly_payment", 0.0),
        standing_orders_count=acc_meta.get("standing_orders_count", 0),
        standing_orders_total=acc_meta.get("standing_orders_total", 0.0),
        has_leasing_labelled_order=acc_meta.get("has_leasing_labelled_order", False),
        primary_indicator=indicators[0] if indicators else "No additional indicator",
        indicator_description=(
            "Observed data fields only; these indicators are not personality labels, "
            "risk classifications or causal explanations."
        ),
        observed_indicators=indicators,
    )
