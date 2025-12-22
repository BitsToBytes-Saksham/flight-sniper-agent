import json
import datetime
import streamlit as st
import pandas as pd

# Try to load dotenv, but don't crash at import-time if it's missing.
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        return
    st.warning("python-dotenv not installed; .env will not be loaded. Install with `pip install python-dotenv` to load environment variables automatically.")

from flight_data import fetch_raw_flights
from flight_filter import find_direct_flights

load_dotenv()


def convert_to_iata(loc: str):
    """Convert common city names to IATA codes. If `loc` is already a 3-letter code, return it uppercased.
    If unknown, return None.
    """
    if not loc:
        return None
    s = loc.strip()
    # If user already entered an IATA code
    if len(s) == 3 and s.isalpha():
        return s.upper()

    mapping = {
        "delhi": "DEL",
        "new delhi": "DEL",
        "mumbai": "BOM",
        "bombay": "BOM",
        "hyderabad": "HYD",
        "bangalore": "BLR",
        "bengaluru": "BLR",
        "lucknow": "LKO",
        "chennai": "MAA",
        "kolkata": "CCU",
        "pune": "PNQ",
        "ahmedabad": "AMD",
        "goa": "GOI",
        "cochin": "COK",
        "kochi": "COK",
        "jaipur": "JAI",
        "visakhapatnam": "VTZ",
        "vishakhapatnam": "VTZ",
        "trivandrum": "TRV",
        "kanpur": "KNU",
        "varanasi": "VNS",
        "nagpur": "NAG",
        "patna": "PAT",
    }

    code = mapping.get(s.lower())
    if code:
        return code

    # fallback: try first three letters uppercased (best-effort), but prefer explicit IATA
    guess = ''.join([c for c in s if c.isalpha()])[:3].upper()
    if len(guess) == 3:
        return guess

    return None

st.set_page_config(page_title="Flight Agent — Demo", layout="wide")
st.title("Flight Agent — Streamlit Demo")
st.write("Find direct flights and see varied-airline recommendations. This demo uses your local project functions to fetch and filter flights.")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    origin = st.text_input("Origin city or IATA (e.g., Delhi or DEL)", value="Delhi")
with col2:
    destination = st.text_input("Destination city or IATA (e.g., Hyderabad or HYD)", value="Hyderabad")
with col3:
    date_input = st.date_input("Travel date", datetime.date.today() + datetime.timedelta(days=30))

st.sidebar.header("Search options")
tolerance = st.sidebar.slider("Near-cheapest tolerance (%)", 0, 20, 5)
top_n = st.sidebar.number_input("Max distinct-airline recommendations", min_value=1, max_value=10, value=3)
max_table = st.sidebar.number_input("Max rows in table", min_value=5, max_value=200, value=50)

if st.button("Search"):
    origin_code = convert_to_iata(origin)
    destination_code = convert_to_iata(destination)

    if not origin_code or not destination_code:
        st.error("Could not determine IATA codes for origin or destination. Please enter 3-letter IATA codes (e.g., DEL, BOM) or use a common city name like 'Delhi' or 'Mumbai'.")
        st.stop()
    # Show detected IATA codes so user can confirm (helps catch bad guesses like 'KAN' vs 'KNU')
    st.info(f"Using IATA codes — Origin: {origin_code}, Destination: {destination_code}")
    date_str = date_input.strftime("%Y-%m-%d")

    with st.spinner("Searching flights..."):
        try:
            raw = fetch_raw_flights(origin_code, destination_code, date_str)
            if not raw:
                st.error("No data returned from the flight fetch. Possible causes: invalid IATA codes, expired SerpApi key, or no flights on that date.")
                st.info(f"Tried origin={origin_code} destination={destination_code} date={date_str}")
                st.stop()

                # Debug: show top-level keys and sizes so we can diagnose missing flight lists
                try:
                    keys = list(raw.keys()) if isinstance(raw, dict) else []
                    summary = {k: (len(raw[k]) if isinstance(raw[k], list) else type(raw[k]).__name__) for k in keys}
                    st.debug = getattr(st, 'debug', None)
                    st.write("Response keys summary:", summary)
                except Exception:
                    pass

            with open("temp_search.json", "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)

            flights = find_direct_flights("temp_search.json")
            if not flights:
                st.info("No direct flights found for that route/date.")
            else:
                # Build recommendations: cheapest per airline, then fill up to top_n
                unique = {}
                for f in flights:
                    if f["airline"] not in unique:
                        unique[f["airline"]] = f

                diverse = sorted(list(unique.values()), key=lambda x: x["price_value"]) 
                recommended = diverse[:top_n]

                if len(recommended) < top_n:
                    seen = {f["flight_number"] for f in recommended}
                    for f in flights:
                        if f["flight_number"] in seen:
                            continue
                        recommended.append(f)
                        seen.add(f["flight_number"]) 
                        if len(recommended) >= top_n:
                            break

                st.subheader("Recommended (varied airlines)")
                for f in recommended:
                    link = f.get("link") or ""
                    if isinstance(link, str) and link.startswith("http"):
                        st.markdown(f"- **{f['airline']} ({f['flight_number']})** — {f['price_raw']} — Departs: {f['departure']} — [Book]({link})")
                    else:
                        st.markdown(f"- **{f['airline']} ({f['flight_number']})** — {f['price_raw']} — Departs: {f['departure']} — [No link]")

                # Near-cheapest alternatives
                cheapest = flights[0]["price_value"]
                threshold = cheapest * (1 + tolerance / 100.0)
                alts = [f for f in flights if f["price_value"] <= threshold and f["flight_number"] not in {r['flight_number'] for r in recommended}]
                if alts:
                    st.subheader(f"Alternatives within {tolerance}%")
                    for f in alts[:10]:
                        link = f.get("link") or ""
                        if isinstance(link, str) and link.startswith("http"):
                            st.markdown(f"- **{f['airline']} ({f['flight_number']})** — {f['price_raw']} — Departs: {f['departure']} — [Book]({link})")
                        else:
                            st.markdown(f"- **{f['airline']} ({f['flight_number']})** — {f['price_raw']} — Departs: {f['departure']} — [No link]")

                st.subheader("All direct flights")
                df = pd.DataFrame(flights)
                # Normalize link column for display
                if 'link' in df.columns:
                    df['link'] = df['link'].fillna('No link')
                display_cols = [c for c in ["airline", "flight_number", "departure", "arrival", "duration", "price_raw", "link"] if c in df.columns]
                st.dataframe(df[display_cols].head(max_table))

        except Exception as e:
            st.error(f"Error during search: {e}")
