"""
check_calculation.py - Exchange Cost Planner

Simple checks for calculation.py and currency.py ("Berechnungen prüfen").
Every expected number below was calculated BY HAND, so if a check fails,
either the code or our hand calculation is wrong.

Run:   python check_calculation.py
Works without internet.
"""

# AI assistance:
# Initial implementation developed with assistance from Claude.
# Students reviewed, tested, adapted and must document the exact use
# according to HSG course requirements.

from datetime import date

from calculation import (calculate_monthly_costs, calculate_one_time_costs, calculate_totals,
                         compare_with_budget, costs_to_table, estimate_exchange_costs,
                         find_missing_values, months_between)
from currency import convert_from_chf

# Simple example city with round numbers (CHF), so we can calculate by hand
TEST_CITY = {
    "rent_shared_room": 800, "rent_dorm": 600, "rent_apartment": 1400,
    "groceries_month": 300, "restaurant_meal": 10, "evening_out": 20,
    "transport_pass": 50, "flight_return": 200, "visa_fee": 0,
}

number_of_checks = 0


def check(description, actual, expected):
    """Print OK or FAILED for one check."""
    global number_of_checks
    number_of_checks = number_of_checks + 1
    if actual == expected:
        print("OK     ", description)
    else:
        print("FAILED ", description, "-> got", actual, "but expected", expected)
        raise SystemExit(1)


# --- Monthly costs, moderate lifestyle, shared flat, 1 trip ---
# Restaurants: 2 meals/week x 4.33 weeks x 10 = 86.6 ; going out: 4 x 20 = 80 -> 166.6 -> 167
monthly = calculate_monthly_costs(TEST_CITY, "Shared flat room", "moderate", trips_per_month=1, cost_per_trip=150)
check("rent shared flat", monthly["Rent"], 800)
check("groceries moderate (factor 1.0)", monthly["Groceries"], 300)
check("restaurants + going out", monthly["Restaurants / going out"], 167)
check("public transport", monthly["Public transport"], 50)
check("travel 1 trip x 150", monthly["Leisure / travel"], 150)

# --- Lifestyle changes the result ---
frugal = calculate_monthly_costs(TEST_CITY, "Shared flat room", "frugal")
check("groceries frugal (300 x 0.85 = 255)", frugal["Groceries"], 255)
comfortable = calculate_monthly_costs(TEST_CITY, "Own apartment", "comfortable")
check("rent own apartment", comfortable["Rent"], 1400)
check("comfortable costs more than frugal", sum(comfortable.values()) > sum(frugal.values()), True)

# --- One-time costs: 1 + 1 flights, deposit 1 month rent ---
one_time = calculate_one_time_costs(TEST_CITY, "Shared flat room", flights_home=1, deposit_months=1, insurance=100)
check("flights 2 x 200", one_time["Flights"], 400)
check("deposit = 1 month rent", one_time["Deposit"], 800)
check("insurance", one_time["Insurance"], 100)

# --- Totals: monthly 800+300+167+50+150 = 1467 ; 5 months = 7335 ; one-time 400+0+800+100 = 1300 ---
totals = calculate_totals(monthly, one_time, 5)
check("monthly total", totals["monthly_total"], 1467)
check("one-time total", totals["one_time_total"], 1300)
check("total = 7335 + 1300", totals["total"], 8635)
check("minimum = 7335 x 0.85 + 1300", totals["total_min"], 7535)
check("maximum = 7335 x 1.15 + 1300", totals["total_max"], 9735)

# --- Budget comparison ---
check("budget 10000 is enough", compare_with_budget(totals, 10000)["status"], "enough")
check("budget 9000 is tight", compare_with_budget(totals, 9000)["status"], "tight")
check("budget 5000 is not enough", compare_with_budget(totals, 5000)["status"], "not enough")
check("budget 5000 lasts (5000-1300)/1467 = 2.5 months", compare_with_budget(totals, 5000)["months_covered"], 2.5)

# --- Table for the charts: 5 monthly + 4 one-time rows ---
table = costs_to_table(monthly, one_time, 5)
check("table has 9 rows", len(table), 9)
check("table total equals total", int(table["chf_total"].sum()), 8635)

# --- Dates ---
check("15 Feb to 30 Jun 2027 = 135 days / 30.44 = 4.4 months", months_between(date(2027, 2, 15), date(2027, 6, 30)), 4.4)
check("end before start = 0 months", months_between(date(2027, 6, 30), date(2027, 2, 15)), 0)

# --- Missing data ---
incomplete_city = dict(TEST_CITY)
incomplete_city["transport_pass"] = None
check("missing value is found", find_missing_values(incomplete_city), ["transport_pass"])
check("missing value counts as 0", calculate_monthly_costs(incomplete_city, "Student dormitory", "frugal")["Public transport"], 0)

# --- Everything in one call ---
result = estimate_exchange_costs(TEST_CITY, "Shared flat room", "moderate", 5, trips_per_month=1,
                                 flights_home=1, insurance=100, budget=9000)
check("main function gives the same total", result["total"], 8635)
check("main function includes budget check", result["budget_check"]["status"], "tight")

# --- Wrong input ---
try:
    calculate_monthly_costs(TEST_CITY, "Castle", "moderate")
    check("unknown housing type raises an error", False, True)
except ValueError:
    check("unknown housing type raises an error", True, True)

# --- Currency conversion (no internet needed) ---
check("1000 CHF x 1.07 = 1070", convert_from_chf(1000, 1.07), 1070)

print()
print("All", number_of_checks, "checks passed.")
