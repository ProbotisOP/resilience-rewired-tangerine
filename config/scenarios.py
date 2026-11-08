"""
Scenario Definitions and Presets for Financial Shock Simulations
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class ShockScenario:
    scenario_id: str
    name: str
    description: str
    income_multiplier: float = 1.0
    household_bills_pct: float = 0.0  # e.g., 0.15 means +15%
    one_off_spend_multiplier: float = 0.0  # e.g., 1.0 means 1.0 * S
    one_off_fixed_amount: float = 0.0  # Fixed dollar amount (e.g. $5,000)
    duration_months: int = 6
    is_judge_preset: bool = True

# Standard Competition Presets from Tangerine README
OFFICIAL_PRESETS = [
    ShockScenario(
        scenario_id="BASELINE",
        name="Baseline (Status Quo)",
        description="Normal monthly cash flow with no unexpected economic disruption.",
        income_multiplier=1.0,
        household_bills_pct=0.0,
        one_off_spend_multiplier=0.0,
        one_off_fixed_amount=0.0,
        duration_months=12,
        is_judge_preset=True
    ),
    ShockScenario(
        scenario_id="JOB_LOSS_EI_55",
        name="Twist 1: Job Loss (EI @ 55%)",
        description="Challenge simulation scales recorded typical money-in to 55%; it does not verify payroll or EI eligibility.",
        income_multiplier=0.55,
        household_bills_pct=0.0,
        one_off_spend_multiplier=0.0,
        one_off_fixed_amount=0.0,
        duration_months=6,
        is_judge_preset=True
    ),
    ShockScenario(
        scenario_id="FURNACE_REPAIR",
        name="Twist 2: Emergency Repair (1 Mo Spend)",
        description="Major home furnace or auto failure costing one full month of typical spending (S).",
        income_multiplier=1.0,
        household_bills_pct=0.0,
        one_off_spend_multiplier=1.0,
        one_off_fixed_amount=0.0,
        duration_months=1,
        is_judge_preset=True
    ),
    ShockScenario(
        scenario_id="COMBINED_SHOCK",
        name="Twist 3: Layoff (EI 55%) + Bills (+15%)",
        description="Challenge simulation scales recorded money-in to 55% and raises household bills by 15%; not a forecast.",
        income_multiplier=0.55,
        household_bills_pct=0.15,
        one_off_spend_multiplier=0.0,
        one_off_fixed_amount=0.0,
        duration_months=6,
        is_judge_preset=True
    )
]

PRESET_DICT = {s.scenario_id: s for s in OFFICIAL_PRESETS}
