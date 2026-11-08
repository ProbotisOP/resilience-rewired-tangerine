# Plan: Random-forest default forecaster (new dashboard page)

## Context
The `Dashboards/` folder has four offline story pages (`index.html` plus pages 1–4). They all read from `data/data.js`, which `prep/build_data.py` builds from the raw CSVs in `D:\Sheridan Hackathon\Tangerine`. This adds a **5th page** with a **random forest** that predicts whether a borrower will default. The model uses several borrower features, but on the page you change just **one: cash share of income**. A slider moves it while everything else stays fixed, and the default probability and prediction update live.

The pages are static and do no calculations themselves. So the model is trained in Python, its results are saved to a JS data file, and no server is needed.

## Approach

### 1. `Dashboards/prep/build_model.py` (new)
- Works the same way as `build_data.py`: by default it reads the `Tangerine` folder, or you can pass a path.
- Builds **one row per loan**: 682 loans, 76 of which defaulted.
- **Only uses history from before each loan started.** Overdrafts and penalties after the loan starts are mostly caused by the default itself, so including them would make the model look better than it is. If a loan has no earlier history, the script uses that account's first 3 months instead and reports how many loans needed this.
- **Features:**
  - **Account:** cash share (the slider variable), median income, median spending, average balance, days spent below zero
  - **Loan:** amount, length, monthly payment, payment-to-income ratio
  - **Household:** joint account, has a card, statement frequency
  - **District and owner:** average salary and unemployment in the district, owner's age
- **Model:** a random forest of 300 trees, with extra weight on defaults because they're rare.
- **Accuracy check:** 5-fold cross-validation, so every loan is scored by a model that never saw it. It reports:
  - AUC (how well the model ranks risky borrowers above safe ones)
  - how many real defaults it catches (recall)
  - how often a "will default" prediction is right (precision)
  - a table of correct and wrong predictions
  - the cut-off probability for calling a borrower a defaulter
- **Feature importance:** the top 10 features the model relies on most.
- **What-if curves:** for every borrower, the default probability at 41 cash-share values from 0% to 100%, with their other features held fixed. Also the average curve across all borrowers.
- **Output:** a new file, `data/model.js` (about 150 KB). `data.js` and the existing pages don't change.

### 2. `Dashboards/5_default_forecaster.html` (new)
Same layout and controls as `4_money_flow.html` (Next/Back buttons, arrow keys, tooltips, dark mode, a table view), reusing `shared/story.js` and `story.css`. Four steps:
1. **How good is the forest?** All loans as dots, sorted by predicted vs actual outcome, with the accuracy numbers.
2. **What does it rely on?** A bar chart of feature importance, with cash share highlighted.
3. **Cash share alone, all else equal.** A faint line for every borrower plus a bold average line, from 0% to 100% cash share.
4. **Your turn: forecast one borrower.**
   - Pick a borrower, or press "random defaulter" / "random non-defaulter".
   - Drag the cash-share slider. It starts at their real value.
   - A readout shows the probability of default and "will default" or "won't default", next to what actually happened to that loan.

### 3. Links and docs
- `index.html`: a 5th card linking to the new page.
- `README.md`: a row for page 5, plus how to rebuild the model.

### Prerequisite
Install scikit-learn first: `pip install scikit-learn`. It isn't installed yet; pandas and numpy are.

## Verification
1. Run `python Dashboards/prep/build_model.py`. It should print the accuracy numbers and create `data/model.js`.
2. Check that the AUC is clearly above 0.5. The script will also confirm that no data from after a loan started is used.
3. Open page 5 in a browser and check:
   - all 4 steps work
   - the slider and borrower picker update the forecast
   - dark mode works and there are no console errors
4. Confirm the new card on `index.html` works and the existing pages still load.
