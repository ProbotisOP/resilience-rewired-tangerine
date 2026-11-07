"""
Recovery & Backup Planning Engine: Personalized Goals & Emergency Action Plans
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import math
import pandas as pd

from src.services.baseline_metrics import BaselineMetrics
from src.services.shock_engine import ShockResult

@dataclass
class GoalPlan:
    target_months: int
    essential_monthly_cost: float
    is_f_unobserved: bool
    emergency_target: float
    current_buffer: float
    funding_gap: float
    is_target_met: bool
    historical_savings_capacity: float
    months_to_goal: Optional[int]
    recommended_monthly_deposit: float
    plan_explanation: str

@dataclass
class BackupAction:
    priority: int
    action_type: str  # "Discretionary Cash Compression", "Contract Review", "Debt Relief"
    title: str
    description: str
    monthly_dollar_impact: float
    is_immediate: bool

@dataclass
class BackupPlan:
    monthly_shortfall: float
    required_monthly_cut: float
    buffer_after_one_off: float
    actions: List[BackupAction]
    total_mitigation_capacity: float
    deficit_fully_covered: bool
    post_mitigation_gap: float
    post_mitigation_runway: float

def build_goal_plan(
    baseline: BaselineMetrics,
    target_months: int = 3,
    custom_monthly_savings: Optional[float] = None
) -> GoalPlan:
    """
    Constructs an emergency fund goal plan:
    - Target = target_months * essential_monthly_cost
    - Essential cost proxy is F (bills + insurance + loan payments) when F > 0.
    """
    # Essential cost proxy
    is_f_zero = (baseline.F <= 0)
    essential_cost = baseline.F if not is_f_zero else max(baseline.H, baseline.S * 0.35)

    emergency_target = round(target_months * essential_cost, 2)
    funding_gap = round(max(0.0, emergency_target - baseline.B), 2)
    target_met = (funding_gap <= 0)

    # Historical savings capacity from visible cash flows (median I - S)
    hist_capacity = max(0.0, baseline.I - baseline.S)

    chosen_savings = custom_monthly_savings if custom_monthly_savings is not None else hist_capacity

    months_to_goal: Optional[int] = None
    if target_met:
        months_to_goal = 0
        explanation = f"Customer already holds ${baseline.B:,.2f} CAD, exceeding the {target_months}-month essential reserve target (${emergency_target:,.2f} CAD)."
    elif chosen_savings > 0:
        months_to_goal = math.ceil(funding_gap / chosen_savings)
        explanation = f"Target can be reached in {months_to_goal} months by allocating ${chosen_savings:,.2f} CAD monthly to a dedicated resilience reserve."
    else:
        months_to_goal = None
        explanation = "Historical cash flow shows neutral or negative savings capacity. Discretionary spending adjustments are required to begin funding the reserve."

    return GoalPlan(
        target_months=target_months,
        essential_monthly_cost=round(essential_cost, 2),
        is_f_unobserved=is_f_zero,
        emergency_target=emergency_target,
        current_buffer=baseline.B,
        funding_gap=funding_gap,
        is_target_met=target_met,
        historical_savings_capacity=round(hist_capacity, 2),
        months_to_goal=months_to_goal,
        recommended_monthly_deposit=round(chosen_savings, 2),
        plan_explanation=explanation
    )

def build_backup_plan(
    baseline: BaselineMetrics,
    shock_result: ShockResult,
    account_meta: Optional[Dict[str, Any]] = None
) -> BackupPlan:
    """
    Generates a personalized, hierarchical emergency backup plan to eliminate the post-shock shortfall:
    1. Cash withdrawal compression (discretionary cash outflow reduction).
    2. Standing order review / pause non-essential mandates.
    3. Loan relief / temporary payment deferral (if active loan running).
    """
    shortfall = max(0.0, shock_result.monthly_gap)
    actions: List[BackupAction] = []
    
    # Lever 1: Discretionary cash compression (76% of outflow is cash withdrawals)
    # Estimate typical monthly discretionary cash: S - F
    discretionary_spend = max(0.0, shock_result.spending_after_shock - baseline.F)
    
    # 25% cash compression
    cut_25 = round(discretionary_spend * 0.25, 2)
    if cut_25 > 0:
        actions.append(BackupAction(
            priority=1,
            action_type="Discretionary Cash Compression",
            title="Austerity Cash Withdrawal Cap (25% Reduction)",
            description=f"Cap over-the-counter and ATM cash withdrawals by 25%. This preserves liquidity without impacting contractual fixed bills or rent.",
            monthly_dollar_impact=cut_25,
            is_immediate=True
        ))

    # 40% cash compression
    cut_additional_15 = round(discretionary_spend * 0.15, 2)
    if cut_additional_15 > 0:
        actions.append(BackupAction(
            priority=2,
            action_type="Deep Discretionary Pause",
            title="Deep Non-Essential Spending Freeze (Additional 15%)",
            description="Pause discretionary card purchases and secondary unlabelled transfers during the emergency period.",
            monthly_dollar_impact=cut_additional_15,
            is_immediate=True
        ))

    # Lever 2: Review standing orders
    if account_meta and account_meta.get("has_leasing_so"):
        actions.append(BackupAction(
            priority=3,
            action_type="Contract Restructuring",
            title="Vehicle Lease Restructuring / Sublease",
            description="Active vehicle leasing standing order detected. Request temporary lease payment deferral or restructuring from lease provider.",
            monthly_dollar_impact=round(account_meta.get("standing_orders_total", 0.0) * 0.3, 2),
            is_immediate=False
        ))

    # Lever 3: Loan Payment Deferral (if active running loan)
    if baseline.has_running_loan and baseline.P > 0:
        actions.append(BackupAction(
            priority=4,
            action_type="Credit Facility Relief",
            title="Tangerine Emergency Loan Payment Deferral",
            description=f"Apply for a 3-month temporary principal/payment forbearance on active loan #{account_meta.get('loan_id', '')} (${baseline.P:,.2f}/mo).",
            monthly_dollar_impact=baseline.P,
            is_immediate=True
        ))

    # Mitigation calculations
    total_mitigation = sum(a.monthly_dollar_impact for a in actions)
    post_gap = max(0.0, shortfall - total_mitigation)
    fully_covered = (total_mitigation >= shortfall)

    # Post-mitigation runway
    if shock_result.buffer_left <= 0:
        post_runway = 0.0
    elif post_gap <= 0:
        post_runway = 120.0
    else:
        post_runway = round(min(shock_result.buffer_left / post_gap, 120.0), 1)

    return BackupPlan(
        monthly_shortfall=shortfall,
        required_monthly_cut=shortfall,
        buffer_after_one_off=shock_result.buffer_left,
        actions=actions,
        total_mitigation_capacity=round(total_mitigation, 2),
        deficit_fully_covered=fully_covered,
        post_mitigation_gap=round(post_gap, 2),
        post_mitigation_runway=post_runway
    )
