import os
from serpapi import GoogleSearch
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()
API_KEY = os.getenv("SERPAPI_KEY")

def fetch_raw_flights(origin_code, dest_code, date):
    """
    Fetches raw flight data from Google Flights via SerpApi.
    origin_code: e.g., 'DEL' (Indira Gandhi International)
    dest_code: e.g., 'BOM' (Chhatrapati Shivaji Maharaj International)
    date: YYYY-MM-DD
    """
    params = {
        "engine": "google_flights",
        "departure_id": origin_code,
        "arrival_id": dest_code,
        "outbound_date": date,
        "currency": "INR",
        "hl": "en",
        "type": "2",      # <--- IMPORTANT: 2 = One-way trip
        "api_key": API_KEY
    }

    print(f"Searching flights from {origin_code} to {dest_code} on {date}...")
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Check for error keys in the response
        if "error" in results:
            print(f"API Error: {results['error']}")
            return None

        # Check if flight data exists in the usual keys
        if 'best_flights' not in results and 'other_flights' not in results:
            print("No flights found. (Check your API key or Date)")
            return None
            
        return results
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# --- TEST BLOCK ---
if __name__ == "__main__":
    # Test with a future date
    test_data = fetch_raw_flights("DEL", "BOM", "2026-01-20")
    
    if test_data:
        # Save to a file so we can inspect the structure
        with open("raw_flight_data.json", "w") as f:
            json.dump(test_data, f, indent=4)
        print("Success! Data saved to 'raw_flight_data.json'.")