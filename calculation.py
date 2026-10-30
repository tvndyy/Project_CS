"""
calculation.py - Exchange Cost Planner

Role: "Berechnung & Wechselkurse" (cost calculation)

Turns the city data (from the database) and the user's inputs into a cost
estimate for the exchange semester:
- monthly costs per category (rent, groceries, restaurants, ...)
- one-time costs (flights, visa, deposit, insurance)
- total for the whole stay, with a min-max range
- comparison with the user's own budget

All amounts are in CHF. Conversion into the local currency is done
separately in currency.py.

How to use it in the Streamlit app (see demo_app.py):

    from calculation import estimate_exchange_costs
    result = estimate_exchange_costs(city, "Shared flat room", "moderate", months=5)
    st.metric("Total", f"CHF {result['total']:,.0f}")
"""

# AI assistance:
# Initial implementation developed with assistance from Claude.
# Students reviewed, tested, adapted and must document the exact use
# according to HSG course requirements.

from datetime import date

import pandas as pd

# ---------------------------------------------------------------------------
# Settings (agreed with the team - change them here, in one place)
# ---------------------------------------------------------------------------

# Which database column holds the rent for each housing type
HOUSING_COLUMNS = {
    "Shared flat room": "rent_shared_room",
    "Student dormitory": "rent_dorm",
    "Own apartment": "rent_apartment",
}

# What each lifestyle means. These are our own assumptions - they are
# shown in the app so that users can see how the estimate is made.
LIFESTYLES = {
    "frugal": {
        "groceries_factor": 0.85,          # cooks at home, buys cheap brands
        "restaurant_meals_per_week": 1,
        "evenings_out_per_month": 2,
    },
    "moderate": {
        "groceries_factor": 1.0,
        "restaurant_meals_per_week": 2,
        "evenings_out_per_month": 4,
    },
    "comfortable": {
        "groceries_factor": 1.15,
        "restaurant_meals_per_week": 4,
        "evenings_out_per_month": 8,
    },
}

WEEKS_PER_MONTH = 4.33       # 52 weeks / 12 months
DAYS_PER_MONTH = 30.44       # 365.25 days / 12 months

# Our estimate is not exact. We show a range of +/- 15 % around it.
# (Later the MAE of the ML model could replace this fixed value.)
UNCERTAINTY = 0.15

