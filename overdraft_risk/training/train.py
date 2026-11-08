"""Train and save the final 6-month overdraft-risk model.

Training rows: one per account per cutoff month (June and December, 2020-12 to 2024-06). Predictors use data up to
the cutoff; the label is 1 if the account has an overdraft event in the 6 months after the cutoff. The last cutoff
(2024-06) is labelled with Jul-Dec 2024, so no 2025 data is used.

Run:  python -m overdraft_risk.training.train
Needs scikit-learn (training only; inference in overdraft_risk/service.py needs only numpy).
"""
import json
from datetime import datetime, timezone
from pathlib import Path
 
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
 
from .features import build, load, outcome
 
HORIZON = 6
WINDOW = 6
MIN_HISTORY = 6
C = 1.0  # chosen on the 2023-12 / 2024-06 validation cutoffs by log loss (see evaluate.py)
CUTOFFS = ["2020-12", "2021-06", "2021-12", "2022-06", "2022-12", "2023-06", "2023-12", "2024-06"]
FEATURES = [
    "log_buffer6", "buffer_months", "min_bal_to_out", "log_mean_in", "cash_wd_share",
    "outflow_months_share", "spend_trend", "loanpay_to_in", "so_to_in", "penalty_hist",
    "neg_months_win", "joint",
]
OUT = Path(__file__).resolve().parents[1] / "model" / "overdraft_risk_6m.json"
 
 
def training_panel(d):
    accs = d["ms"]["account_id"].unique()
    parts = []
    for c in CUTOFFS:
        cut = pd.Series(pd.Period(c, "M"), index=accs, name="cut")
        cut.index.name = "account_id"
        f, _ = build(d, cut, min_hist=MIN_HISTORY, win=WINDOW)
        f = f.merge(outcome(d, cut, horizon=HORIZON, min_obs=HORIZON).reset_index(), on="account_id")
        f["cutoff"] = c
        parts.append(f)
    return pd.concat(parts, ignore_index=True)
 
 
def main():
    d = load()
    panel = training_panel(d)
    model = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                          LogisticRegression(C=C, max_iter=5000)).fit(panel[FEATURES], panel["y"])
    imputer, scaler, lr = model
    artifact = {
        "name": "overdraft_risk_6m",
        "description": "P(overdraft event in the 6 months after the as-of month). Event = month with "
                       "days_below_zero > 0 or min_balance < 0, or a penalty-interest transaction.",
        "horizon_months": HORIZON,
        "window_months": WINDOW,
        "min_history_months": MIN_HISTORY,
        "trained_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "training_cutoffs": CUTOFFS,
        "label_period": "2021-01 to 2024-12",
        "training_rows": int(len(panel)),
        "training_accounts": int(panel["account_id"].nunique()),
        "training_events": int(panel["y"].sum()),
        "regularisation_C": C,
        "features": FEATURES,
        "impute_median": imputer.statistics_.tolist(),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coef": lr.coef_[0].tolist(),
        "intercept": float(lr.intercept_[0]),
        "test_metrics_2025": {
            "note": "Model fit on cutoffs 2020-12..2024-06, scored on cutoffs 2024-12 and 2025-06 (labels 2025).",
            "rows": 8541, "events": 234, "AUC": 0.958, "AUC_95ci": [0.947, 0.968], "average_precision": 0.606,
            "brier": 0.0159, "brier_skill": 0.405, "log_loss": 0.0655,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"Saved {OUT}: {artifact['training_rows']} rows, {artifact['training_events']} events")
    print(pd.Series(artifact["coef"], index=FEATURES).round(3).to_string())
 
 
if __name__ == "__main__":
    main()
