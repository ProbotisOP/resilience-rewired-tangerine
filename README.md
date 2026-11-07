# 🛡️ Tangerine: Resilience Rewired — Financial Resilience Engine
### Sheridan Datathon 2026 · Tangerine Track (November 7–8, 2026)

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Phase%201%20Complete-orange.svg)]()

> **Mission:** Build a dynamic Financial Resilience Engine that understands any retail banking customer by account ID, simulates multidimensional economic shocks (job loss with EI, inflation, surprise repairs), and generates actionable, personalized resilience plans.

---

## 📑 Project Navigation & Documentation

- 📊 **[Phase 1: Full Data Intelligence & System Audit Report](reports/phase1_data_intelligence_audit.md)**
- 📁 **[Verification & Audit Scripts](src/audit/)**
- 📖 **[Track Challenge Guidelines](tangerine/README.md)**

---

## 💡 Executive Summary of Phase 1 Discoveries

During initial forensic data intelligence across 4,500 bank accounts, 1,056,320 transactions, and 185,326 monthly ledger entries, our engine uncovered foundational behavioral patterns:

### 1. The 100% Overdraft Determinism Anomaly
- **0 out of 606 (0.0%)** borrowers with healthy loans (`Status A` and `C`) ever experienced a negative balance.
- **76 out of 76 (100.0%)** borrowers who defaulted or fell into distressed debt (`Status B` and `D`) experienced negative balances.
- Negative balance frequency operates as a deterministic distress indicator within this credit portfolio.

### 2. The Underwriting Pre-Origination Blindspot
- Of the 76 defaulted credit facilities, **27 borrowers (35.5%)** exhibited active negative balance events **prior to loan origination**.
- Traditional underwriting mechanisms approved these loans despite clear historical transactional distress already recorded on the bank's own ledger.

### 3. The Silent Deficit Population
- **1,181 accounts (26.2%)** operate at an ongoing monthly deficit ($S > I$) at baseline, surviving by steadily eroding accumulated savings buffers long before entering negative balances.

---

## 📐 Mathematical Framework & Judging Compliance

Our engine adheres strictly to the Tangerine judging specification:

| Metric | Formula / Source | Baseline Dataset Median |
| :--- | :--- | :--- |
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

## 🗄️ Relational Architecture

```
districts ──< accounts ──< transactions
                │    ├──< monthly_summary
                │    ├──< standing_orders
                │    └──< loans
                └──< dispositions >── clients
                          └──< cards
```

- **Accounts:** 4,500 retail accounts (tenure 12–72 months; median 36 months).
- **Clients & Dispositions:** 5,369 clients, 4,500 primary owners, and 869 authorized users (100% heterosexual couples with matching age distributions).
- **Cards:** 892 cards, 100% held by primary account owners.
- **Credit Facilities:** 682 loans, exactly 448 active at the end of 2025.

---

## 🚀 Reproduction & Verification

To reproduce our data intelligence audit and verify all numbers:

```bash
# 1. Inspect data and schema integrity
python src/audit/inspect_data.py

# 2. Run detailed demographic, card, and negative balance audit
python src/audit/detailed_audit.py

# 3. Verify Tangerine judging metrics and runway formulas
python src/audit/test_metrics.py

# 4. Analyze credit defaults vs pre-origination distress
python src/audit/loan_stress_analysis.py
```

---

## 👥 Authors
- **Satnam Singh** ([@ProbotisOP](https://github.com/ProbotisOP)) & Sheridan Datathon 2026 Team
