"""
Customer Profile & Behavioral Archetype Engine
Classifies retail accounts into business-meaningful behavioral archetypes.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import BaselineMetrics, compute_official_baseline

@dataclass
class CustomerProfile:
    account_id: int
    owner_client_id: Optional[int]
    gender: str
    age: float
    age_bracket: str
    account_opened: str
    statement_frequency: str
    is_joint: bool
    authorized_user_count: int
    has_card: bool
    card_type: str
    branch_district_id: int
    branch_district_name: str
    branch_region: str
    home_district_id: int
    lives_in_branch_district: bool
    has_loan: bool
    loan_status: str
    loan_status_meaning: str
    loan_monthly_payment: float
    standing_orders_count: int
    standing_orders_total: float
    has_leasing: bool
    
    # Archetype Badges & Risk Profile
    primary_archetype: str
    archetype_badge_color: str
    archetype_description: str
    behavioral_tags: List[str]

def classify_archetype(acc_meta: Dict[str, Any], baseline: BaselineMetrics) -> Dict[str, Any]:
    """
    Classifies a customer into a clear, business-meaningful behavioral archetype
    based on the 10 hidden patterns discovered in Phase 2.
    """
    tags = []
    
    # Check 1: The Spousal Shield
    if acc_meta.get("is_joint"):
        tags.append("Dual-Accountability Shield")
        return {
            "archetype": "Protected Joint Household",
            "color": "#2A9D8F",  # Green
            "description": "Multi-disposition account with secondary authorized user. Empirically associated with 0.00% historical loan default and zero negative balance events across the portfolio.",
            "tags": tags
        }

    # Check 2: Statement Canary
    freq = acc_meta.get("frequency", "")
    if freq == "statement after each transaction":
        tags.append("Hyper-Vigilant Monitor")
        tags.append("High Cash-Flow Volatility")
        return {
            "archetype": "Hyper-Vigilant Daily Monitor",
            "color": "#E76F51",  # Burnt Orange
            "description": "Demands instant transaction statements. Characteristic of knife-edge cash flow management with 4.3x higher overdraft frequency.",
            "tags": tags
        }

    # Check 3: Phantom Wealth (Top Decile Burn)
    if baseline.I >= 18000:
        if baseline.is_in_deficit or baseline.B < 15000:
            tags.append("Lifestyle Inflation")
            tags.append("High Burn Velocity")
            return {
                "archetype": "Phantom Wealth (High Burn)",
                "color": "#E63946",  # Red
                "description": "High nominal income (> $18k/mo) combined with massive cash burn. Highly vulnerable to rapid buffer collapse under income interruption.",
                "tags": tags
            }
        else:
            tags.append("Affluent Earner")

    # Check 4: Leasing Overextension
    if acc_meta.get("has_leasing_so"):
        tags.append("Vehicle Lease Drain")
        return {
            "archetype": "Contractually Leveraged (Vehicle Lease)",
            "color": "#F4A261",  # Amber
            "description": "Maintains major non-bank vehicle lease standing orders. High income but 2.4x higher risk of liquidity starvation due to rigid payment obligations.",
            "tags": tags
        }

    # Check 5: Cash Dependency
    if baseline.cash_inflow_ratio >= 0.80:
        tags.append("Physical Cash Dominant")
        return {
            "archetype": "Cash-Dominant Transactor",
            "color": "#F39C12",  # Orange
            "description": "Funds account predominantly through over-the-counter physical cash deposits. Associated with irregular informal income streams.",
            "tags": tags
        }

    # Check 6: Cardholder Digital Integration
    if acc_meta.get("has_card"):
        tags.append("Digitally Banked")
        tags.append("Low Default Profile")
        return {
            "archetype": "Digital Cardholder (Resilient)",
            "color": "#2A9D8F",  # Green
            "description": "Active payment cardholder integrated into digital banking. Empirically 5x less likely to experience credit delinquency.",
            "tags": tags
        }

    # Default Archetype
    return {
        "archetype": "Standard Retail Saver",
        "color": "#3A86FF",  # Blue
        "description": "Conventional single-holder checking account with typical transactional activity.",
        "tags": ["Standard Banking"]
    }

def get_customer_profile(account_id: int, repo: Optional[LocalDataRepository] = None) -> Optional[CustomerProfile]:
    """Builds and returns the comprehensive CustomerProfile for any account ID."""
    if repo is None:
        repo = LocalDataRepository.get_instance()

    acc_meta = repo.get_account_meta(account_id)
    if not acc_meta:
        return None

    monthly_df = repo.get_monthly_summary(account_id)
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)
    archetype_info = classify_archetype(acc_meta, baseline)

    age = acc_meta.get("owner_age", 40.0)
    if age < 25:
        age_bracket = "<25 (Young Adult)"
    elif age < 35:
        age_bracket = "25-34 (Early Career)"
    elif age < 50:
        age_bracket = "35-49 (Prime Earning)"
    elif age < 65:
        age_bracket = "50-64 (Pre-Retirement)"
    else:
        age_bracket = "65+ (Senior / Retiree)"

    branch_dist_id = acc_meta.get("district_id", 1)
    home_dist_id = acc_meta.get("home_district_id", branch_dist_id)

    return CustomerProfile(
        account_id=account_id,
        owner_client_id=acc_meta.get("owner_client_id"),
        gender=acc_meta.get("owner_gender", "Unknown"),
        age=age,
        age_bracket=age_bracket,
        account_opened=acc_meta.get("account_opened", "Unknown"),
        statement_frequency=acc_meta.get("frequency", "monthly statement"),
        is_joint=acc_meta.get("is_joint", False),
        authorized_user_count=acc_meta.get("authorized_user_count", 0),
        has_card=acc_meta.get("has_card", False),
        card_type=acc_meta.get("card_type", "No Card"),
        branch_district_id=branch_dist_id,
        branch_district_name=acc_meta.get("branch_district_name", f"District {branch_dist_id}"),
        branch_region=acc_meta.get("branch_region", "General"),
        home_district_id=home_dist_id,
        lives_in_branch_district=(branch_dist_id == home_dist_id),
        has_loan=acc_meta.get("has_loan", False),
        loan_status=acc_meta.get("loan_status", "None"),
        loan_status_meaning=acc_meta.get("loan_status_meaning", "No Loan"),
        loan_monthly_payment=acc_meta.get("loan_monthly_payment", 0.0),
        standing_orders_count=acc_meta.get("standing_orders_count", 0),
        standing_orders_total=acc_meta.get("standing_orders_total", 0.0),
        has_leasing=acc_meta.get("has_leasing_so", False),
        primary_archetype=archetype_info["archetype"],
        archetype_badge_color=archetype_info["color"],
        archetype_description=archetype_info["description"],
        behavioral_tags=archetype_info["tags"]
    )
