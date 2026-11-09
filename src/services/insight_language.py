"""Turn Snowflake TOP_INSIGHTS segment strings into plain language for advisors and judges."""

import re
from typing import List, Optional

def _k(value: float) -> str:
    return f"${value / 1000:,.0f}k" if value >= 1000 else f"${value:,.0f}"


def _group_number(code) -> Optional[int]:
    match = re.fullmatch(r"\s*D?(\d{1,2})\s*", str(code))
    return int(match.group(1)) if match and 1 <= int(match.group(1)) <= 10 else None


def money_in_group_name(code) -> str:
    """Plain name for a money-in decile code: 'D1' -> 'Bottom 10%', 'D4' -> '30–40%', 'D10' -> 'Top 10%'."""
    n = _group_number(code)
    if n is None:
        return str(code)
    if n == 1:
        return "Bottom 10%"
    if n == 10:
        return "Top 10%"
    return f"{(n - 1) * 10}–{n * 10}%"


def _money_in_phrase(included: List[int], excluded: List[int]) -> str:
    """Describe the money-in groups a segment covers, in whichever form is shorter."""
    def names(nums):
        return " / ".join(money_in_group_name(n).lower() for n in nums)

    if included:
        return names(sorted(included)) + " money-in"
    excluded = sorted(set(excluded))
    if excluded == [1]:
        return "money-in above the bottom 10%"
    if excluded == [10]:
        return "money-in below the top 10%"
    kept = [n for n in range(1, 11) if n not in excluded]
    if len(kept) <= len(excluded):
        return "money-in groups " + names(kept)
    return "money-in outside " + names(excluded)


def humanize_segment(segment: str) -> str:
    if segment.strip().lower() == "overall":
        return "All accounts"
    parts, buffer_low, buffer_high = [], None, None
    included, excluded = [], []
    for raw in segment.split(" AND "):
        term = raw.strip()
        negated = term.startswith("not ")
        term = term[4:] if negated else term
        m = re.match(r"SAVINGS_BUFFER\s*(<=|>|<|>=)\s*([\d.]+)", term)
        if m:
            value = float(m.group(2))
            if m.group(1) in ("<=", "<"):
                buffer_high = value
            else:
                buffer_low = value
            continue
        key, _, value = term.partition(" = ")
        value = value.strip()
        if key == "INCOME_DECILE" and _group_number(value) is not None:
            (excluded if negated else included).append(_group_number(value))
        elif key in ("SPEND_TO_MONEY_IN", "FIXED_COST_SHARE", "LOAN", "CARD_TYPE", "STATEMENT_FREQUENCY", "BRANCH_REGION",
                     "AUTHORIZED_USER"):
            label = {"LOAN": "loan", "CARD_TYPE": "card", "STATEMENT_FREQUENCY": "statements", "BRANCH_REGION": "branch region",
                     "AUTHORIZED_USER": "authorized user"}.get(key, "")
            text = f"{label}: {value}" if label else value
            parts.append(("not " if negated else "") + text)
        else:
            parts.append(("not " if negated else "") + term.lower().replace("_", " "))
    if buffer_low is not None or buffer_high is not None:
        lo = _k(buffer_low) if buffer_low is not None else "$0"
        parts.append(f"buffer {lo}–{_k(buffer_high)}" if buffer_high is not None else f"buffer above {lo}")
    # "not spends under 90%" and "not spends more than" together mean "spends 90-100%".
    # Money-in groups lead the phrase, in plain names (never D1..D10).
    if included or excluded:
        parts.insert(0, _money_in_phrase(included, excluded))
    text = " · ".join(parts)
    text = text.replace("not spends under 90% of money in · not spends more than money in", "spends 90–100% of money in")
    text = text.replace("not spends more than money in · not spends under 90% of money in", "spends 90–100% of money in")
    text = text.replace("not spends under 90% of money in", "spends 90%+ of money in")
    text = text.replace("spends more than money in", "spends > money in").replace(" of money in", "")
    return text[:1].upper() + text[1:]
