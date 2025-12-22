import json

def clean_price(price_input):
    """
    Robust price cleaner. Handles both strings ('₹4,500') and integers (4500).
    """
    if price_input is None:
        return float('inf') # Return infinity so it goes to bottom of list
    
    # If it's already a number (int or float), just return it
    if isinstance(price_input, (int, float)):
        return int(price_input)
    
    # If it's a string, clean it
    if isinstance(price_input, str):
        clean_str = price_input.replace('₹', '').replace(',', '').replace('INR', '').strip()
        try:
            return int(clean_str)
        except ValueError:
            return float('inf')
            
    return float('inf')

def find_direct_flights(json_file_path):
    """
    Reads the raw JSON and returns a sorted list of DIRECT flights.
    """
    try:
        with open(json_file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: JSON file not found. Run flight_data.py first!")
        return []

    all_flights = []
    
    # Google Flights often groups results into 'best_flights' and 'other_flights'
    # We want to check BOTH lists.
    sources = []
    if 'best_flights' in data:
        sources.extend(data['best_flights'])
    if 'other_flights' in data:
        sources.extend(data['other_flights'])

    # If the expected keys are missing, try to be flexible and find any list
    # in the top-level response that looks like flight entries (has 'flights' key).
    if not sources:
        for v in data.values():
            if isinstance(v, list) and v:
                first = v[0]
                if isinstance(first, dict) and 'flights' in first:
                    sources.extend(v)
                    break

    print(f"Analyzing {len(sources)} total flight options...")

    search_url = data.get('search_metadata', {}).get('google_flights_url')

    for flight in sources:
        # --- THE SNIPER LOGIC ---
        
        # 1. Filter for DIRECT flights only
        # In SerpApi, if 'layovers' key exists, it usually means there are stops.
        # Direct flights often don't have the 'layovers' key or it is empty.
        has_layovers = flight.get('layovers')
        if has_layovers:
            continue # Skip this flight, it has stops

        # 2. Extract Data safely
        try:
            # 'flights' is a list of segments. Direct flights have 1 segment.
            segment = flight['flights'][0] 
            
            # Prefer per-flight URL if present; else try booking_token or search-level URL
            booking_token = flight.get('booking_token')
            per_flight_url = flight.get('google_flights_url')

            if per_flight_url:
                link_value = per_flight_url
            elif booking_token and search_url:
                # append token to the search URL as a best-effort deep link
                link_value = f"{search_url}&booking_token={booking_token}"
            elif search_url:
                link_value = search_url
            else:
                link_value = 'No link'

            flight_info = {
                "airline": segment.get('airline', 'Unknown'),
                "flight_number": segment.get('flight_number', 'N/A'),
                "departure": segment.get('departure_airport', {}).get('time', 'Unknown'),
                "arrival": segment.get('arrival_airport', {}).get('time', 'Unknown'),
                "duration": flight.get('total_duration', 'Unknown'),
                "price_raw": flight.get('price'),
                "price_value": clean_price(flight.get('price')), # Used for sorting
                "link": link_value # Direct booking link or search URL
            }
            all_flights.append(flight_info)
            
        except (KeyError, IndexError) as e:
            print(f"Skipping a malformed flight entry: {e}")
            continue

    # 3. Sort by Price (Cheapest first)
    sorted_flights = sorted(all_flights, key=lambda x: x['price_value'])
    
    return sorted_flights

# --- TEST BLOCK ---
if __name__ == "__main__":
    # We load the data we saved in Phase 1
    direct_flights = find_direct_flights("raw_flight_data.json")
    
    print(f"\nFound {len(direct_flights)} DIRECT flights.")
    print("-" * 50)
    
    # Print the Top 5 Cheapest
    for i, f in enumerate(direct_flights[:5]):
        print(f"{i+1}. {f['airline']} ({f['flight_number']})")
        print(f"   Time: {f['departure']} -> {f['arrival']} ({f['duration']} mins)")
        print(f"   Price: {f['price_raw']}")
        print("-" * 50)