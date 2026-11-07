# 🛡️ Tangerine: Resilience Rewired — Financial Resilience Engine
### Sheridan Datathon 2026 · Tangerine Track (November 7–8, 2026)

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Phase%202%20Validated-success.svg)]()

> **Mission:** Build an explainable, dynamic Financial Resilience Engine that understands any retail banking customer by account ID, simulates multidimensional economic shocks (job loss with EI, inflation, surprise repairs), and generates actionable, personalized resilience plans.

---

## 📑 Project Navigation & Documentation

- 🔍 **[Phase 2: 10 Hidden Behavioral Intelligence Discoveries](reports/phase2_hidden_patterns_discovery.md)** *(NEW)*
- 📊 **[Phase 1: Full Data Intelligence & System Audit Report](reports/phase1_data_intelligence_audit.md)**
- 📁 **[Discovery & Verification Scripts](src/)**
  - [`src/discovery/run_discoveries.py`](src/discovery/run_discoveries.py): Automated reproduction of all 10 discoveries & p-values.
  - [`src/audit/`](src/audit/): Phase 1 accounting and schema verification suite.
- 📖 **[Track Challenge Guidelines](tangerine/README.md)**

---

## 🏆 Headline Discoveries (Phase 2 Scavenger Hunt)

We bypassed generic banking metrics to uncover the **hidden, counterintuitive behavioral patterns** that traditional credit scoring and standard dashboards miss:

| Discovery | What Everyone Assumes | What the Data Proves | Statistical Proof |
|:---|:---|:---|:---|
| **1. The Spousal Shield** | Authorized users are just account noise | **0.00% default rate** across all joint accounts vs. **14.15%** for solo accounts. 100% of all defaults are solo accounts! | $\chi^2 = 21.69, p = 3.21 \times 10^{-6}$ |
| **2. The Statement Canary** | Statement frequency is just an admin setting | Asking for **"statement after each tx"** yields a **23.66% overdraft rate** (vs 5.50%) and **18.75% default rate** (nearly double). | $\chi^2 = 84.49, p = 4.50 \times 10^{-19}$ |
| **3. Inverted Resilience Paradox** | High earners ($>\$20\text{k/mo}$) are safest from shocks | **Top-decile earners crash fastest:** Under a 55% EI shock, their median runway collapses to **3.6 months** (vs 38 months for low earners) due to high dollar burn. | $\chi^2 = 62.44, p = 2.75 \times 10^{-15}$ |
| **4. Cardholder Immunity** | Debit cards encourage impulse spending | Borrowers **without a card are 5x more likely to default** (13.87% vs 2.94%). Classic cardholders default at only **2.26%**. | $\chi^2 = 14.30, p = 1.56 \times 10^{-4}$ |
| **5. Cash Addiction Gradient** | Cash deposits equal electronic transfers | Default risk scales monotonically with cash reliance: **18.12% default rate** for heavy cash depositors vs **3.88%** for transfer recipients. | $\chi^2 = 44.41, p = 1.24 \times 10^{-9}$ |
| **6. Leasing Overextension** | Car leasers are affluent and solvent | Car leasers have **2.4x higher overdraft rates** (13.78% vs 5.79%) despite having twice the median income. | $\chi^2 = 32.25, p = 1.35 \times 10^{-8}$ |
| **7. External Debt Shadow** | Internal loans capture all debt | **35 accounts** are servicing loans to competitor banks via monthly standing orders with zero visibility in the internal loan book. | Cross-table ledger reconciliation |
| **8. Penalty Fee Death Spiral** | Overdraft fees discipline customer behavior | **90.0% of penalty-hit borrowers default** (72 out of 80). The bank penalizes customers into bankruptcy, accelerating credit write-offs. | Contingency analysis |
| **9. Payday Evaporation** | Balances decay smoothly over the month | Money arrives on Days 5–8 and Day 14, and is **instantly drained via cash within 48–72 hours** (Day 14 alone sees \$52.7M in cash withdrawals). | Transaction daily velocity |
| **10. 76% Spend Cushion** | Customer spending is rigid under a shock | Fixed costs ($F$: bills, debt, insurance) make up only **19.07%** of spend; **76.37% is cash withdrawals**, representing huge compressible survival buffer. | Full bank flow decomposition |

👉 **Read the full scientific report:** [**`reports/phase2_hidden_patterns_discovery.md`**](reports/phase2_hidden_patterns_discovery.md)

---

## 📐 Mathematical Framework & Judging Compliance

Our engine reproduces the official Tangerine judging formulas:

| Metric | Official Definition | Dataset Median |
|:---|:---|:---|
| **Typical Monthly Money In ($I$)** | `median(money_in)` | **$7,568.26 CAD** |
| **Typical Fixed Costs ($F$)** | `median(household_bills + insurance + loan_payments)` | **$1,774.17 CAD** |
| **Typical Monthly Spending ($S$)** | `median(money_out)` | **$6,380.20 CAD** |
| **Savings Buffer ($B$)** | `mean(avg_daily_balance)` over account's last 6 months | **$22,325.10 CAD** |
| **Household Bills ($H$)** | `median(household_bills)` | **$1,240.50 CAD** |
| **Active Loan Payment ($P$)** | `monthly_payment` if loan status in `['C', 'D']`, else 0 | **$0.00 CAD** (Active: **$2,330.19**) |

### Runway Calculation Engine:
```python
buffer_left = B - one_off_costs
gap = spending_after_shock - income_after_shock

if buffer_left <= 0:
    runway = 0.0
elif gap <= 0:
    runway = "no shortfall (120+)"
else:
    runway = round(min(buffer_left / gap, 120.0), 1)
```

---

## 🚀 Reproduction & Verification

To reproduce all 10 discoveries and verify statistical test outputs:

```bash
# Run the complete Phase 2 Discovery Reproduction Suite
python src/discovery/run_discoveries.py
```

---

## 👥 Authors
- **Satnam Singh** ([@ProbotisOP](https://github.com/ProbotisOP)) & Sheridan Datathon 2026 Team (CTRL + ALT + WIN)
