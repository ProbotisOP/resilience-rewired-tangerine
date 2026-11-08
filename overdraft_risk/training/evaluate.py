"""6-month-horizon version of the vulnerability model with a train / validation / test split.

Run:  python -m overdraft_risk.training.evaluate
"""
import warnings

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import build, formula_score, load, outcome

warnings.filterwarnings("ignore")

HORIZON = 6
CUTOFFS = ["2020-12", "2021-06", "2021-12", "2022-06", "2022-12", "2023-06", "2023-12", "2024-06", "2024-12", "2025-06"]
SPLIT = {"train": CUTOFFS[:6], "valid": CUTOFFS[6:8], "test": CUTOFFS[8:]}

PRED_12 = ["log_buffer6", "buffer_months", "min_bal_to_out", "log_mean_in", "cash_wd_share",
           "outflow_months_share", "spend_trend", "loanpay_to_in", "so_to_in", "penalty_hist",
           "neg_months_win", "joint"]
PRED_14 = PRED_12 + ["pension_share", "hist_months"]


def make_panel(d, accs, win, min_hist):
    parts = []
    for c in CUTOFFS:
        cut = pd.Series(pd.Period(c, "M"), index=accs, name="cut")
        cut.index.name = "account_id"
        f, _ = build(d, cut, min_hist=min_hist, win=win)
        f = f.merge(outcome(d, cut, horizon=HORIZON, min_obs=HORIZON).reset_index(), on="account_id")
        fs = formula_score(f, d, include_status=False)
        f = f.set_index("account_id").join(fs.add_prefix("F_"))
        f["cutoff"] = c
        parts.append(f.reset_index())
    return pd.concat(parts, ignore_index=True)


def fit(df, cols, C):
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(C=C, max_iter=5000)).fit(df[cols], df["y"])


def metrics(y, p):
    return dict(AUC=roc_auc_score(y, p), AP=average_precision_score(y, p),
                Brier=brier_score_loss(y, p), LogLoss=log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)))


def cluster_ci(df, p, n=1000, seed=0):
    """Bootstrap over accounts (an account can appear at several cutoffs)."""
    rng = np.random.default_rng(seed)
    ids, inv = np.unique(df["account_id"].values, return_inverse=True)
    y = df["y"].values
    out = []
    for _ in range(n):
        w = rng.multinomial(len(ids), np.full(len(ids), 1 / len(ids)))[inv].astype(float)
        if (y * w).sum() == 0:
            continue
        out.append((roc_auc_score(y, p, sample_weight=w), average_precision_score(y, p, sample_weight=w)))
    return np.percentile(np.array(out), [2.5, 97.5], axis=0).round(3)


def top_k(y, p, frac=0.10):
    k = int(round(len(y) * frac))
    idx = np.argsort(-p)[:k]
    return y[idx].sum() / y.sum(), y[idx].mean(), y[idx].mean() / y.mean()


