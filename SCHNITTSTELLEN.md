# Schnittstellen – Berechnung & Wechselkurse

Dieses Dokument beschreibt, **welche Daten das Modul braucht** (von „Daten & Datenbank“) und **was es
liefert** (an „App & Design“). Bitte am Kick-off gemeinsam absegnen. Änderungen nur nach Absprache,
weil sonst der Code der anderen nicht mehr passt.

## Dateien

| Datei | Inhalt |
|-------|--------|
| `calculation.py` | Kostenberechnung: monatliche und einmalige Kosten, Total, Bandbreite, Budgetvergleich |
| `currency.py` | Wechselkurse (Frankfurter-API), Umrechnung CHF → Landeswährung, gespeicherte Kurse als Notlösung |
| `demo_app.py` | Beispielseite in Streamlit mit **Platzhalter-Daten**. Sie zeigt, wie man die Module einbaut |
| `check_calculation.py` | 30 Prüfungen mit von Hand gerechneten Ergebnissen (`python check_calculation.py`) |

Ausprobieren:

```bash
cd exchange_cost_planner
pip install -r requirements.txt
python check_calculation.py      # alle Prüfungen müssen "OK" zeigen
streamlit run demo_app.py        # Demo im Browser
python currency.py               # prüft, welche unserer Währungen die API kennt (braucht Internet)
```

---

## 1. Was ich von „Daten & Datenbank“ brauche

Pro Stadt **eine Zeile** als `dict` oder pandas `Series` (z. B. eine Zeile aus `pd.read_sql_query`).
Wichtig: **kein** `sqlite3.Row`, denn das kennt `.get()` nicht.

**Alle Beträge in CHF.** Die Umrechnung macht ihr einmal beim Erfassen der Daten. Bitte Kurs und
Datum dokumentieren. So hängt die Berechnung nie von der Internetverbindung ab.

| Spalte | Bedeutung | Einheit |
|--------|-----------|---------|
| `city` | Name der Stadt | Text |
| `currency` | Landeswährung, z. B. `EUR`, `SGD` (nur für die Anzeige) | Text, ISO-Code |
| `rent_shared_room` | WG-Zimmer | CHF pro Monat |
| `rent_dorm` | Studentenwohnheim | CHF pro Monat |
| `rent_apartment` | Eigene Wohnung / Studio | CHF pro Monat |
| `groceries_month` | Lebensmittel für 1 Person, normaler Einkauf | CHF pro Monat |
| `restaurant_meal` | 1 Essen in einem günstigen Restaurant | CHF pro Besuch |
| `evening_out` | 1 Abend im Ausgang (Getränke, Kino …) | CHF pro Abend |
| `transport_pass` | ÖV-Monatsabo (Studierendentarif, falls vorhanden) | CHF pro Monat |
| `flight_return` | 1 Hin- und Rückflug ab der Schweiz | CHF |
| `visa_fee` | Visumgebühr für CH-Bürger, `0` falls keines nötig | CHF |

**Fehlende Werte:** einfach leer lassen (`NULL` / `None`). Die Berechnung zählt sie als 0, und
`result["missing_values"]` listet sie auf, damit die App eine Warnung zeigen kann.

Vorschlag für eine Lese-Funktion im Datenbank-Modul:

```python
def load_city(city_name):
    connection = sqlite3.connect(DATABASE_PATH)
    table = pd.read_sql_query("SELECT * FROM cities WHERE city = ?", connection, params=(city_name,))
    connection.close()
    return table.iloc[0]   # eine Zeile als pandas Series
```

---

## 2. Was ich an „App & Design“ liefere

### Kostenberechnung – eine Funktion für alles

```python
from calculation import estimate_exchange_costs, months_between, HOUSING_COLUMNS, LIFESTYLES

months = months_between(start_date, end_date)          # z. B. 4.4
result = estimate_exchange_costs(
    city,                 # Zeile aus der Datenbank
    housing_type,         # "Shared flat room" | "Student dormitory" | "Own apartment"
    lifestyle,            # "frugal" | "moderate" | "comfortable"
    months,
    trips_per_month=1,    # optional
    cost_per_trip=150,    # optional, CHF pro Ausflug
    flights_home=0,       # optional, zusätzliche Heimflüge
    deposit_months=1,     # optional, Mietkaution in Monatsmieten
    insurance=0,          # optional, CHF für den ganzen Aufenthalt
    budget=None,          # optional, eigenes Budget in CHF
)
```

