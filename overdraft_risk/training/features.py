"""Point-in-time feature builder for the vulnerability / stability score study.

Every feature is computed only from information available at a per-account cutoff month,
so the same table can be used to (a) evaluate the hand-weighted formula and (b) fit a model.
"""
import numpy as np
import pandas as pd

from config.settings import DATA_DIR as DATA

CARD_SCALE = {"none": 0.0, "junior": 1 / 3, "classic": 2 / 3, "gold": 1.0}


def load():
    ms = pd.read_csv(DATA / "monthly_summary.csv")
    ms["month"] = pd.PeriodIndex(ms["month"], freq="M")
    ms["neg"] = ((ms["days_below_zero"] > 0) | (ms["min_balance"] < 0)).astype(int)
    ms["fixed"] = ms["household_bills"] + ms["insurance"] + ms["loan_payments"]
    ms["net"] = ms["money_in"] - ms["money_out"]
    ms = ms.sort_values(["account_id", "month"]).reset_index(drop=True)

    accounts = pd.read_csv(DATA / "accounts.csv")
    disp = pd.read_csv(DATA / "dispositions.csv")
    cards = pd.read_csv(DATA / "cards.csv", parse_dates=["issued"])
    so = pd.read_csv(DATA / "standing_orders.csv")
    loans = pd.read_csv(DATA / "loans.csv", parse_dates=["loan_start"])
    districts = pd.read_csv(DATA / "districts.csv")
    tx = pd.read_csv(DATA / "transactions.csv", usecols=["account_id", "date", "purpose"], parse_dates=["date"])
    pen = tx[tx["purpose"].fillna("").str.contains("penalty")].copy()
    pen["month"] = pen["date"].dt.to_period("M")
    return dict(ms=ms, accounts=accounts, disp=disp, cards=cards, so=so, loans=loans,
                districts=districts, pen=pen[["account_id", "month"]])


def static_tables(d):
    acc = d["accounts"].merge(d["districts"][["district_id", "average_salary", "unemployment_rate_2022"]],
                              on="district_id", how="left")
    acc["unemployment_rate_2022"] = acc["unemployment_rate_2022"].fillna(acc["unemployment_rate_2022"].median())
    acc["stmt_score"] = acc["frequency"].map({"monthly statement": 2, "weekly statement": 1,
                                              "statement after each transaction": 0})
    acc["stmt_weekly"] = (acc["frequency"] == "weekly statement").astype(int)
    acc["stmt_each_txn"] = (acc["frequency"] == "statement after each transaction").astype(int)
    n_clients = d["disp"].groupby("account_id")["client_id"].nunique().rename("n_clients")
    acc = acc.merge(n_clients, on="account_id", how="left")
    acc["joint"] = (acc["n_clients"] >= 2).astype(int)

    owner = d["disp"][d["disp"]["type"] == "owner"][["disposition_id", "account_id"]]
    cards = d["cards"].merge(owner, on="disposition_id", how="inner")[["account_id", "card_type", "issued"]]
    cards = cards.sort_values("issued").drop_duplicates("account_id", keep="first")

    so = d["so"].copy()
    so["purpose"] = so["purpose"].fillna("other")
    so_tot = so.groupby("account_id")["amount"].sum().rename("so_total")
    so_lease = so[so["purpose"] == "leasing"].groupby("account_id")["amount"].sum().rename("so_leasing")
    so_t = pd.concat([so_tot, so_lease], axis=1).fillna(0.0).reset_index()
    return acc, cards, so_t