def main():
    d = load()
    accs = d["ms"]["account_id"].unique()
    P = make_panel(d, accs, win=6, min_hist=6)
    P["split"] = P["cutoff"].map({c: s for s, cs in SPLIT.items() for c in cs})
    print("== split sizes (rows = account x cutoff) ==")
    print(P.groupby("split").agg(rows=("y", "size"), accounts=("account_id", "nunique"), events=("y", "sum"),
                                 rate=("y", "mean")).round(4).to_string())
    print(P.groupby(["split", "cutoff"]).agg(rows=("y", "size"), events=("y", "sum"), rate=("y", "mean")).round(4).to_string())
    tr, va, te = (P[P.split == s] for s in ["train", "valid", "test"])

    print("\n== choose ridge strength C on validation (log loss) ==")
    best = None
    for C in [0.003, 0.01, 0.03, 0.1, 0.3, 1.0]:
        m = fit(tr, PRED_12, C)
        ll = log_loss(va["y"], m.predict_proba(va[PRED_12])[:, 1])
        auc = roc_auc_score(va["y"], m.predict_proba(va[PRED_12])[:, 1])
        print(f"C={C:<6} valid logloss={ll:.4f} AUC={auc:.3f}")
        if best is None or ll < best[1]:
            best = (C, ll)
    C = best[0]
    print("chosen C =", C)

    trva = pd.concat([tr, va])
    final = fit(trva, PRED_12, C)
    p = final.predict_proba(te[PRED_12])[:, 1]
    y = te["y"].values
    base = trva["y"].mean()

    print("\n== TEST metrics (12-predictor, 6m window, 6m horizon) ==")
    mm = metrics(y, p)
    mm["Brier_skill"] = 1 - mm["Brier"] / brier_score_loss(y, np.full(len(y), base))
    print({k: round(v, 4) for k, v in mm.items()})
    print("cluster-bootstrap 95% CI  AUC, AP:", cluster_ci(te, p).T.tolist())
    print("mean predicted", p.mean().round(4), "observed rate", y.mean().round(4), "train base rate", round(base, 4))
    rec, prec, lift = top_k(y, p)
    print(f"top 10% flagged: recall={rec:.3f} precision={prec:.3f} lift={lift:.1f}x")
    rec, prec, lift = top_k(y, p, 0.20)
    print(f"top 20% flagged: recall={rec:.3f} precision={prec:.3f} lift={lift:.1f}x")
    lp = np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
    cal = LogisticRegression(C=1e6, max_iter=1000).fit(lp.reshape(-1, 1), y)
    print("calibration slope", cal.coef_[0][0].round(3), "intercept", cal.intercept_[0].round(3))
    q = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
    print(pd.DataFrame({"decile": q, "y": y, "p": p}).groupby("decile").agg(
        n=("y", "size"), events=("y", "sum"), observed=("y", "mean"), predicted=("p", "mean")).round(3).to_string())
    for c in SPLIT["test"]:
        s = (te["cutoff"] == c).values
        print(f"  test cutoff {c}: n={s.sum()} events={y[s].sum()} AUC={roc_auc_score(y[s], p[s]):.3f}")

    print("\n== comparisons on the same TEST rows ==")
    rows = {}
    rows["Base rate only"] = metrics(y, np.full(len(y), base))
    rows["Original hand formula (score x -1)"] = {"AUC": roc_auc_score(y, -te["F_score"]), "AP": average_precision_score(y, -te["F_score"])}
    bm = te["buffer_months"].fillna(te["buffer_months"].median())
    rows["Buffer months alone"] = {"AUC": roc_auc_score(y, -bm), "AP": average_precision_score(y, -bm)}
    m14 = fit(trva, PRED_14, C)
    rows["14 predictors (incl. #9, #10)"] = metrics(y, m14.predict_proba(te[PRED_14])[:, 1])
    rows["12 predictors (this model)"] = metrics(y, p)
    print(pd.DataFrame(rows).T.round(4).to_string())

    print("\n== sensitivity: 12-month look-back windows instead of 6 (same horizon, same accounts) ==")
    P12 = make_panel(d, accs, win=12, min_hist=6)
    P12["split"] = P12["cutoff"].map({c: s for s, cs in SPLIT.items() for c in cs})
    t12, v12, e12 = (P12[P12.split == s] for s in ["train", "valid", "test"])
    m12 = fit(pd.concat([t12, v12]), PRED_12, C)
    p12 = m12.predict_proba(e12[PRED_12])[:, 1]
    print({k: round(v, 4) for k, v in metrics(e12["y"].values, p12).items()})

    print("\n== robustness: hold out 30% of ACCOUNTS (never seen in training at any date) ==")
    rng = np.random.default_rng(42)
    hold = set(rng.choice(accs, size=int(0.3 * len(accs)), replace=False))
    trh = trva[~trva["account_id"].isin(hold)]
    teh = te[te["account_id"].isin(hold)]
    mh = fit(trh, PRED_12, C)
    ph = mh.predict_proba(teh[PRED_12])[:, 1]
    print("holdout accounts: rows", len(teh), "events", int(teh["y"].sum()), {k: round(v, 4) for k, v in metrics(teh["y"].values, ph).items()})

    print("\n== final coefficients (fit on train+valid) ==")
    sc, lr = final[1], final[-1]
    std = pd.Series(lr.coef_[0], index=PRED_12)
    raw = pd.Series(lr.coef_[0] / sc.scale_, index=PRED_12)
    print(pd.DataFrame({"std_coef": std, "per_unit_coef": raw, "mean": sc.mean_, "sd": sc.scale_}).round(4).to_string())
    print("intercept (standardised scale):", lr.intercept_[0].round(4))


if __name__ == "__main__":
    main()
