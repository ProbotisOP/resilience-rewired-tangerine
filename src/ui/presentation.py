from config.scenarios import ShockScenario


_SCENARIO_COPY = {
    "BASELINE": (
        "Keep things steady",
        "What if the usual monthly money in and spending continue, with no added bill?",
    ),
    "JOB_LOSS_EI_55": (
        "Income takes a dip",
        "What if recorded monthly money-in falls to 55% of its usual level? This is a "
        "scenario, not confirmed payroll or EI.",
    ),
    "FURNACE_REPAIR": (
        "The repair bill arrives",
        "What if a one-off repair costs the same as one typical month of spending? "
        "This is a test amount, not a quoted repair bill.",
    ),
    "COMBINED_SHOCK": (
        "Two plot twists at once",
        "What if recorded monthly money-in falls to 55% and household bills rise 15%? "
        "A double what-if, not a prediction.",
    ),
}


def scenario_display_name(scenario: ShockScenario) -> str:
    """Return a plain-language UI name while retaining the official scenario object."""
    return _SCENARIO_COPY.get(
        scenario.scenario_id, (scenario.name, scenario.description)
    )[0]


def scenario_display_description(scenario: ShockScenario) -> str:
    """Return a plain-language explanation of the scenario assumptions."""
    return _SCENARIO_COPY.get(
        scenario.scenario_id, (scenario.name, scenario.description)
    )[1]
