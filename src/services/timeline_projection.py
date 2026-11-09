"""
Timeline Projection Engine: Month-by-Month Trajectory & Cash Burn Simulation
Strictly separated from the official Judge Match Runway formula.
"""

import math
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
    if duration_months < 0:
        raise ValueError("duration_months cannot be negative")

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


def _timeline_duration(shock, no_shortfall_duration: int) -> int:
    finite_runways = [
        min(shock.buffer_left / gap, 120.0)
        for gap in (shock.monthly_gap, shock.adaptive_gap)
        if shock.buffer_left > 0 and gap > 0
    ]
    if finite_runways:
        return max(1, math.ceil(max(finite_runways)))
    return 1 if shock.buffer_left <= 0 else no_shortfall_duration


def _timeline_series(baseline, shock, projection, gap: float, runway: float, label: str):
    """Buffer path: before event, after one-off, then month ends; ends at $0 on the runway point."""
    x_values = ["Before event", "After one-off"]
    y_values = [baseline.B, shock.buffer_left]
    raw_runway = shock.buffer_left / gap if shock.buffer_left > 0 and gap > 0 else None
    depletion_step = math.ceil(raw_runway) if raw_runway is not None else None
    if raw_runway is not None and raw_runway <= 120:
        points = projection.trajectory[: depletion_step - 1]
        x_values += [p.month_name for p in points] + [f"{label} runway · {runway:.1f} mo"]
        y_values += [p.ending_buffer for p in points] + [0.0]
    else:
        x_values += [p.month_name for p in projection.trajectory]
        y_values += [p.ending_buffer for p in projection.trajectory]
    return x_values, y_values, raw_runway, depletion_step
