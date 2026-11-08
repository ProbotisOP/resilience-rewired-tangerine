import streamlit as st


def render_methodology():
    st.title("🧮 How we calculate it")
    st.caption(
        "Here is where the figures come from and what they mean. Scenarios use the supplied records to show possible outcomes; they are not forecasts."
    )

    st.header("A typical month for one account")
    st.markdown(
        """
        We sort each account's available monthly records and calculate:

        | Measure | Calculation |
        |---|---|
        | **Money in** | Median of available monthly `money_in` rows |
        | **Spending** | Median of available monthly `money_out` rows |
        | **Fixed costs** | For each month, add household bills + insurance + loan payments; take the median of those monthly sums |
        | **Household bills** | Median of available monthly household-bill rows |
        | **Buffer** | Average `avg_daily_balance` across up to the latest six available monthly rows |
        | **Monthly gap** | Spending minus money in, rounded to cents |

        Accounts can have different amounts of history. The buffer uses up to the latest six
        available records, which may not be six consecutive calendar months.
        """
    )

    st.header("How the runway is worked out")
    st.latex(r"\text{Runway} = \min\left(\frac{B}{S-I}, 120\right)")
    st.markdown(
        """
        If the buffer is empty or below zero, the result is 0 months. If money coming in covers
        spending and the buffer is positive, the result is shown as 120+ months. Otherwise, the
        app divides the buffer by the monthly shortfall, up to a limit of 120 months, and rounds
        to one decimal place.

        Portfolio charts count accounts with less than 3, 6 or 12 months. An account at exactly
        6.0 months is not counted as below six months.
        """
    )

    st.header("What-if scenarios")
    st.markdown(
        """
        A what-if can change recorded money coming in, increase household bills, and/or add a
        one-time cost. The app recalculates the monthly shortfall, remaining buffer and estimated
        runway from the account's records. Recorded money in is not verified pay and does not
        confirm eligibility for benefits.

        The timeline repeats the same monthly shortfall for each month shown. It is an illustration,
        not a forecast of future transactions.
        """
    )

    st.header("How much monthly improvement reaches a target?")
    st.markdown(
        "For the selected number of months, the app spreads the available buffer across that period "
        "and calculates how much the monthly shortfall would need to improve:"
    )
    st.latex(
        r"\text{Required improvement} = "
        r"\max\left(0,\ \text{monthly gap} - "
        r"\frac{\text{available buffer}}{\text{target months}}\right)"
    )
    st.markdown(
        """
        The monthly change you choose is a separate what-if. It changes the estimated monthly
        shortfall and runway. The app does not decide which costs you could change.
        """
    )

    st.header("What the data can—and cannot—say")
    st.markdown(
        """
        - An authorized user is someone listed as having account access. This does not tell us
          their relationship to the account holder.
        - A pattern in the records does not explain what caused it. What-if results are simulated,
          not observed outcomes.
        - Cash withdrawals are not automatically treated as discretionary spending.
          A user may model an adjustment explicitly.
        - Payment instructions to another provider do not confirm a contract, monthly bill or debt.
        - When fixed costs are zero in the records, the plan asks for an estimate instead of
          guessing essential costs.
        - Optional AI can rephrase an explanation but does not calculate or change the figures.
        - These calculations summarize the supplied data. They are not financial advice, a credit
          decision, or a complete picture of a person's finances.
        - The calculations are not compared with outside benchmarks.
        """
    )