# All columns the city data must contain (amounts in CHF)
REQUIRED_CITY_COLUMNS = [
    "rent_shared_room",       # per month
    "rent_dorm",              # per month
    "rent_apartment",         # per month
    "groceries_month",        # per month, one person, normal shopping
    "restaurant_meal",        # one meal in an inexpensive restaurant
    "evening_out",            # one evening out (drinks, cinema, ...)
    "transport_pass",         # monthly public transport pass
    "flight_return",          # one return flight from Switzerland
    "visa_fee",               # 0 if no visa is needed
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def value_or_zero(city, column):
    """Return the value of one column, or 0 if it is missing (None / NaN)."""
    value = city.get(column)
    if value is None or pd.isna(value):
        return 0
    return float(value)


def find_missing_values(city):
    """Return a list of required columns that are missing for this city.

    The app should show a warning if this list is not empty, because the
    estimate is then too low.
    """
    missing = []
    for column in REQUIRED_CITY_COLUMNS:
        value = city.get(column)
        if value is None or pd.isna(value):
            missing.append(column)
    return missing


def months_between(start_date, end_date):
    """Length of the stay in months (with decimals), e.g. 4.5 months.

    Both inputs are datetime.date objects, e.g. from st.date_input.
    """
    if end_date <= start_date:
        return 0
    number_of_days = (end_date - start_date).days
    return round(number_of_days / DAYS_PER_MONTH, 1)


# ---------------------------------------------------------------------------
# Step 1: monthly costs
# ---------------------------------------------------------------------------
def calculate_monthly_costs(city, housing_type, lifestyle, trips_per_month=0, cost_per_trip=150):
    """Monthly costs in CHF, per category. Returns a dictionary.

    city            - one row of city data (dict or pandas Series)
    housing_type    - a key of HOUSING_COLUMNS, e.g. "Shared flat room"
    lifestyle       - a key of LIFESTYLES, e.g. "moderate"
    trips_per_month - planned weekend trips per month
    cost_per_trip   - average cost of one trip in CHF (travel + hostel)
    """
    if housing_type not in HOUSING_COLUMNS:
        raise ValueError(f"Unknown housing type: {housing_type}")
    if lifestyle not in LIFESTYLES:
        raise ValueError(f"Unknown lifestyle: {lifestyle}")

    habits = LIFESTYLES[lifestyle]

    rent = value_or_zero(city, HOUSING_COLUMNS[housing_type])
    groceries = value_or_zero(city, "groceries_month") * habits["groceries_factor"]

    # Restaurants and going out: number of times x price of one visit
    restaurants = habits["restaurant_meals_per_week"] * WEEKS_PER_MONTH * value_or_zero(city, "restaurant_meal")
    going_out = habits["evenings_out_per_month"] * value_or_zero(city, "evening_out")

    transport = value_or_zero(city, "transport_pass")
    travel = trips_per_month * cost_per_trip

    monthly_costs = {
        "Rent": rent,
        "Groceries": groceries,
        "Restaurants / going out": restaurants + going_out,
        "Public transport": transport,
        "Leisure / travel": travel,
    }

    # Round every amount to whole francs
    for category in monthly_costs:
        monthly_costs[category] = round(monthly_costs[category])
    return monthly_costs


# ---------------------------------------------------------------------------
# Step 2: one-time costs
# ---------------------------------------------------------------------------
def calculate_one_time_costs(city, housing_type, flights_home=0, deposit_months=1, insurance=0):
    """One-time costs in CHF, per category. Returns a dictionary.

    flights_home   - extra return flights home during the stay (0 = only arrival and departure)
    deposit_months - rental deposit in months of rent (usually paid back at the end!)
    insurance      - extra insurance for the whole stay in CHF (0 if not needed)
    """
    if housing_type not in HOUSING_COLUMNS:
        raise ValueError(f"Unknown housing type: {housing_type}")

    # 1 return flight for arrival + departure, plus any extra flights home
    number_of_flights = 1 + flights_home
    flights = number_of_flights * value_or_zero(city, "flight_return")

    rent = value_or_zero(city, HOUSING_COLUMNS[housing_type])
    deposit = deposit_months * rent

    one_time_costs = {
        "Flights": round(flights),
        "Visa": round(value_or_zero(city, "visa_fee")),
        "Deposit": round(deposit),
        "Insurance": round(insurance),
    }
    return one_time_costs


# ---------------------------------------------------------------------------
# Step 3: totals and range
# ---------------------------------------------------------------------------
def calculate_totals(monthly_costs, one_time_costs, months):
    """Add everything up. Returns a dictionary with the key numbers."""
    monthly_total = sum(monthly_costs.values())
    one_time_total = sum(one_time_costs.values())
    total = monthly_total * months + one_time_total

    return {
        "monthly_total": round(monthly_total),
        "one_time_total": round(one_time_total),
        "total": round(total),
        # The range only applies to the monthly part - flight and visa prices are known in advance
        "total_min": round(monthly_total * months * (1 - UNCERTAINTY) + one_time_total),
        "total_max": round(monthly_total * months * (1 + UNCERTAINTY) + one_time_total),
        "months": months,
    }


# ---------------------------------------------------------------------------
# Step 4: compare with the user's budget
# ---------------------------------------------------------------------------
def compare_with_budget(totals, budget):
    """Compare the estimate with the money the user has (CHF).

    Returns a dictionary with the difference and a short status text:
    "enough", "tight" (budget is inside the range) or "not enough".
    """
    difference = budget - totals["total"]

    if budget >= totals["total_max"]:
        status = "enough"
    elif budget >= totals["total_min"]:
        status = "tight"
    else:
        status = "not enough"

    # How many months the budget lasts after paying the one-time costs
    if totals["monthly_total"] > 0:
        months_covered = (budget - totals["one_time_total"]) / totals["monthly_total"]
    else:
        months_covered = 0

    return {
        "budget": budget,
        "difference": round(difference),
        "status": status,
        "months_covered": round(max(0, months_covered), 1),
    }


# ---------------------------------------------------------------------------
# Table for the charts (used by "App & Design")
# ---------------------------------------------------------------------------
def costs_to_table(monthly_costs, one_time_costs, months):
    """Put all costs into one DataFrame - this is the format for the charts.

    Columns: category, type ("monthly" / "one-time"), chf_per_month, chf_total
    Example for a donut chart:  px.pie(table, names="category", values="chf_total", hole=0.4)
    """
    rows = []
    for category, amount in monthly_costs.items():
        rows.append({
            "category": category,
            "type": "monthly",
            "chf_per_month": amount,
            "chf_total": round(amount * months),
        })
    for category, amount in one_time_costs.items():
        rows.append({
            "category": category,
            "type": "one-time",
            "chf_per_month": None,     # one-time costs have no monthly value
            "chf_total": amount,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Everything in one call - the main function for the app
# ---------------------------------------------------------------------------
def estimate_exchange_costs(city, housing_type, lifestyle, months,
                            trips_per_month=0, cost_per_trip=150,
                            flights_home=0, deposit_months=1, insurance=0, budget=None):
    """Run steps 1-4 and return all results in one dictionary.

    Keys of the result:
      monthly_costs, one_time_costs  - dictionaries per category (CHF)
      monthly_total, one_time_total, total, total_min, total_max, months
      table                          - DataFrame for the charts
      missing_values                 - list of missing city columns (show a warning if not empty)
      budget_check                   - only if a budget was given, otherwise None
    """
    monthly_costs = calculate_monthly_costs(city, housing_type, lifestyle, trips_per_month, cost_per_trip)
    one_time_costs = calculate_one_time_costs(city, housing_type, flights_home, deposit_months, insurance)
    totals = calculate_totals(monthly_costs, one_time_costs, months)

    result = {
        "monthly_costs": monthly_costs,
        "one_time_costs": one_time_costs,
        "table": costs_to_table(monthly_costs, one_time_costs, months),
        "missing_values": find_missing_values(city),
        "budget_check": None,
    }
    result.update(totals)  # adds monthly_total, total, total_min, ... to the result

    if budget is not None and budget > 0:
        result["budget_check"] = compare_with_budget(totals, budget)

    return result


# Run "python calculation.py" to see a quick example in the terminal
if __name__ == "__main__":
    example_city = {
        "rent_shared_room": 800, "rent_dorm": 600, "rent_apartment": 1400,
        "groceries_month": 300, "restaurant_meal": 15, "evening_out": 30,
        "transport_pass": 50, "flight_return": 250, "visa_fee": 0,
    }
    example = estimate_exchange_costs(example_city, "Shared flat room", "moderate",
                                      months=months_between(date(2027, 2, 15), date(2027, 6, 30)),
                                      trips_per_month=1, budget=8000)
    print("Months:", example["months"])
    print("Monthly costs:", example["monthly_costs"])
    print("One-time costs:", example["one_time_costs"])
    print("Total: CHF", example["total"], f"(range {example['total_min']} - {example['total_max']})")
    print("Budget check:", example["budget_check"])
