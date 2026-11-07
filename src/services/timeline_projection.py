"""
Timeline Projection Engine: Month-by-Month Trajectory & Cash Burn Simulation
Strictly separated from the official Judge Match Runway formula.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from src.services.baseline_metrics import BaselineMetrics
from src.services.shock_engine import ShockResult

@dataclass
class MonthPoint:
    month_index: int
    month_name: str
    starting_buffer: float
    income: float
    spending: float
    net_flow: float
    ending_buffer: float
    is_in_overdraft: bool

@dataclass
class TimelineProjection:
    duration_months: int
    starting_buffer_after_one_off: float
    ending_buffer_at_shock_end: float
    months_until_depleted: Optional[int]
    trajectory: List[MonthPoint]
    survives_full_shock_period: bool

def project_shock_timeline(
    baseline: BaselineMetrics,
    shock_result: ShockResult,
    duration_months: int = 6,
    adaptive_mode: bool = False
) -> TimelineProjection:
    """
    Simulates monthly buffer progression across the shock window:
    - Month 1 begins with: buffer_left = B - one_off_costs
    - Each month: buffer_{t+1} = buffer_t + (income_after - spending_after)
    """
    current_buf = shock_result.buffer_left
    income = shock_result.income_after_shock
    spending = shock_result.adaptive_spending if adaptive_mode else shock_result.spending_after_shock
    net_monthly = income - spending

    trajectory: List[MonthPoint] = []
    depleted_month: Optional[int] = None

    for m in range(1, duration_months + 1):
        start_b = current_buf
        end_b = round(start_b + net_monthly, 2)
        is_neg = (end_b < 0)

        if end_b <= 0 and depleted_month is None:
            depleted_month = m

        trajectory.append(MonthPoint(
            month_index=m,
            month_name=f"Month +{m}",
            starting_buffer=round(start_b, 2),
            income=round(income, 2),
            spending=round(spending, 2),
            net_flow=round(net_monthly, 2),
            ending_buffer=round(end_b, 2),
            is_in_overdraft=is_neg
        ))
        current_buf = end_b

    survives = (depleted_month is None or depleted_month > duration_months)

    return TimelineProjection(
        duration_months=duration_months,
        starting_buffer_after_one_off=shock_result.buffer_left,
        ending_buffer_at_shock_end=trajectory[-1].ending_buffer if trajectory else current_buf,
        months_until_depleted=depleted_month,
        trajectory=trajectory,
        survives_full_shock_period=survives
    )
