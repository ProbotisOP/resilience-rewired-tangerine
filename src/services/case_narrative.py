"""
Case narrative: an LLM writes the story, but only from verified facts, and every number is checked.

The facts dictionary is built from the deterministic engine, the stress model, anomaly detection and the
forecast. The LLM (Snowflake Cortex AI_COMPLETE) must return labelled statements in a fixed JSON schema;
verify_numbers() then flags any number in the text that does not appear in the facts.
"""

import json
import re
from typing import Any, Dict, Iterable, List, Set

LABELS = ["OBSERVED FACT", "CALCULATED FROM OBSERVED DATA", "SIMULATED SCENARIO", "MODEL ESTIMATE", "PROPOSED ACTION"]

NARRATIVE_SCHEMA = {
    "type": "json",
    "schema": {
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "statements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "enum": LABELS},
                        "text": {"type": "string"},
                        "source": {"type": "string"},
                    },
                    "required": ["label", "text", "source"],
                },
            },
            "conversation_opener": {"type": "string"},
            "limits": {"type": "string"},
        },
        "required": ["headline", "statements", "conversation_opener", "limits"],
    },
}

PROMPT = """You are writing a short customer-support case story for a Tangerine advisor.
Use ONLY the facts in the JSON below. Copy numbers exactly as written; do not compute, round differently,
convert, or invent any number, percentage, date, product, approval or eligibility.
Write 6 to 9 statements that tell the story in this order: what is observed, what changed or looked unusual,
what the calculated runway is, what the simulated scenario does, what the model estimates (with its limit),
and a proposed, customer-led next step drawn from the support prompts. Label each statement with exactly one of:
OBSERVED FACT, CALCULATED FROM OBSERVED DATA, SIMULATED SCENARIO, MODEL ESTIMATE, PROPOSED ACTION.
"source" names the fact group used (for example "baseline", "anomalies", "scenario", "model", "forecast").
Say "money in", never "income" or "salary". Never describe a simulation as something that happened, and never
describe an association as a cause. The model estimate is for supportive outreach only, never a credit decision.
The conversation_opener is one empathetic sentence an advisor could say. "limits" is one sentence of caveats.

FACTS:
{facts}
"""

_NUMBER = re.compile(r"(?<![A-Za-z#\d.,])[-+]?\$?\d[\d,]*(?:\.\d+)?%?")


def _variants(value: float) -> Set[str]:
    out = set()
    for digits in (0, 1, 2):
        rounded = round(value, digits)
        out.add(f"{rounded:.{digits}f}")
        out.add(f"{abs(rounded):.{digits}f}")
    return out


def _collect(obj: Any, into: Set[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _collect(v, into)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect(v, into)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        into |= _variants(float(obj))
    elif isinstance(obj, str):
        for token in _NUMBER.findall(obj):
            cleaned = token.replace("$", "").replace(",", "").replace("%", "").lstrip("+")
            try:
                into |= _variants(float(cleaned))
            except ValueError:
                pass


def allowed_numbers(facts: Dict[str, Any]) -> Set[str]:
    allowed: Set[str] = set()
    _collect(facts, allowed)
    return allowed


def verify_numbers(texts: Iterable[str], facts: Dict[str, Any]) -> List[str]:
    """Return every number in texts that cannot be traced to the facts (years and small counts 0-12 are allowed)."""
    allowed = allowed_numbers(facts)
    unmatched = []
    for text in texts:
        for token in _NUMBER.findall(text or ""):
            cleaned = token.replace("$", "").replace(",", "").replace("%", "").lstrip("+")
            try:
                value = float(cleaned)
            except ValueError:
                continue
            if value.is_integer() and (0 <= value <= 12 or 2020 <= value <= 2026):
                continue
            digits = len(cleaned.split(".")[1]) if "." in cleaned else 0
            if f"{abs(value):.{digits}f}" not in allowed and f"{value:.{digits}f}" not in allowed:
                unmatched.append(token)
    return unmatched


def build_prompt(facts: Dict[str, Any]) -> str:
    return PROMPT.replace("{facts}", json.dumps(facts, indent=1, default=str))


# ---------------------------------------------------------------- TANG plan coach
COACH_SCHEMA = {
    "type": "json",
    "schema": {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string", "enum": LABELS},
                        "text": {"type": "string"},
                    },
                    "required": ["label", "text"],
                },
            },
            "next_step": {"type": "string"},
        },
        "required": ["answer", "points", "next_step"],
    },
}

COACH_PROMPT = """You are TANG, Tangerine's resilience assistant. You help a business manager plan and explain a
customer recovery plan. Answer the manager's QUESTION using ONLY the facts in the JSON below.
Copy numbers exactly as written; do not compute, round differently, convert, or invent any number, percentage,
date, product, approval or eligibility. If the facts cannot answer the question, say so plainly.
"answer" is 2 to 4 plain-English sentences a non-specialist manager understands, with no jargon.
"points" are 2 to 5 short supporting bullets, each labelled with exactly one of:
OBSERVED FACT, CALCULATED FROM OBSERVED DATA, SIMULATED SCENARIO, MODEL ESTIMATE, PROPOSED ACTION.
"next_step" is one concrete, customer-led action the manager can take next.
Say "money in", never "income" or "salary". Never describe a simulation as something that happened, never describe
an association as a cause, and never promise relief, approval or a product. The model estimate is for supportive
outreach only, never a credit decision. The customer decides which spending, if any, changes.

FACTS:
{facts}

EARLIER IN THIS CONVERSATION:
{history}

QUESTION:
{question}
"""


def build_coach_prompt(facts: Dict[str, Any], question: str, history: List[Dict[str, str]]) -> str:
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:]) or "(none)"
    return (COACH_PROMPT.replace("{facts}", json.dumps(facts, indent=1, default=str))
            .replace("{history}", convo).replace("{question}", question))
