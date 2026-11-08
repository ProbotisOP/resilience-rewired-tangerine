"""Overdraft-risk service: probability of an overdraft event in the 6 months after a chosen month.

An "overdraft event" is a month with days_below_zero > 0 or min_balance < 0 (monthly_summary.csv), or a
`penalty interest (negative balance)` charge (transactions.csv, column purpose).

Inference needs only numpy: the fitted logistic-regression weights are read from
overdraft_risk/model/overdraft_risk_6m.json (written by overdraft_risk/training/train.py).

    from overdraft_risk.service import get_overdraft_risk
    result = get_overdraft_risk(20111)       # uses the account's latest month as the "as of" month
    result.display                           # e.g. "30.35%"
"""

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.data.local_repository import LocalDataRepository

MODEL_PATH = Path(__file__).resolve().parent / "model" / "overdraft_risk_6m.json"
WINDOW = 6          # months of history used by the flow / balance predictors
TREND_HALF = 3      # spend_trend compares the last 3 months with the 3 before them
BUFFER_WINDOW = 6   # months used for the buffer (average daily balance)
MIN_HISTORY = 6     # monthly rows required before the as-of month

_PENALTY_CACHE: Dict[str, Dict[int, np.ndarray]] = {}


@dataclass
class OverdraftRisk:
    account_id: int
    as_of_month: str
    horizon_months: int
    probability_pct: float
    display: str
    features: Dict[str, float] = field(default_factory=dict)


@lru_cache(maxsize=4)
def load_model(path: str = str(MODEL_PATH)) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def format_probability(probability: float) -> str:
    """0.303549 -> '30.35%'."""
    return f"{round(float(probability) * 100.0, 2):.2f}%"


def _safe_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator not in (0, 0.0) else np.nan


def compute_features(
    monthly: pd.DataFrame,
    as_of: pd.Period,
    n_clients: int,
    standing_order_total: float,
    penalty_months: np.ndarray,
) -> Dict[str, float]:
    """Build the predictors for one account using only information up to and including `as_of`.

    monthly: that account's monthly_summary rows (any order); penalty_months: Period ordinals (as ints)
    of months with a penalty-interest charge.
    """
    m = monthly.copy()
    m["_period"] = pd.PeriodIndex(m["month"], freq="M")
    m = m[m["_period"] <= as_of].sort_values("_period")
    if len(m) < MIN_HISTORY:
        raise ValueError(f"Need at least {MIN_HISTORY} monthly rows up to {as_of}; found {len(m)}.")

    last = m.iloc[::-1].reset_index(drop=True)  # row 0 = latest month <= as_of
    w = last.iloc[:WINDOW]
    recent, prior = last.iloc[:TREND_HALF], last.iloc[TREND_HALF:WINDOW]
    buf_rows = last.iloc[:BUFFER_WINDOW]
    n = len(w)

    money_in, money_out = float(w["money_in"].sum()), float(w["money_out"].sum())
    avg_out = money_out / n
    buffer_raw = float(buf_rows["avg_daily_balance"].mean())
    neg_flag = (w["days_below_zero"] > 0) | (w["min_balance"] < 0)

    return {
        "log_buffer6": float(np.log1p(max(buffer_raw, 0.0))),
        "buffer_months": float(np.minimum(_safe_ratio(buffer_raw, avg_out), 60.0)),
        "min_bal_to_out": float(np.clip(_safe_ratio(float(w["min_balance"].min()), avg_out), -5.0, 60.0)),
        "log_mean_in": float(np.log1p(w["money_in"].mean())),
        "cash_wd_share": _safe_ratio(float(w["cash_withdrawals_genuine"].sum()), money_out),
        "outflow_months_share": float((w["money_out"] > w["money_in"]).mean()),
        "spend_trend": float(np.log1p(recent["money_out"].mean()) - np.log1p(prior["money_out"].mean())),
        "loanpay_to_in": _safe_ratio(float(w["loan_payments"].sum()), money_in),
        "so_to_in": float(np.minimum(standing_order_total / (money_in / n + 1e-9), 5.0)),
        "penalty_hist": float(bool(len(penalty_months)) and bool((penalty_months <= as_of.ordinal).any())),
        "neg_months_win": float(neg_flag.sum()),
        "joint": float(n_clients >= 2),
    }


def predict_probability(features: Dict[str, float], model: Optional[dict] = None) -> float:
    """Apply the saved logistic regression: impute, standardise, weighted sum, sigmoid."""
    model = model or load_model()
    names = model["features"]
    x = np.array([features[name] for name in names], dtype=float)
    x = np.where(np.isnan(x), np.array(model["impute_median"], dtype=float), x)
    z = (x - np.array(model["scaler_mean"])) / np.array(model["scaler_scale"])
    logit = float(np.dot(z, np.array(model["coef"])) + model["intercept"])
    return float(1.0 / (1.0 + np.exp(-logit)))


def _penalty_index(repo: LocalDataRepository) -> Dict[int, np.ndarray]:
    """account_id -> sorted array of Period ordinals with a penalty-interest charge (read once, cached)."""
    key = str(repo.data_dir)
    if key not in _PENALTY_CACHE:
        if repo.transactions is not None:
            tx = repo.transactions[["account_id", "date", "purpose"]]
        else:
            tx = pd.read_csv(Path(repo.data_dir) / "transactions.csv", usecols=["account_id", "date", "purpose"])
        pen = tx[tx["purpose"].fillna("").str.contains("penalty", case=False)]
        ordinals = pd.PeriodIndex(pd.to_datetime(pen["date"]), freq="M").asi8
        frame = pd.DataFrame({"account_id": pen["account_id"].values, "ord": ordinals})
        _PENALTY_CACHE[key] = {
            int(acc): np.sort(grp["ord"].to_numpy()) for acc, grp in frame.groupby("account_id")
        }
    return _PENALTY_CACHE[key]


def get_overdraft_risk(
    account_id: int,
    repo: Optional[LocalDataRepository] = None,
    as_of: Optional[str] = None,
) -> Optional[OverdraftRisk]:
    """Probability (as a percentage) of an overdraft event in the 6 months after `as_of` ('YYYY-MM').

    `as_of` defaults to the account's latest month. Returns None for an unknown account_id; raises
    ValueError if the account has fewer than 6 monthly rows up to `as_of`.
    """
    if repo is None:
        repo = LocalDataRepository.get_instance()
    if not repo._is_loaded:
        repo.load_all()
    if account_id not in set(repo.accounts["account_id"]):
        return None

    monthly = repo.get_monthly_summary(account_id)
    if monthly.empty:
        raise ValueError(f"Account {account_id} has no monthly_summary rows.")
    period = (
        pd.Period(as_of, freq="M")
        if as_of
        else pd.PeriodIndex(monthly["month"], freq="M").max()
    )

    disp = repo.dispositions[repo.dispositions["account_id"] == account_id]
    so = repo.standing_orders[repo.standing_orders["account_id"] == account_id]
    penalties = _penalty_index(repo).get(int(account_id), np.array([], dtype=np.int64))

    features = compute_features(
        monthly=monthly,
        as_of=period,
        n_clients=int(disp["client_id"].nunique()),
        standing_order_total=float(so["amount"].sum()) if not so.empty else 0.0,
        penalty_months=penalties,
    )
    model = load_model()
    pct = round(predict_probability(features, model) * 100.0, 2)
    return OverdraftRisk(
        account_id=int(account_id),
        as_of_month=str(period),
        horizon_months=int(model["horizon_months"]),
        probability_pct=pct,
        display=f"{pct:.2f}%",
        features=features,
    )
