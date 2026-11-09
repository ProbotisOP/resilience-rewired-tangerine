import streamlit as st


def render_methodology():
    st.title("🧮 How we calculate it")
    st.caption(
        "No black boxes: the figures come from the supplied records and the formulas below. "
        "Scenarios are what-ifs, not forecasts."
    )

    st.header("A typical month for one account")
    st.markdown(
        """
        For an account, monthly records are sorted by month. We calculate:

        | Measure | Calculation |
        |---|---|
        | Plain-language figure | How it is calculated |
        |---|---|
        | **Money in** | Median of available monthly `money_in` rows |
        | **Spending** | Median of available monthly `money_out` rows |
        | **Fixed costs** | For each month, add household bills + insurance + loan payments; take the median of those monthly sums |
        | **Household bills** | Median of available monthly household-bill rows |
        | **Buffer** | Average `avg_daily_balance` across up to the latest six available monthly rows |
        | **Monthly gap** | Spending minus money in, rounded to cents |

        Account histories can differ in length. The buffer uses up to the latest six
        available rows; it does not imply six complete calendar months when records
        are missing.
        """
    )

    st.header("How the runway is worked out")
    st.latex(r"\text{Runway} = \min\left(\frac{B}{S-I}, 120\right)")
    st.markdown(
        """
        In plain language: if the buffer is empty, the result is 0.0 months. If
        money in covers spending and the buffer is positive, the display is 120+
        months. Otherwise, divide the buffer by the monthly gap and cap the result
        at 120 months. The app rounds runway to one decimal.

        For portfolio charts, it rounds first, then counts accounts strictly below
        3, 6, or 12 months. So a displayed result of exactly 6.0 is **not** below
        six months.
        """
    )

    st.header("What-if scenarios")
    st.markdown(
        """
        Scenario settings change recorded money in, household bills, and/or add a
        one-off cost. The app recalculates the monthly gap, remaining buffer and
        runway using the same account figures. A money-in multiplier applies to
        recorded money in; it does not verify employment income or benefit eligibility.

        The timeline applies the same monthly gap in each selected scenario month.
        That makes it a clear simulation, not a forecast of future transactions.
        """
    )

    st.header("How much monthly improvement reaches a target?")
    st.markdown(
        "For a selected target duration, the optimizer spreads the available buffer "
        "across the target months and calculates the remaining monthly improvement:"
    )
    st.latex(
        r"\text{Required improvement} = "
        r"\max\left(0,\ \text{monthly gap} - "
        r"\frac{\text{available buffer}}{\text{target months}}\right)"
    )
    st.markdown(
        """
        The selected monthly adjustment is a separate what-if. It changes the
        proposed monthly gap and estimated runway; it does not change the official
        challenge runway. The app does not choose which costs are adjustable.
        """
    )

    st.header("What the data can—and cannot—say")
    st.markdown(
        """
        - Authorized-user records indicate account access only; they do not
          establish spouses, partners, or household relationships.
        - Observed associations do not establish causation. Simulated shocks are
          not observed outcomes.
        - Cash withdrawals are not automatically treated as discretionary spending.
          A user may model an adjustment explicitly.
        - Standing orders and external-destination payment instructions do not
          prove contractual monthly commitments or outstanding external debt.
        - A zero fixed-cost figure is shown as missing/zero evidence; the planner
          asks the user to enter any essential-cost assumption rather than
          inventing one.
        - Snowflake is not connected in this application. The SQL files are
          optional setup examples. Gemini, when configured, is an explanation
          layer and does not calculate or alter financial metrics.
        - These calculations summarize the supplied data; they are not financial
          advice, credit decisions, or a full picture of a person's finances.
        - No external benchmark is used to calibrate the calculations.
        """
    )