def build(d, cutoff, min_hist=12, win=12):
    """cutoff: pd.Series indexed by account_id of pd.Period('M'). Returns one row per eligible account."""
    ms = d["ms"].merge(cutoff.rename("cut"), left_on="account_id", right_index=True)
    ms = ms[ms["month"] <= ms["cut"]].copy()
    ms["k"] = ms.groupby("account_id").cumcount(ascending=False)  # 0 = last month <= cutoff
    g_all = ms.groupby("account_id")
    n_hist = g_all.size().rename("hist_months")
    ok = n_hist[n_hist >= min_hist].index
    ms = ms[ms["account_id"].isin(ok)]

    w = ms[ms["k"] < win]
    h = win // 2
    g = w.groupby("account_id")
    f = pd.DataFrame(index=sorted(ok))
    f.index.name = "account_id"
    mi, mo = g["money_in"].sum(), g["money_out"].sum()
    nw = g.size()
    f["hist_months"] = n_hist
    f["net_margin"] = (mi - mo) / mi.replace(0, np.nan)
    f["outflow_months_share"] = (w["net"] < 0).groupby(w["account_id"]).mean()
    f["fixed_to_in"] = g["fixed"].sum() / mi.replace(0, np.nan)
    f["fixed_to_out"] = g["fixed"].sum() / mo.replace(0, np.nan)
    f["bills_to_in"] = g["household_bills"].sum() / mi.replace(0, np.nan)
    f["loanpay_to_in"] = g["loan_payments"].sum() / mi.replace(0, np.nan)
    f["fees_to_in"] = g["bank_fees"].sum() / mi.replace(0, np.nan)
    f["cash_dep_share"] = g["cash_deposits"].sum() / mi.replace(0, np.nan)
    f["pension_share"] = g["pension_in"].sum() / mi.replace(0, np.nan)
    f["transfer_in_share"] = g["transfers_in"].sum() / mi.replace(0, np.nan)
    f["cash_wd_share"] = g["cash_withdrawals_genuine"].sum() / mo.replace(0, np.nan)
    f["income_cv"] = g["money_in"].std() / g["money_in"].mean().replace(0, np.nan)
    f["spend_cv"] = g["money_out"].std() / g["money_out"].mean().replace(0, np.nan)
    f["log_mean_in"] = np.log1p(g["money_in"].mean())
    l6 = ms[ms["k"] < h].groupby("account_id")
    p6 = ms[(ms["k"] >= h) & (ms["k"] < win)].groupby("account_id")
    b6 = ms[ms["k"] < 6].groupby("account_id")
    f["income_trend"] = np.log1p(l6["money_in"].mean()) - np.log1p(p6["money_in"].mean())
    f["spend_trend"] = np.log1p(l6["money_out"].mean()) - np.log1p(p6["money_out"].mean())
    buf6 = b6["avg_daily_balance"].mean()
    f["log_buffer6"] = np.log1p(buf6.clip(lower=0))
    f["buffer_months"] = (buf6 / (mo / nw).replace(0, np.nan)).clip(upper=60)
    f["min_bal_to_out"] = (g["min_balance"].min() / (mo / nw).replace(0, np.nan)).clip(-5, 60)
    f["neg_months_win"] = g["neg"].sum()
    f["neg_days_win"] = g["days_below_zero"].sum()
    gh = ms.groupby("account_id")
    f["neg_months_hist"] = gh["neg"].sum()
    pen = d["pen"].merge(cutoff.rename("cut"), left_on="account_id", right_index=True)
    pen = pen[pen["month"] <= pen["cut"]]
    f["penalty_hist"] = pen.groupby("account_id").size().reindex(f.index).fillna(0).gt(0).astype(int)
    f["penalty_count_hist"] = pen.groupby("account_id").size().reindex(f.index).fillna(0)

    acc, cards, so_t = static_tables(d)
    f = f.reset_index().merge(acc[["account_id", "stmt_score", "stmt_weekly", "stmt_each_txn", "joint",
                                   "average_salary", "unemployment_rate_2022"]], on="account_id", how="left")
    f = f.merge(cutoff.rename("cut").reset_index(), on="account_id", how="left")
    f = f.merge(cards, on="account_id", how="left")
    cut_end = f["cut"].dt.to_timestamp(how="end")
    has_card = f["issued"].notna() & (f["issued"] <= cut_end)
    f["card_type"] = np.where(has_card, f["card_type"], "none")
    f["has_card"] = has_card.astype(int)
    f["card_scale"] = f["card_type"].map(CARD_SCALE)
    f = f.merge(so_t, on="account_id", how="left").fillna({"so_total": 0.0, "so_leasing": 0.0})
    f["leasing_share"] = np.where(f["so_total"] > 0, f["so_leasing"] / f["so_total"].replace(0, np.nan), 0.0)
    f["so_to_in"] = f["so_total"] / (mi.reindex(f["account_id"]).values / nw.reindex(f["account_id"]).values + 1e-9)
    f["so_to_in"] = f["so_to_in"].clip(upper=5)

    ln = d["loans"].merge(cutoff.rename("cut"), left_on="account_id", right_index=True)
    ln = ln[ln["loan_start"] <= ln["cut"].dt.to_timestamp(how="end")]
    f = f.merge(ln[["account_id", "monthly_payment", "amount", "status"]], on="account_id", how="left")
    f["has_loan"] = f["monthly_payment"].notna().astype(int)
    avg_in = (mi / nw).reindex(f["account_id"]).values
    f["loan_pay_to_in"] = (f["monthly_payment"].fillna(0) / (avg_in + 1e-9)).clip(upper=5)
    f["loan_amount_to_in"] = (f["amount"].fillna(0) / (avg_in * 12 + 1e-9)).clip(upper=10)
    f = f.drop(columns=["issued", "monthly_payment", "amount"])
    # median-income decile over full history <= cutoff (D1..D10 -> 0.1..1.0)
    med_in = gh["money_in"].median().reindex(f["account_id"]).values
    f["income_decile"] = pd.qcut(pd.Series(med_in).rank(method="first"), 10, labels=False).values / 10 + 0.1
    num = f.select_dtypes("number").columns
    f[num] = f[num].replace([np.inf, -np.inf], np.nan)
    return f, ms


