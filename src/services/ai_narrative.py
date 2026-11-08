"""Verified-metric explanations with optional Gemini language assistance."""

import json
import logging
import urllib.error
import urllib.request
from typing import Dict, Any

from config.settings import GEMINI_API_KEY, GEMINI_MODEL
from src.services.baseline_metrics import BaselineMetrics
from src.services.shock_engine import ShockResult
from src.services.recovery_planner import GoalPlan, BackupPlan
from src.services.customer_profile import CustomerProfile

LOGGER = logging.getLogger(__name__)


def generate_deterministic_narrative(
    profile: CustomerProfile,
    baseline: BaselineMetrics,
    shock: ShockResult,
    goal: GoalPlan,
    backup: BackupPlan,
) -> Dict[str, Any]:
    """Create an explanation entirely from deterministic service outputs."""
    if shock.buffer_left <= 0:
        headline = "The selected one-off cost exhausts the modeled starting buffer."
    elif shock.monthly_gap > 0:
        headline = (
            f"The selected scenario produces a monthly gap of "
            f"${shock.monthly_gap:,.2f} and an official runway of {shock.runway_label}."
        )
    else:
        headline = (
            f"The selected scenario has no modeled monthly shortfall; the official runway "
            f"is {shock.runway_label}."
        )

    summary = (
        f"Account-level historical medians are ${baseline.I:,.2f}/month money-in and "
        f"${baseline.S:,.2f}/month money-out. Under {shock.scenario_name}, modeled money-in "
        f"is ${shock.income_after_shock:,.2f}, spending is ${shock.spending_after_shock:,.2f}, "
        f"and buffer after one-off costs is ${shock.buffer_left:,.2f}. The Judge Match "
        f"calculation gives {shock.runway_label}."
    )
    drivers = [
        f"Typical fixed-cost measure F: ${baseline.F:,.2f}/month.",
        f"Recent six-row median monthly net cash flow: "
        f"${goal.recent_six_month_median_net_cash_flow:,.2f}."
        if goal.recent_six_month_median_net_cash_flow is not None
        else "Recent six-row net cash flow is unavailable.",
        f"Cash deposits are {baseline.cash_inflow_ratio:.1%} of recorded money-in; "
        "money-in is not verified employment income.",
        f"{profile.indicator_description}",
    ]
    actions = [
        "Use the customer-controlled Resilience Gap Optimizer to test a monthly adjustment; "
        "the model does not classify spending as discretionary.",
        "Treat any lender or standing-order review as an option to investigate, not an available service or guaranteed saving.",
    ]
    return {
        "headline": headline,
        "executive_summary": summary,
        "key_drivers": drivers,
        "recommended_actions": actions,
        "limitations": [
            "The Judge Match result is a deterministic scenario calculation, not a forecast.",
            "The 55% income scenario applies to recorded money-in and does not verify EI eligibility or employment income.",
            "Historical monthly coverage varies by account; the recent net-flow statistic uses the latest six available rows.",
        ],
        "metrics_used": {
            "typical_money_in": baseline.I,
            "typical_spending": baseline.S,
            "typical_fixed_costs": baseline.F,
            "recent_six_row_median_net_cash_flow": goal.recent_six_month_median_net_cash_flow,
            "income_after_shock": shock.income_after_shock,
            "spending_after_shock": shock.spending_after_shock,
            "monthly_gap": shock.monthly_gap,
            "buffer_left": shock.buffer_left,
            "judge_runway_months": shock.runway_months,
            "scenario_id": shock.scenario_id,
        },
        "ai_status": "deterministic",
    }


def get_ai_narrative(
    profile: CustomerProfile,
    baseline: BaselineMetrics,
    shock: ShockResult,
    goal: GoalPlan,
    backup: BackupPlan,
) -> Dict[str, Any]:
    """Keep Gemini optional and restricted to explaining verified aggregate metrics."""
    narrative = generate_deterministic_narrative(profile, baseline, shock, goal, backup)
    if not GEMINI_API_KEY:
        narrative["ai_status"] = "Gemini not configured; deterministic explanation shown."
        return narrative

    prompt = (
        "Rewrite the supplied verified financial facts as a concise plain-language explanation. "
        "Do not add recommendations, relationships, causes, predictions, or numbers not present "
        "in the facts. If the facts cannot support a conclusion, state that it cannot be determined. "
        "Return only the explanation.\n\n"
        f"Verified facts: {json.dumps(narrative['metrics_used'], sort_keys=True)}\n"
        f"Approved explanation: {narrative['executive_summary']}"
    )
    request_data = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 200},
        }
    ).encode("utf-8")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:"
        f"generateContent?key={GEMINI_API_KEY}"
    )
    request = urllib.request.Request(
        url, data=request_data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response_json = json.loads(response.read().decode("utf-8"))
        generated = response_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        if not generated:
            raise ValueError("Gemini returned an empty explanation")
        narrative["ai_explanation"] = generated
        narrative["ai_status"] = "Gemini explanation layer; deterministic metrics unchanged."
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as error:
        LOGGER.warning("Gemini explanation unavailable: %s", error)
        narrative["ai_status"] = (
            "Gemini explanation unavailable; deterministic explanation shown. "
            f"Reason: {type(error).__name__}."
        )
    return narrative


def answer_verified_question(
    question: str, baseline: BaselineMetrics, shock: ShockResult
) -> str:
    """Answer only questions covered by loaded deterministic metrics."""
    q = question.casefold()
    if any(term in q for term in ("default", "cause", "spouse", "partner", "predict", "debt outside")):
        return (
            "The selected account metrics cannot establish that conclusion. They do not "
            "identify causes, relationships, future defaults or confirmed external debt."
        )
    if "runway" in q or "survive" in q:
        return (
            f"The official Judge Match runway for {shock.scenario_name} is {shock.runway_label}. "
            "It uses the selected buffer after one-off costs and the modeled monthly gap."
        )
    if "buffer" in q or "savings" in q:
        return (
            f"The challenge buffer is ${baseline.B:,.2f}, the mean average daily balance over "
            "the latest six monthly rows; after the selected one-off cost it is "
            f"${shock.buffer_left:,.2f}."
        )
    if "fixed" in q or "essential" in q:
        return (
            f"Typical fixed costs F are ${baseline.F:,.2f}/month, calculated as the median of "
            "row-wise household bills, insurance and loan payments. F is a challenge metric, "
            "not a verified full measure of essential costs."
        )
    if "spend" in q or "outflow" in q:
        return (
            f"Typical monthly spending is ${baseline.S:,.2f}; under the selected scenario the "
            f"modeled amount is ${shock.spending_after_shock:,.2f}."
        )
    if "income" in q or "money in" in q:
        return (
            f"Typical monthly money-in is ${baseline.I:,.2f}; under this scenario it is "
            f"${shock.income_after_shock:,.2f}. Recorded money-in is not verified payroll."
        )
    if "gap" in q or "shortfall" in q:
        return (
            f"The modeled monthly gap is ${shock.monthly_gap:,.2f}; positive means spending "
            "exceeds modeled money-in."
        )
    return (
        "The loaded metrics do not answer that question. I can explain this account's money-in, "
        "spending, fixed-cost measure, buffer, monthly gap and Judge Match runway."
    )
