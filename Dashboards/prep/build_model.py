"""Train the random-forest default forecaster and write Dashboards/data/model.js.

    python Dashboards/prep/build_model.py [path/to/Tangerine]

Needs scikit-learn (pip install scikit-learn).

Leakage rule: every account feature is computed from monthly_summary rows BEFORE the loan's
start month, and only cards issued before the loan count. Post-loan overdrafts and penalty
interest are largely consequences of a default, so using them would inflate accuracy.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parents[1] / "Tangerine"
SEED = 42
# Cash-share values for the what-if curves. Real cash shares are bimodal (a third below 0.12, most at 0.987-0.997)
# and the forest splits almost only inside those two bands, so the grid is fine at both ends and coarse in between.
GRID = np.unique(np.round(np.concatenate([np.arange(0, 0.1, 0.005), np.arange(0.1, 0.95, 0.05),
                                          np.arange(0.95, 1.0005, 0.001)]), 4))

FEATURES = {                                       # column -> readable label for the dashboard
    "cash_share": "Cash share of income",
    "income": "Median monthly income",
    "spending": "Median monthly spending",
    "balance": "Average balance (last 6 months)",
    "neg_days": "Days below zero",
    "amount": "Loan amount",
    "duration": "Loan length (months)",
    "payment": "Monthly payment",
    "pti": "Payment-to-income ratio",
    "joint": "Joint account",
    "card": "Has a card",
    "freq_monthly": "Monthly statements",
    "freq_weekly": "Weekly statements",
    "freq_per_tx": "Statement after each transaction",
    "district_salary": "District average salary",
    "district_unemp": "District unemployment rate",
    "age": "Owner's age at loan start",
}


def build_features(data_dir: Path) -> pd.DataFrame:
    loans = pd.read_csv(data_dir / "loans.csv")
    acc = pd.read_csv(data_dir / "accounts.csv")
    disp = pd.read_csv(data_dir / "dispositions.csv")
    cards = pd.read_csv(data_dir / "cards.csv")
    clients = pd.read_csv(data_dir / "clients.csv")
    dist = pd.read_csv(data_dir / "districts.csv")
    ms = pd.read_csv(data_dir / "monthly_summary.csv")

    loans["start_month"] = loans.loan_start.str[:7]

    # --- account behaviour, pre-loan months only
    m = ms.merge(loans[["account_id", "start_month"]], on="account_id")
    pre = m[m.month < m.start_month].sort_values(["account_id", "month"])
    assert (pre.month < pre.start_month).all()
    g = pre.groupby("account_id")
    beh = pd.DataFrame({
        "months_pre": g.size(),
        "cash_share": g.cash_deposits.sum() / (g.money_in.sum() + 1e-6),
        "income": g.money_in.median(),
        "spending": g.money_out.median(),
        "balance": g.tail(6).groupby("account_id").avg_daily_balance.mean(),
        "neg_days": g.days_below_zero.sum(),
    })
    missing = set(loans.account_id) - set(beh.index)
    assert not missing, f"{len(missing)} loans have no pre-loan history"

    X = loans[["loan_id", "account_id", "loan_start", "defaulted", "amount", "duration_months", "monthly_payment"]] \
        .rename(columns={"duration_months": "duration", "monthly_payment": "payment"}) \
        .merge(beh, left_on="account_id", right_index=True)
    X["pti"] = X.payment / X.income.clip(lower=1)

    # --- household: joint account, card issued before the loan
    X["joint"] = X.account_id.isin(disp.loc[disp.type == "authorized user", "account_id"]).astype(int)
    cd = disp.merge(cards, on="disposition_id")[["account_id", "issued"]].merge(loans[["account_id", "loan_start"]], on="account_id")
    X["card"] = X.account_id.isin(cd.loc[cd.issued < cd.loan_start, "account_id"]).astype(int)

    # --- statement frequency (one-hot)
    freq = acc.set_index("account_id").frequency.map(
        {"monthly statement": "monthly", "weekly statement": "weekly", "statement after each transaction": "per_tx"})
    for f in ["monthly", "weekly", "per_tx"]:
        X[f"freq_{f}"] = (X.account_id.map(freq) == f).astype(int)

    # --- district and owner
    d = acc.set_index("account_id").district_id.map(dist.set_index("district_id")[["average_salary", "unemployment_rate_2023"]].to_dict("index"))
    X["district_salary"] = X.account_id.map(lambda a: d[a]["average_salary"])
    X["district_unemp"] = X.account_id.map(lambda a: d[a]["unemployment_rate_2023"])
    owner = disp[disp.type == "owner"].merge(clients, on="client_id").set_index("account_id").birth_date
    X["age"] = (pd.to_datetime(X.loan_start) - pd.to_datetime(X.account_id.map(owner))).dt.days / 365.25

    return X.reset_index(drop=True)


def make_forest():
    return RandomForestClassifier(n_estimators=300, max_depth=6, min_samples_leaf=5,
                                  class_weight="balanced", random_state=SEED, n_jobs=-1)


def cross_validate(X: pd.DataFrame, y: pd.Series):
    """Out-of-fold probabilities + permutation importance averaged over the 5 held-out folds."""
    cols = list(FEATURES)
    oof = np.zeros(len(X))
    imp = np.zeros(len(cols))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y):
        rf = make_forest().fit(X.iloc[tr][cols], y.iloc[tr])
        oof[te] = rf.predict_proba(X.iloc[te][cols])[:, 1]
        pi = permutation_importance(rf, X.iloc[te][cols], y.iloc[te], scoring="roc_auc", n_repeats=10, random_state=SEED, n_jobs=-1)
        imp += pi.importances_mean / 5
    return oof, pd.Series(imp, index=cols).sort_values(ascending=False)


def best_threshold(y, p):
    ts = np.round(np.arange(0.05, 0.95, 0.01), 2)
    f1 = [f1_score(y, p >= t) for t in ts]
    return float(ts[int(np.argmax(f1))])


def what_if_curves(rf, X: pd.DataFrame) -> np.ndarray:
    """Probability of default for every borrower at every GRID value of cash_share, all else fixed (ICE)."""
    cols = list(FEATURES)
    rep = X[cols].loc[X.index.repeat(len(GRID))].copy()
    rep["cash_share"] = np.tile(GRID, len(X))
    return rf.predict_proba(rep)[:, 1].reshape(len(X), len(GRID))


def main():
    X = build_features(DATA)
    y = X.defaulted
    cols = list(FEATURES)

    oof, imp = cross_validate(X, y)
    thr = best_threshold(y, oof)
    pred = (oof >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    fpr, tpr, _ = roc_curve(y, oof)
    keep = np.unique(np.linspace(0, len(fpr) - 1, 60).astype(int))

    rf = make_forest().fit(X[cols], y)
    ice = what_if_curves(rf, X)

    metrics = {"auc": round(roc_auc_score(y, oof), 4), "recall": round(recall_score(y, pred), 4),
               "precision": round(precision_score(y, pred), 4), "accuracy": round(float((pred == y).mean()), 4),
               "base_rate": round(float(y.mean()), 4)}
    order = X.sort_values(["defaulted", "account_id"], ascending=[False, True]).index
    out = {
        "meta": {"loans": int(len(X)), "defaulted": int(y.sum()), "n_estimators": 300, "max_depth": 6,
                 "min_samples_leaf": 5, "folds": 5, "seed": SEED, "features": len(cols),
                 "months_pre_min": int(X.months_pre.min()), "months_pre_median": float(X.months_pre.median()),
                 "cash_share_range": [round(float(X.cash_share.min()), 4), round(float(X.cash_share.max()), 4)]},
        "metrics": metrics,
        "threshold": thr,
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "roc": [[round(float(fpr[i]), 4), round(float(tpr[i]), 4)] for i in keep],
        "importance": [{"key": k, "label": FEATURES[k], "value": round(float(v), 4)} for k, v in imp.head(10).items()],
        "grid": GRID.tolist(),
        "pdp": np.round(ice.mean(axis=0), 4).tolist(),
        "borrowerFields": ["account_id", "defaulted", "cash_share", "oof_prob", "income", "amount", "payment", "joint", "card", "curve"],
        "borrowers": [[int(X.account_id[i]), int(y[i]), round(float(X.cash_share[i]), 4), round(float(oof[i]), 3),
                       round(float(X.income[i]), 0), round(float(X.amount[i]), 0), round(float(X.payment[i]), 0),
                       int(X.joint[i]), int(X.card[i]), np.round(ice[i], 3).tolist()] for i in order],
    }
    dest = ROOT / "data" / "model.js"
    dest.write_text("// generated by prep/build_model.py - do not edit by hand\nwindow.MODEL = " + json.dumps(out, separators=(",", ":")) +";\n", encoding="utf-8")
    print("wrote", dest, f"({dest.stat().st_size / 1024:.0f} KB)")
    print(json.dumps({k: out[k] for k in ["meta", "metrics", "threshold", "confusion", "importance"]}, indent=1))


if __name__ == "__main__":
    main()
