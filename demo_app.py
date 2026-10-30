"""
demo_app.py - Exchange Cost Planner (DEMO of the calculation and currency modules)

Start with:   streamlit run demo_app.py

This page only shows how "App & Design" can use calculation.py and
currency.py. The city numbers below are PLACEHOLDERS (dummy data) until
"Daten & Datenbank" delivers the real data from SQLite.
"""

# AI assistance:
# Initial implementation developed with assistance from Claude.
# Students reviewed, tested, adapted and must document the exact use
# according to HSG course requirements.

from datetime import date

import plotly.express as px
import streamlit as st

from calculation import HOUSING_COLUMNS, LIFESTYLES, estimate_exchange_costs, months_between
from currency import convert_from_chf, get_exchange_rates

# ---------------------------------------------------------------------------
# DUMMY city data - NOT real prices. Will be replaced by a database query,
# e.g. city = load_city("Milan") from the "Daten & Datenbank" module.
# All amounts in CHF.
# ---------------------------------------------------------------------------
DUMMY_CITIES = {
    "Milan (dummy)": {
        "currency": "EUR", "rent_shared_room": 750, "rent_dorm": 600, "rent_apartment": 1300,
        "groceries_month": 300, "restaurant_meal": 15, "evening_out": 25,
        "transport_pass": 35, "flight_return": 200, "visa_fee": 0,
    },
    "Singapore (dummy)": {
        "currency": "SGD", "rent_shared_room": 900, "rent_dorm": 550, "rent_apartment": 2200,
        "groceries_month": 350, "restaurant_meal": 8, "evening_out": 40,
        "transport_pass": 70, "flight_return": 900, "visa_fee": 30,
    },
    "Copenhagen (dummy)": {
        "currency": "DKK", "rent_shared_room": 850, "rent_dorm": 700, "rent_apartment": 1500,
        "groceries_month": 330, "restaurant_meal": 20, "evening_out": 35,
        "transport_pass": None,  # missing on purpose -> shows the warning
        "flight_return": 250, "visa_fee": 0,
    },
}



# Streamlit runs this whole script again after every click. To avoid asking
# the API every time, we remember successful answers in st.session_state.
# Failed requests are NOT remembered, so the app tries again next time.
def get_rate_cached(currency_code):
    key = "rates_" + currency_code
    if key in st.session_state:
        return st.session_state[key]

    rates, source = get_exchange_rates([currency_code])
    if rates is not None:
        st.session_state[key] = (rates, source)
    return rates, source


st.set_page_config(page_title="Exchange Cost Planner - Demo", page_icon="E", layout="wide")
st.title("Exchange Cost Planner – calculation demo")
st.warning("Demo with **placeholder data** – the city prices are not real.")

# Layout from the kick-off: inputs left, results right, breakdown below
left, right = st.columns([1, 2])

# ---------------------------------------------------------------------------
# Inputs (left)
# ---------------------------------------------------------------------------
with left:
    st.subheader("Your plan")
    city_name = st.selectbox("City", list(DUMMY_CITIES.keys()))
    start_date = st.date_input("Start", value=date(2027, 2, 15))
    end_date = st.date_input("End", value=date(2027, 6, 30))
    housing_type = st.selectbox("Housing", list(HOUSING_COLUMNS.keys()))
    lifestyle = st.radio("Lifestyle", list(LIFESTYLES.keys()), index=1, horizontal=True)
    trips_per_month = st.slider("Weekend trips per month", 0, 4, 1)
    flights_home = st.number_input("Extra flights home", min_value=0, max_value=5, value=0)
    budget = st.number_input("My budget (CHF, optional)", min_value=0, max_value=100000, value=0, step=500)

city = DUMMY_CITIES[city_name]
months = months_between(start_date, end_date)

# ---------------------------------------------------------------------------
# Results (right)
# ---------------------------------------------------------------------------
with right:
    if months == 0:
        st.error("The end date must be after the start date.")
        st.stop()

    result = estimate_exchange_costs(
        city, housing_type, lifestyle, months,
        trips_per_month=trips_per_month, flights_home=flights_home, budget=budget,
    )

    if len(result["missing_values"]) > 0:
        st.warning("Missing data for this city: " + ", ".join(result["missing_values"])
                   + ". The estimate is too low.")

    st.subheader(f"Estimate for {months} months")
    col1, col2, col3 = st.columns(3)
    col1.metric("Per month", f"CHF {result['monthly_total']:,}")
    col2.metric("One-time costs", f"CHF {result['one_time_total']:,}")
    col3.metric("Total", f"CHF {result['total']:,}")
    st.write(f"Range: **CHF {result['total_min']:,} – {result['total_max']:,}** (it is an estimate)")

    # Local currency
    rates, source = get_rate_cached(city["currency"])
    if rates is None:
        st.info("Exchange rate not available – amounts are shown in CHF only.")
    else:
        rate = rates[city["currency"]]
        st.write(f"≈ **{convert_from_chf(result['total'], rate):,} {city['currency']}** total "
                 f"(1 CHF = {rate} {city['currency']}, {source})")

    # Budget comparison
    check = result["budget_check"]
    if check is not None:
        if check["status"] == "enough":
            st.success(f"Your budget is enough (CHF {check['difference']:,} left over).")
        elif check["status"] == "tight":
            st.warning("Your budget is tight – it is inside the uncertainty range.")
        else:
            st.error(f"Your budget is CHF {-check['difference']:,} too low. "
                     f"It covers about {check['months_covered']} months.")

# ---------------------------------------------------------------------------
# Breakdown (below)
# ---------------------------------------------------------------------------
st.subheader("Cost breakdown")
table = result["table"]
chart_table = table[table["chf_total"] > 0]  # hide categories with CHF 0 (e.g. no visa needed)
chart_left, chart_right = st.columns(2)
with chart_left:
    fig_donut = px.pie(chart_table, names="category", values="chf_total", hole=0.4, title="Share of total costs")
    st.plotly_chart(fig_donut)
with chart_right:
    fig_bar = px.bar(chart_table, x="chf_total", y="category", color="type", orientation="h",
                     labels={"chf_total": "CHF for the whole stay", "category": ""}, title="Costs per category")
    st.plotly_chart(fig_bar)

st.dataframe(table, hide_index=True)

with st.expander("How is this calculated?"):
    habits = LIFESTYLES[lifestyle]
    st.markdown(
        f"""
        - **Rent:** price for "{housing_type}" in this city.
        - **Groceries:** normal monthly shopping × {habits['groceries_factor']} ({lifestyle}).
        - **Restaurants / going out:** {habits['restaurant_meals_per_week']} meals per week and
          {habits['evenings_out_per_month']} evenings out per month × the local price.
        - **Leisure / travel:** {trips_per_month} trips per month × CHF 150.
        - **One-time:** {1 + flights_home} return flight(s), visa, 1 month rent deposit (usually paid back).
        - **Range:** monthly costs ± 15 %.
        """
    )
