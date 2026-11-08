"""
Deterministic Shock Simulation & Runway Engine
Calculates official Judge Match Runway, shock deltas, and adaptive survival runways.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np

from config.scenarios import ShockScenario
from src.services.baseline_metrics import BaselineMetrics, calculate_runway_details

@dataclass
class ShockResult:
    scenario_name: str
    scenario_id: str
    income_after_shock: float
    spending_after_shock: float
    household_bills_after_shock: float
    one_off_costs: float
    buffer_left: float
    monthly_gap: float
    runway_months: float
    runway_label: str
    delta_runway_vs_baseline: float
    
    # Adaptive / Compressible spend extension
    adaptive_spending: float
    adaptive_gap: float
    adaptive_runway_months: float
    adaptive_runway_label: str
    months_gained_by_adaptation: float
    
    # Severity & Vulnerability Status
    is_immediate_failure: bool  # buffer_left <= 0
    is_cashflow_negative: bool  # gap > 0
    resilience_status: str  # "Robust", "Manageable", "Critical", "Depleted"

def calculate_judge_runway(
    buffer: float,
    income_after_shock: float,
    spending_after_shock: float,
    one_off_costs: float = 0.0
) -> Dict[str, Any]:
    """
    Exact official formula from Tangerine challenge README:
    buffer_left = B - one_off_costs
    gap = spending_after_shock - income_after_shock
    if buffer_left <= 0: runway = 0
    elif gap <= 0: runway = "no shortfall (120+)"
    else: runway = min(buffer_left / gap, 120)
    Round runway to 1 decimal.
    """
    return calculate_runway_details(
        buffer,
        income_after_shock,
        spending_after_shock,
        one_off_costs,
    )

def simulate_shock(
    baseline: BaselineMetrics,
    scenario: ShockScenario,
    monthly_spending_adjustment: float = 0.0
) -> ShockResult:
    """
    Simulates a financial shock on a customer's baseline numbers:
    - Income: income_multiplier * I
    - Spending: S + household_bills_pct * H
    - One-off costs: one_off_spend_multiplier * S + one_off_fixed_amount
    """
    # 1. Shock Transformations
    income_after = round(scenario.income_multiplier * baseline.I, 2)
    h_after = round(baseline.H * (1.0 + scenario.household_bills_pct), 2)
    spending_after = round(baseline.S + (scenario.household_bills_pct * baseline.H), 2)
    one_off = round(
        (scenario.one_off_spend_multiplier * baseline.S) + scenario.one_off_fixed_amount, 2
    )

    # 2. Official Judge Match Runway
    judge_calc = calculate_judge_runway(
        buffer=baseline.B,
        income_after_shock=income_after,
        spending_after_shock=spending_after,
        one_off_costs=one_off
    )
    buffer_left = judge_calc["buffer_left"]
    gap = judge_calc["gap"]
    runway = judge_calc["runway"]
    runway_label = judge_calc["runway_label"]

    delta_runway = round(runway - baseline.baseline_runway, 1)

    if monthly_spending_adjustment < 0:
        raise ValueError("monthly_spending_adjustment cannot be negative")

    # Optional scenario only: this reduction is explicitly supplied by the user.
    adaptive_spending = round(max(0.0, spending_after - monthly_spending_adjustment), 2)
    adaptive_gap = round(adaptive_spending - income_after, 2)

    adaptive_calc = calculate_judge_runway(
        buffer=baseline.B,
        income_after_shock=income_after,
        spending_after_shock=adaptive_spending,
        one_off_costs=one_off
    )
    adaptive_runway = adaptive_calc["runway"]
    adaptive_label = adaptive_calc["runway_label"]
    months_gained = round(max(0.0, adaptive_runway - runway), 1)

    # 4. Resilience Classification
    if buffer_left <= 0:
        status = "Buffer Depleted (Critical)"
    elif runway >= 24.0 or gap <= 0:
        status = "Highly Resilient"
    elif runway >= 6.0:
        status = "Moderate Resilience"
    elif runway >= 3.0:
        status = "High Vulnerability (<6 Mos)"
    else:
        status = "Imminent Crisis (<3 Mos)"

    return ShockResult(
        scenario_name=scenario.name,
        scenario_id=scenario.scenario_id,
        income_after_shock=income_after,
        spending_after_shock=spending_after,
        household_bills_after_shock=h_after,
        one_off_costs=one_off,
        buffer_left=buffer_left,
        monthly_gap=gap,
        runway_months=runway,
        runway_label=runway_label,
        delta_runway_vs_baseline=delta_runway,
        adaptive_spending=adaptive_spending,
        adaptive_gap=adaptive_gap,
        adaptive_runway_months=adaptive_runway,
        adaptive_runway_label=adaptive_label,
        months_gained_by_adaptation=months_gained,
        is_immediate_failure=(buffer_left <= 0),
        is_cashflow_negative=(gap > 0),
        resilience_status=status
    )
