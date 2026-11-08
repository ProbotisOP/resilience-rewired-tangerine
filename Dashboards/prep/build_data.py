"""Build Dashboards/data/data.js from the raw challenge CSVs (run once; the dashboards themselves compute nothing).

    python Dashboards/prep/build_data.py [path/to/Tangerine]

Every figure in the dashboards comes from this file's output, so the numbers are reproducible.
Where a figure differs from reports/phase2_hidden_patterns_discovery.md, the report value is
kept alongside it under "report" so the dashboards can say so openly.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parents[1] / "Tangerine"

acc = pd.read_csv(DATA / "accounts.csv")
loans = pd.read_csv(DATA / "loans.csv")
disp = pd.read_csv(DATA / "dispositions.csv")
cards = pd.read_csv(DATA / "cards.csv")
so = pd.read_csv(DATA / "standing_orders.csv")
ms = pd.read_csv(DATA / "monthly_summary.csv").sort_values(["account_id", "month"])
tx = pd.read_csv(DATA / "transactions.csv", usecols=["account_id", "date", "direction", "operation", "purpose", "amount"])
tx = tx.dropna(subset=["amount"])  # file ends with one truncated row

# ------------------------------------------------------------------ account level (judges' definitions)
g = ms.groupby("account_id")
a = pd.DataFrame({
    "I": g.money_in.median(),
    "S": g.money_out.median(),
    "B": g.tail(6).groupby("account_id").avg_daily_balance.mean(),
    "neg": g.days_below_zero.sum() > 0,
    "cash_share": g.cash_deposits.sum() / (g.money_in.sum() + 1e-6),
})
gap = a.S - 0.55 * a.I
a["runway"] = np.where(a.B <= 0, 0, np.where(gap <= 0, 120, np.minimum(a.B / gap, 120)))
a = a.join(acc.set_index("account_id")[["frequency"]])
joint = set(disp.loc[disp.type == "authorized user", "account_id"])
card_by_acc = disp.merge(cards, on="disposition_id").groupby("account_id").card_type.first()
a["joint"] = a.index.isin(joint)
a["card"] = a.index.map(card_by_acc).fillna("none")
a["leasing"] = a.index.isin(so.loc[so.purpose == "leasing", "account_id"])

# ------------------------------------------------------------------ one record per loan (for the dot story)
L = loans.merge(a, left_on="account_id", right_index=True)
L["cash_q"] = pd.qcut(L.cash_share, 4, labels=["Q1", "Q2", "Q3", "Q4"]).astype(str)
FREQ = {"monthly statement": "monthly", "weekly statement": "weekly", "statement after each transaction": "per_tx"}
L["freq"] = L.frequency.map(FREQ)
L["flags"] = (~L.joint).astype(int) + (L.card == "none").astype(int) + (L.cash_q == "Q4").astype(int) + (L.freq != "monthly").astype(int)
L = L.sort_values(["defaulted", "account_id"], ascending=[False, True])
loan_rows = [[int(r.account_id), int(r.defaulted), r.status, int(r.joint), int(r.card != "none"), r.cash_q, r.freq, int(r.flags)]
             for r in L.itertuples()]
cash_q_ranges = L.groupby("cash_q").cash_share.agg(["min", "max"]).round(3).to_dict("index")

# ------------------------------------------------------------------ deciles (#3)
a["decile"] = pd.qcut(a.I, 10, labels=[f"D{i}" for i in range(1, 11)])
dec = a.groupby("decile", observed=True).agg(
    I=("I", "median"), S=("S", "median"), B=("B", "median"), runway=("runway", "median"),
    under6=("runway", lambda s: (s < 6).mean()), under3=("runway", lambda s: (s < 3).mean()),
    overdraft=("neg", "mean")).round(4).reset_index()

# ------------------------------------------------------------------ per-account group stats
def grp(col):
    t = a.groupby(col).agg(n=("neg", "size"), neg=("neg", "sum"), I=("I", "median"), B=("B", "median"))
    return {str(k): {kk: (float(vv) if not isinstance(vv, (np.integer, int)) else int(vv)) for kk, vv in v.items()}
            for k, v in t.to_dict("index").items()}

# ------------------------------------------------------------------ penalty spiral (#8)
pen = tx[tx.purpose == "penalty interest (negative balance)"]
pen_counts = pen.groupby("account_id").size()
pen_loans = loans[loans.account_id.isin(pen_counts.index)]

# ------------------------------------------------------------------ external debt (#7)
lp = so[so.purpose == "loan payment"]
external = sorted(set(lp.account_id) - set(loans.account_id))

# ------------------------------------------------------------------ payday cycle (#9)
tx["day"] = pd.to_datetime(tx.date).dt.day
credit = tx.direction.str.startswith("credit")
days = pd.DataFrame({
    "in": tx[credit].groupby("day").amount.sum(),
    "out": tx[~credit].groupby("day").amount.sum(),
    "cash": tx[tx.operation == "cash withdrawal"].groupby("day").amount.sum(),
}).fillna(0) / 1e6

# ------------------------------------------------------------------ spending decomposition (#10)
parts = ["household_bills", "loan_payments", "insurance", "bank_fees", "cash_withdrawals_genuine", "transfers_out_other", "card_withdrawals"]
tot = ms.money_out.sum()
decomp = {p: round(float(ms[p].sum() / tot), 4) for p in parts}

out = {
    "source": str(DATA.name),
    "totals": {"accounts": int(len(a)), "loans": int(len(loans)), "defaulted": int(loans.defaulted.sum()),
               "transactions_in_file": int(len(tx)), "tx_last_date": str(tx.date.max())},
    "loanFields": ["account_id", "defaulted", "status", "joint", "card", "cash_q", "freq", "flags"],
    "loans": loan_rows,
    "cashQRanges": cash_q_ranges,
    "deciles": dec.to_dict("records"),
    "jointAccounts": grp("joint"),
    "freqAccounts": grp("frequency"),
    "cardAccounts": grp("card"),
    "leasing": grp("leasing"),
    "leasingWithLoans": int(loans.account_id.isin(a.index[a.leasing]).sum()),
    "penalty": {"accounts": int(len(pen_counts)), "mean_hits": round(float(pen_counts.mean()), 2),
                "max_hits": int(pen_counts.max()), "with_loans": int(len(pen_loans)),
                "status": {k: int(v) for k, v in pen_loans.status.value_counts().items()}},
    "external": {"loan_payment_orders": int(len(lp)), "internal_loans": int(len(loans)), "external_accounts": len(external),
                 "amounts": sorted(lp[lp.account_id.isin(external)].amount.round(2).tolist()),
                 "median_payment": round(float(lp[lp.account_id.isin(external)].amount.median()), 2),
                 "total_monthly": round(float(lp[lp.account_id.isin(external)].amount.sum()), 2),
                 # to_bank codes are the same set for internal and unmatched orders, so they can't prove "competitor bank"
                 "bank_codes_internal": int(lp[~lp.account_id.isin(external)].to_bank.nunique()),
                 "bank_codes_unmatched": int(lp[lp.account_id.isin(external)].to_bank.nunique())},
    "payday": {"day": days.index.tolist(), **{k: days[k].round(2).tolist() for k in days}},
    "spend": decomp,
    "typical": {"I": float(a.I.median()), "S": float(a.S.median()), "B": float(a.B.median()),
                "F": float((ms.household_bills + ms.insurance + ms.loan_payments).groupby(ms.account_id).median().median())},
    # Values printed in the report that did NOT reproduce from these CSVs (shown as footnotes)
    "report": {
        "cash_q_rates": {"Q1": 0.0388, "Q2": 0.0573, "Q3": 0.0815, "Q4": 0.1812},
        "d10_runway": 3.7, "d10_under6": 0.844, "d1_runway": 38.1,
        "penalty": {"accounts": 264, "with_loans": 80, "defaulted": 72},
        "payday_claim": "inflows drained by cash within 48-72 hours",
    },
}
dest = ROOT / "data" / "data.js"
dest.parent.mkdir(exist_ok=True)
dest.write_text("// generated by prep/build_data.py - do not edit by hand\nwindow.DATA = " + json.dumps(out, default=str) + ";\n", encoding="utf-8")
print("wrote", dest, f"({dest.stat().st_size/1024:.0f} KB)")
print(json.dumps({k: out[k] for k in ["totals", "penalty", "external", "spend", "typical", "cashQRanges", "leasing", "freqAccounts", "jointAccounts"]}, indent=1, default=str))