def outcome(d, cutoff, horizon=12, min_obs=6):
    """1 if any negative-balance month or penalty-interest charge in the `horizon` months after cutoff."""
    ms = d["ms"].merge(cutoff.rename("cut"), left_on="account_id", right_index=True)
    ahead = (ms["month"] - ms["cut"]).apply(lambda x: x.n)
    fut = ms[(ahead >= 1) & (ahead <= horizon)]
    g = fut.groupby("account_id")
    out = pd.DataFrame({"n_obs": g.size(), "y_neg": g["neg"].max()})
    pen = d["pen"].merge(cutoff.rename("cut"), left_on="account_id", right_index=True)
    pa = (pen["month"] - pen["cut"]).apply(lambda x: x.n)
    pen_acc = set(pen[(pa >= 1) & (pa <= horizon)]["account_id"])
    out["y_pen"] = out.index.isin(pen_acc).astype(int)
    out["y"] = ((out["y_neg"] > 0) | (out["y_pen"] > 0)).astype(int)
    return out[out["n_obs"] >= min_obs]


def formula_score(f, d, include_status=True, within_customer=False):
    """The user's hand-weighted formula, implemented literally. Returns DataFrame of components + total.
    Uses history <= cutoff already embedded in f; recomputes annual terms from d['ms'] and f['cut']."""
    ms = d["ms"].merge(f[["account_id", "cut"]], on="account_id")
    ms = ms[ms["month"] <= ms["cut"]].copy()
    ms["yr"] = ms["month"].dt.year
    ay = ms.groupby(["account_id", "yr"]).agg(m=("month", "size"), net=("net", "mean"), fixed=("fixed", "sum"),
                                              mo=("money_out", "sum")).reset_index()
    ay["fix_ratio"] = np.where(ay["mo"] > 0, ay["fixed"] / ay["mo"].replace(0, np.nan), 0.0)
    if within_customer:
        gb = ay.groupby("account_id")["net"]
        sd = gb.transform("std")
        ay["z"] = ((ay["net"] - gb.transform("mean")) / sd).fillna(0.0)
    else:
        ay["z"] = (ay["net"] - ay["net"].mean()) / ay["net"].std()
    ay["t1"] = ay["z"] * ay["m"]
    ay["t2"] = ay["fix_ratio"] * ay["m"]
    agg = ay.groupby("account_id").agg(T1=("t1", "mean"), T2=("t2", "mean"))
    s = f.set_index("account_id").join(agg)
    cash = ms.groupby("account_id")[["cash_deposits", "money_in"]].sum()
    cash_ratio = (cash["cash_deposits"] / cash["money_in"].replace(0, np.nan)).fillna(0)
    out = pd.DataFrame(index=s.index)
    out["T1_net_flow"] = s["T1"]
    out["T2_fixed_cost"] = s["T2"]
    out["statement"] = s["stmt_score"]
    out["joint"] = s["joint"]
    out["income_decile_term"] = 1 - s["income_decile"]
    out["card_term"] = 1 - s["card_scale"]
    out["cash_term"] = 1 - cash_ratio.reindex(s.index)
    out["leasing_term"] = 1 - s["leasing_share"]
    out["no_penalty"] = 1 - s["penalty_hist"]
    st = s["status"].map({"A": 1.0, "C": 0.6, "D": 0.4, "B": 0.0}).fillna(0.0)
    out["status_term"] = st if include_status else 0.0
    out["score"] = out.sum(axis=1)
    return out