Für die Auswahlfelder: `list(HOUSING_COLUMNS.keys())` und `list(LIFESTYLES.keys())`.

### Was im Ergebnis steht

| Schlüssel | Typ | Beispiel |
|-----------|-----|----------|
| `monthly_costs` | dict | `{"Rent": 800, "Groceries": 300, "Restaurants / going out": 250, "Public transport": 50, "Leisure / travel": 150}` |
| `one_time_costs` | dict | `{"Flights": 250, "Visa": 0, "Deposit": 800, "Insurance": 0}` |
| `monthly_total` | int (CHF) | `1550` |
| `one_time_total` | int (CHF) | `1050` |
| `total` | int (CHF) | `7870` |
| `total_min`, `total_max` | int (CHF) | `6847`, `8893` (monatlicher Teil ± 15 %) |
| `months` | float | `4.4` |
| `table` | DataFrame | Spalten `category`, `type` („monthly“/„one-time“), `chf_per_month`, `chf_total` → **für die Diagramme** |
| `missing_values` | list | `["transport_pass"]`, leer = alles da |
| `budget_check` | dict oder None | `{"budget": 8000, "difference": 130, "status": "tight", "months_covered": 4.5}` |

`status` ist `"enough"`, `"tight"` (Budget liegt innerhalb der Bandbreite) oder `"not enough"`.

Diagramm-Beispiel:

```python
chart_table = result["table"][result["table"]["chf_total"] > 0]
st.plotly_chart(px.pie(chart_table, names="category", values="chf_total", hole=0.4))
```

### Wechselkurse

```python
from currency import get_exchange_rates, convert_from_chf

rates, source = get_exchange_rates([city["currency"]])
if rates is None:
    st.info("Exchange rate not available – amounts in CHF only.")
else:
    rate = rates[city["currency"]]                       # Wert von 1 CHF in Landeswährung
    st.write(convert_from_chf(result["total"], rate), city["currency"], f"({source})")
```

- `source` ist ein Text für die App, z. B. `"live (ECB, 2026-10-30)"` oder
  `"saved rates from 2026-10-28 (API not reachable)"`.
- Wenn die API nicht erreichbar ist, werden die **zuletzt gespeicherten Kurse** aus
  `data/last_rates.json` verwendet. Diese Datei ist in `.gitignore` und wird automatisch erstellt.
- **Tipp:** Streamlit führt das Skript bei jedem Klick neu aus. Damit nicht jedes Mal die API gefragt
  wird, merkt sich `demo_app.py` erfolgreiche Antworten in `st.session_state` (Funktion
  `get_rate_cached`). Diese Funktion bitte in die richtige App übernehmen.

---

## 3. Annahmen, die wir im Team festlegen müssen

Diese Werte stehen oben in `calculation.py` und lassen sich an **einer Stelle** ändern:

| Annahme | Aktueller Wert | Frage ans Team |
|---------|----------------|----------------|
| Lifestyle „frugal“ | Lebensmittel × 0.85, 1 Restaurant/Woche, 2 Abende/Monat | passt das? |
| Lifestyle „moderate“ | Lebensmittel × 1.0, 2 Restaurants/Woche, 4 Abende/Monat | passt das? |
| Lifestyle „comfortable“ | Lebensmittel × 1.15, 4 Restaurants/Woche, 8 Abende/Monat | passt das? |
| Kosten pro Ausflug | CHF 150 | aus Erfahrungsberichten ableiten? |
| Bandbreite | ± 15 % auf die monatlichen Kosten | später durch den MAE des ML-Modells ersetzen |
| Kaution | 1 Monatsmiete (wird meist zurückbezahlt!) | in der App erwähnen? |
| Flüge | 1 Hin- und Rückflug + Heimflüge | ok |

---

## 4. Verbindung zum ML-Teil

Die Berechnung ist **regelbasiert** (Preise × Mengen). Laut Kursanforderung braucht es zusätzlich ein
selbst trainiertes Modell. Zwei Möglichkeiten, die zu diesem Modul passen:

- Das ML-Modell sagt die **Monatskosten** aus Umfragedaten voraus, und die App zeigt beides: „Rechner: CHF X,
  Modell (aus echten Erfahrungen): CHF Y“.
- Der **MAE** des Modells ersetzt die fixe Bandbreite von ± 15 % (Konstante `UNCERTAINTY`).

Das bitte mit der ML-Person und dem Tutor abstimmen.
