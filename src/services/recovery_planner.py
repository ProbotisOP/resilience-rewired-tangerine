"""Customer-controlled resilience goal and monthly cash-flow simulations."""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import math
import pandas as pd

from src.services.baseline_metrics import BaselineMetrics, calculate_runway
from src.services.shock_engine import ShockResult


@dataclass
class GoalPlan:
    target_months: int
    essential_monthly_cost: Optional[float]
    is_f_unobserved: bool
    emergency_target: Optional[float]
    current_buffer: float
    funding_gap: Optional[float]
    is_target_met: Optional[bool]
    recent_six_month_median_net_cash_flow: Optional[float]
    months_to_goal: Optional[int]
    recommended_monthly_deposit: float
    plan_explanation: str


@dataclass
class BackupAction:
    priority: int
    action_type: str
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


@dataclass
class ResilienceGapPlan:
    current_monthly_gap: float
    available_buffer: float
    target_months: int
    required_monthly_improvement: float
    selected_monthly_adjustment: float
    proposed_monthly_gap: float
    current_runway_months: float
    proposed_runway_months: float


def recent_six_month_median_net_cash_flow(
    monthly_rows: pd.DataFrame,
) -> Optional[float]:
    """Return median money-in minus money-out across up to six supplied rows."""
    if monthly_rows.empty or not {"money_in", "money_out"}.issubset(monthly_rows.columns):
        return None
    return float((monthly_rows["money_in"] - monthly_rows["money_out"]).median())


def build_goal_plan(
    baseline: BaselineMetrics,
    target_months: int = 3,
    custom_monthly_savings: Optional[float] = None,
    essential_monthly_cost: Optional[float] = None,
) -> GoalPlan:
    """Build a reserve target without inventing essential costs or savings."""
    if target_months <= 0:
        raise ValueError("target_months must be positive")

    essential_cost = essential_monthly_cost
    if essential_cost is None and baseline.F > 0:
        essential_cost = baseline.F
    if essential_cost is not None and essential_cost <= 0:
        raise ValueError("essential_monthly_cost must be positive when provided")

    recent = baseline.last_6_months_summary
    recent_median_net_flow = recent_six_month_median_net_cash_flow(recent)

    emergency_target = (
        round(target_months * essential_cost, 2) if essential_cost is not None else None
    )
    funding_gap = (
        round(max(0.0, emergency_target - baseline.B), 2)
        if emergency_target is not None
        else None
    )
    target_met = funding_gap <= 0 if funding_gap is not None else None
    visible_capacity = max(0.0, recent_median_net_flow or 0.0)
    chosen_savings = (
        max(0.0, float(custom_monthly_savings))
        if custom_monthly_savings is not None
        else visible_capacity
    )

    if emergency_target is None:
        months_to_goal = None
        explanation = (
            "Typical fixed costs are zero or unavailable. Enter a customer-confirmed "
            "essential monthly cost to calculate a reserve target."
        )
    elif target_met:
        months_to_goal = 0
        explanation = (
            f"The selected buffer of ${baseline.B:,.2f} CAD meets the "
            f"{target_months}-month target of ${emergency_target:,.2f} CAD."
        )
    elif chosen_savings > 0:
        months_to_goal = math.ceil(funding_gap / chosen_savings)
        explanation = (
            f"At the selected ${chosen_savings:,.2f} CAD monthly contribution, "
            f"the target gap is estimated to take {months_to_goal} months."
        )
    else:
        months_to_goal = None
        explanation = (
            "No positive contribution is selected or visible in recent net cash flow. "
            "A customer-selected adjustment is needed to model a savings path."
        )

    return GoalPlan(
        target_months=target_months,
        essential_monthly_cost=(
            round(essential_cost, 2) if essential_cost is not None else None
        ),
        is_f_unobserved=baseline.F <= 0,
        emergency_target=emergency_target,
        current_buffer=baseline.B,
        funding_gap=funding_gap,
        is_target_met=target_met,
        recent_six_month_median_net_cash_flow=(
            round(recent_median_net_flow, 2)
            if recent_median_net_flow is not None
            else None
        ),
        months_to_goal=months_to_goal,
        recommended_monthly_deposit=round(chosen_savings, 2),
        plan_explanation=explanation,
    )


def build_resilience_gap_plan(
    buffer: float,
    monthly_gap: float,
    target_months: int,
    selected_monthly_adjustment: float = 0.0,
) -> ResilienceGapPlan:
    """Calculate the adjustment needed for a selected duration, without category assumptions."""
    if target_months <= 0:
        raise ValueError("target_months must be positive")
    if selected_monthly_adjustment < 0:
        raise ValueError("selected_monthly_adjustment cannot be negative")

    required = max(0.0, monthly_gap - buffer / target_months)
    proposed_gap = monthly_gap - selected_monthly_adjustment
    return ResilienceGapPlan(
        current_monthly_gap=round(monthly_gap, 2),
        available_buffer=round(buffer, 2),
        target_months=target_months,
        required_monthly_improvement=round(required, 2),
        selected_monthly_adjustment=round(selected_monthly_adjustment, 2),
        proposed_monthly_gap=round(proposed_gap, 2),
        current_runway_months=calculate_runway(buffer, monthly_gap),
        proposed_runway_months=calculate_runway(buffer, proposed_gap),
    )


def build_backup_plan(
    baseline: BaselineMetrics,
    shock_result: ShockResult,
    account_meta: Optional[Dict[str, Any]] = None,
) -> BackupPlan:
    """List options to investigate; no savings or payment relief is presumed."""
    shortfall = max(0.0, shock_result.monthly_gap)
    actions: List[BackupAction] = []

    if account_meta and account_meta.get("has_leasing_labelled_order"):
        actions.append(
            BackupAction(
                priority=1,
                action_type="Standing-order review",
                title="Review the leasing-labelled standing order",
                description=(
                    "Confirm the payee, current amount, frequency and whether a contract "
                    "exists. A standing-order label is not proof of a current monthly obligation."
                ),
                monthly_dollar_impact=0.0,
                is_immediate=False,
            )
        )

    if baseline.has_running_loan and baseline.P > 0:
        actions.append(
            BackupAction(
                priority=len(actions) + 1,
                action_type="Lender contact",
                title="Ask the lender about available hardship options",
                description=(
                    "Contact the lender to ask what, if any, payment options are available. "
                    "No deferral, approval or savings amount is assumed."
                ),
                monthly_dollar_impact=0.0,
                is_immediate=False,
            )
        )

    return BackupPlan(
        monthly_shortfall=shortfall,
        required_monthly_cut=shortfall,
        buffer_after_one_off=shock_result.buffer_left,
        actions=actions,
        total_mitigation_capacity=0.0,
        deficit_fully_covered=shortfall <= 0,
        post_mitigation_gap=shortfall,
        post_mitigation_runway=calculate_runway(shock_result.buffer_left, shortfall),
    )
