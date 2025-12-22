# Flight Agent

This repository contains a small flight-finding assistant with two interfaces:

- `agent.py` — a CLI agent that accepts natural-language prompts and uses a Google GenAI model (via LangChain) to orchestrate searches and tools.
- `streamlit_app.py` — a Streamlit web demo that calls the local `fetch_raw_flights()` and `find_direct_flights()` functions and displays results in a clean UI with booking links.

This README explains how to set up, run, and troubleshoot both interfaces.

## Prerequisites

- Python 3.11 or newer (the project was developed and tested on 3.11).
- A SerpApi key for scraping Google Flights results (used by `flight_data.py`).
- A Google GenAI API key if you plan to run the LLM agent (`agent.py`).

Recommended: create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

## Environment variables

Create a `.env` file in the project root with the following (example):

```
SERPAPI_KEY=your_serpapi_key_here
GOOGLE_API_KEY=your_google_genai_key_here
# Optional: override or set models
GOOGLE_MODEL=models/gemini-2.5-pro
GOOGLE_FALLBACK_MODELS=models/gemini-2.5-flash,models/gemini-flash-lite-latest
```

Do NOT commit your `.env` or API keys to source control.

## Streamlit demo

Start the web UI:

```powershell
streamlit run streamlit_app.py
```

Notes about the Streamlit app
- The UI accepts a city name or a 3-letter IATA code. It will try to map common city names to IATA automatically; the app shows the detected IATA codes before searching so you can confirm.
- The app writes a `temp_search.json` file containing the raw SerpApi response when a search succeeds; this is useful for debugging.
- Booking links: the app shows a [Book] link when a URL is available in the SerpApi response or forms a best-effort deep link using the `booking_token` and search URL.

## CLI agent

Run the interactive CLI agent:

```powershell
python agent.py
```

The agent uses `langchain` + `langchain-google-genai` to call Google GenAI models and a small tool (`search_flights_tool`) that fetches flight data and filters it.

If you get model errors (NOT_FOUND or RESOURCE_EXHAUSTED):
- Use `python list_models.py` to list models available to your `GOOGLE_API_KEY`.
- Set `GOOGLE_MODEL` to a supported model name.
- If you hit quota limits, enable billing or use a different project/key, or rely on fallback models configured in `GOOGLE_FALLBACK_MODELS`.

## Debugging

- If the Streamlit app returns "No data returned from the flight fetch":
	- Confirm `SERPAPI_KEY` is set and valid.
	- Try entering explicit IATA codes (e.g., `DEL`, `BOM`) rather than city names.
	- Inspect `temp_search.json` (written by the app) to see where flight results appear; share it if you want precise parsing fixes.

- If the agent raises quota/model errors, run `python list_models.py` and/or check Google Cloud Console for quota and billing.

## Files of interest

- `agent.py` — interactive CLI agent
- `list_models.py` — helper that calls the GenAI ListModels endpoint using `GOOGLE_API_KEY`
- `flight_data.py` — fetches raw flight data from SerpApi
- `flight_filter.py` — extracts direct flights and normalizes fields (price, link)
- `streamlit_app.py` — Streamlit demo UI

## Next steps / improvements

- Add an offline CSV-based IATA/airport lookup for robust city->IATA mapping.
- Improve deep-link generation for bookings if SerpApi returns booking tokens in a consistent format.
- Add caching (Streamlit `st.cache_data`) to reduce repeated API calls during UI exploration.

If you'd like, I can add the IATA lookup CSV and a confirmation dropdown so the UI never guesses wrong and always shows choices to the user.
