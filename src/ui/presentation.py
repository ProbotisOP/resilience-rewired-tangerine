import re
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from config.scenarios import ShockScenario
from src.services.insight_language import _group_number, money_in_group_name  # noqa: F401  (re-exported)


_SCENARIO_COPY = {
    "BASELINE": (
        "Baseline (no shock)",
        "What if the usual monthly money in and spending continue, with no added bill?",
    ),
    "JOB_LOSS_EI_55": (
        "Job loss: money-in at 55% (EI)",
        "What if recorded monthly money-in falls to 55% of its usual level? This is a "
        "scenario, not confirmed payroll or EI.",
    ),
    "FURNACE_REPAIR": (
        "Furnace repair: one month of spending",
        "What if a one-off repair costs the same as one typical month of spending? "
        "This is a test amount, not a quoted repair bill.",
    ),
    "COMBINED_SHOCK": (
        "Money-in at 55% + bills +15%",
        "What if recorded monthly money-in falls to 55% and household bills rise 15%? "
        "A double what-if, not a prediction.",
    ),
}


def scenario_display_name(scenario: ShockScenario) -> str:
    """Return a plain-language UI name while retaining the official scenario object."""
    return _SCENARIO_COPY.get(
        scenario.scenario_id, (scenario.name, scenario.description)
    )[0]


def scenario_display_description(scenario: ShockScenario) -> str:
    """Return a plain-language explanation of the scenario assumptions."""
    return _SCENARIO_COPY.get(
        scenario.scenario_id, (scenario.name, scenario.description)
    )[1]


# ---------------------------------------------------------------- plain group names
# Calculations keep the analyst codes (D1..D10, Q1..Q4, bins 1..10); only what people read changes.
MONEY_IN_GROUP_NOTE = ("Money-in groups: all accounts ranked by typical monthly money in and split into 10 equal "
                       "groups · Bottom 10% = lowest money in, Top 10% = highest")


def _k(value: float) -> str:
    return f"${value / 1000:,.1f}k" if abs(value) >= 1000 else f"${value:,.0f}"


def money_in_group_ranges(incomes: pd.Series) -> Dict[str, Tuple[float, float]]:
    """Min and max typical money in per group, using the same split as the decile discovery."""
    groups = pd.qcut(incomes, 10, labels=[f"D{i}" for i in range(1, 11)], duplicates="drop")
    return {str(code): (float(v.min()), float(v.max())) for code, v in incomes.groupby(groups, observed=True)}


def money_in_group_range_text(code: Any, ranges: Dict[str, Tuple[float, float]]) -> str:
    n = _group_number(code)
    if n is None or f"D{n}" not in ranges:
        return ""
    lo, hi = ranges[f"D{n}"]
    if n == 1:
        return f"up to {_k(hi)}/mo"
    if n == 10:
        return f"over {_k(lo)}/mo"
    return f"{_k(lo)}–{_k(hi)}/mo"


def money_in_group_tick(code: Any) -> str:
    """Short chart tick that fits ten bars: 'Bottom\n10%', '10–20%', …, 'Top\n10%'."""
    name = money_in_group_name(code)
    return name.replace(" ", "\n", 1) if name.startswith(("Bottom", "Top")) else name


def money_in_ranges_caption(ranges: Dict[str, Tuple[float, float]]) -> str:
    """One line listing every group's typical monthly money-in range."""
    items = [f"{money_in_group_name(f'D{n}')} {money_in_group_range_text(f'D{n}', ranges)}"
             for n in range(1, 11) if f"D{n}" in ranges]
    return "Typical monthly money in per group: " + " · ".join(items)


def buffer_group_name(code: Any) -> str:
    """'Q1 (Lowest Buffer)' -> 'Lowest 25% buffer' … 'Q4 (Highest Buffer)' -> 'Highest 25% buffer'."""
    match = re.match(r"\s*Q([1-4])", str(code))
    if not match:
        return str(code)
    return {"1": "Lowest 25% buffer", "2": "25–50% buffer", "3": "50–75% buffer", "4": "Highest 25% buffer"}[match.group(1)]


PRELOAN_BUFFER_LABEL = "What is the pre-loan buffer?"


def preloan_buffer_explainer(pre: Dict[str, Any]) -> str:
    """Plain-language explanation of the pre-loan buffer, filled with the cohort's own numbers."""
    q = pre.get("quartile_summary")
    medians = ""
    if q is not None and not q.empty:
        # "\$" keeps Streamlit markdown from reading two dollar signs as a LaTeX formula.
        medians = " · ".join(f"{buffer_group_name(r.buffer_quartile)}: median **\\${r.median_buffer:,.0f}**"
                             for r in q.itertuples())
    return (
        "**What it is:** the savings cushion an account had *before* it took the loan, measured as the average "
        "daily balance over the account's **6 latest monthly records before the loan-start month**. It uses only "
        "information the bank already had on the day the loan was made, so nothing after the loan leaks in.\n\n"
        f"**Which loans count:** {pre.get('cohort_size', 0):,} of {pre.get('eligible_loan_count', 0):,} loans had at "
        "least 6 earlier monthly records; the rest are left out rather than guessed.\n\n"
        "**The 4 groups:** those loans are ranked by pre-loan buffer and split into 4 equal groups (25% of loans "
        f"each), from the smallest cushion to the largest. {medians}\n\n"
        "**Why it matters:** a thin cushion leaves no room for a bad month, so the loan payment competes with "
        "everything else. **Read it as an association**, not a cause: it is unadjusted, and the default flag includes "
        "running loans (status D) whose outcome can still change."
    )


def score_group_name(bin_number: Any) -> str:
    """Calibration bin 1..10 -> 'Lowest 10%' … 'Highest 10%' (of model scores)."""
    n = int(bin_number)
    if n == 1:
        return "Lowest 10%"
    if n == 10:
        return "Highest 10%"
    return f"{(n - 1) * 10}–{n * 10}%"
