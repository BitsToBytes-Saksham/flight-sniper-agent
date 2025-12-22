import os
import datetime
import re
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

# Import our working functions from previous phases
from flight_data import fetch_raw_flights
from flight_filter import find_direct_flights

# Load keys
load_dotenv()


def extract_text(msg):
    """Normalize different model response shapes into a printable string."""
    try:
        content = getattr(msg, "content", msg)
        # If LangChain wrapped content is a list of message dicts
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    # common shapes: {'type':'text','text':...}
                    text = item.get("text") or item.get("content") or item.get("message")
                    if text:
                        parts.append(str(text))
                    else:
                        parts.append(str(item))
                else:
                    parts.append(str(item))
            return "\n".join(parts).strip()

        if isinstance(content, dict):
            if "text" in content:
                return str(content["text"])
            # fallback to stringifying dict
            return str(content)

        return str(content)
    except Exception:
        return str(msg)

# --- 1. DEFINE THE TOOL ---
# This decorator tells the AI: "Here is a function you can use."
@tool
def search_flights_tool(origin: str, destination: str, date: str):
    """
    Searches for direct flights between two airport codes for a specific date.
    
    Args:
        origin: The 3-letter IATA code for the origin city (e.g., 'DEL').
        destination: The 3-letter IATA code for the destination city (e.g., 'BOM').
        date: The date of travel in 'YYYY-MM-DD' format.
    """
    print(f"\n✈️  AGENT ACTION: Searching flights from {origin} to {destination} on {date}...")
    
    # 1. Fetch Data (Phase 1 Logic)
    raw_data = fetch_raw_flights(origin, destination, date)
    
    if not raw_data:
        return "I found no flights or there was an API error."

    # 2. Save temporarily (so our filter script can read it)
    import json
    with open("temp_search.json", "w") as f:
        json.dump(raw_data, f)
        
    # 3. Filter Data (Phase 2 Logic)
    # We reuse the logic we built in Phase 2
    # Note: We need to slightly modify Phase 2 logic to accept a file path or dict, 
    # but for now, we read the temp file we just wrote.
    from flight_filter import find_direct_flights
    cleaned_flights = find_direct_flights("temp_search.json")
    
    if not cleaned_flights:
        return "I found flights, but none were direct."

    # 4. Format the output for the AI to read
    # Provide varied-airline recommendations: pick the cheapest flight per airline,
    # then return up to 3 distinct-airline options. If fewer than 3 distinct
    # airlines exist, fill with the next cheapest overall. Also include close
    # alternatives within a small price tolerance (5%).
    cheapest_price = cleaned_flights[0]['price_value']

    # cheapest flight per airline (cleaned_flights is sorted by price_value already)
    unique_airlines = {}
    for f in cleaned_flights:
        airline_name = f['airline']
        if airline_name not in unique_airlines:
            unique_airlines[airline_name] = f

    diverse_flights = sorted(list(unique_airlines.values()), key=lambda x: x['price_value'])

    # Pick up to 3 varied airlines
    recommended = diverse_flights[:3]

    # If fewer than 3 distinct airlines, append the next cheapest overall
    if len(recommended) < 3:
        seen = {f['flight_number'] for f in recommended}
        for f in cleaned_flights:
            if f['flight_number'] in seen:
                continue
            recommended.append(f)
            seen.add(f['flight_number'])
            if len(recommended) >= 3:
                break

    summary = f"Found {len(cleaned_flights)} direct flights. Recommended (varied airlines, up to 3):\n"
    for f in recommended:
        summary += f"- {f['airline']} ({f['flight_number']}): {f['price_raw']}, Departs: {f['departure']}\n"

    # Also show near-cheapest alternatives (within 5% of the absolute cheapest)
    tolerance_pct = 0.05
    threshold = cheapest_price * (1 + tolerance_pct)
    alt_candidates = [f for f in cleaned_flights if f['price_value'] <= threshold and f['flight_number'] not in {r['flight_number'] for r in recommended}]
    if alt_candidates:
        summary += "\nAlso near-cheapest alternatives within 5%:\n"
        for f in alt_candidates[:5]:
            summary += f"- {f['airline']} ({f['flight_number']}): {f['price_raw']}, Departs: {f['departure']}\n"

    return summary

# --- 2. SETUP THE BRAIN ---
# Support a list of fallback models (comma-separated in env var GOOGLE_FALLBACK_MODELS)
FALLBACK_MODELS = [m.strip() for m in os.getenv("GOOGLE_FALLBACK_MODELS", "models/gemini-2.5-flash,models/gemini-flash-lite-latest").split(",") if m.strip()]


def create_llm(model_name: str):
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY")
    )


# Initialize primary LLM (from env GOOGLE_MODEL) and bind tools
current_model = os.getenv("GOOGLE_MODEL", "models/gemini-2.5-pro")
llm = create_llm(current_model)
llm_with_tools = llm.bind_tools([search_flights_tool])

# --- 3. THE CHAT LOOP ---
def chat_with_agent():
    global llm, llm_with_tools, current_model
    print("---------------------------------------------------------")
    print("🤖 FLIGHT AGENT: Where would you like to go? (Type 'quit' to exit)")
    print("   (Example: 'Find me a direct flight from Delhi to Mumbai for Jan 20th')")
    print("---------------------------------------------------------")
    
    # We need to tell the Agent what today is, or it gets confused about dates.
    today = datetime.date.today()
    system_prompt = f"You are a helpful flight assistant. Today is {today}. When searching, convert city names to Airport Codes (e.g. Delhi -> DEL). Always use YYYY-MM-DD format for dates."

    messages = [SystemMessage(content=system_prompt)]

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["quit", "exit"]:
            break
        
        # Add user message to history
        messages.append(HumanMessage(content=user_input))
        
        # 1. AI Thinks
        try:
            ai_msg = llm_with_tools.invoke(messages)
        except Exception as e:
            s = str(e)
            print("\n⚠️  Error calling the model:", s)
            if "RESOURCE_EXHAUSTED" in s or "quota" in s:
                # Try fallbacks first (don't wait immediately)
                tried_fallback = False
                for fb in FALLBACK_MODELS:
                    if fb == current_model:
                        continue
                    print(f"Attempting fallback model: {fb}")
                    try:
                        # recreate llm and binding with fallback
                        llm = create_llm(fb)
                        llm_with_tools = llm.bind_tools([search_flights_tool])
                        # test invoke (dry run) - call with same messages
                        ai_msg = llm_with_tools.invoke(messages)
                        # succeeded: update current_model and proceed
                        current_model = fb
                        print(f"Fallback to {fb} succeeded.")
                        tried_fallback = True
                        break
                    except Exception as efb:
                        print(f"Fallback {fb} failed: {efb}")
                        continue

                if tried_fallback:
                    # proceed with the ai_msg returned by the successful fallback
                    pass
                else:
                    # No fallback succeeded; parse retry delay and retry once
                    m = re.search(r"retry in ([0-9.]+)s", s)
                    if not m:
                        m = re.search(r"retryDelay.*?(\d+)s", s)
                    if m:
                        wait_s = float(m.group(1)) if m else 30.0
                        wait_s = min(max(wait_s, 1.0), 300.0)
                        print(f"Quota exhausted — waiting {wait_s:.0f}s then retrying once...")
                        time.sleep(wait_s + 1)
                        try:
                            ai_msg = llm_with_tools.invoke(messages)
                        except Exception as e2:
                            print("Retry failed:", str(e2))
                            print("Check your project's billing/quotas in Google Cloud Console or use a different model/API key.")
                            continue
                    else:
                        print("Quota exhausted. Check billing & quota at https://ai.google.dev/gemini-api/docs/rate-limits")
                        print("You can also run `python list_models.py` and pick a different model or use a different project/API key.")
                        continue
            else:
                print("Hint: The configured model may not be available for your API version.")
                print("Try a Gemini model from ListModels, for example: models/gemini-2.5-pro or models/gemini-pro-latest.")
                print("Run `python list_models.py` to see the full list of available models for your API key.")
                continue
        messages.append(ai_msg)

        # 2. Does the AI want to use a tool?
        if ai_msg.tool_calls:
            for tool_call in ai_msg.tool_calls:
                # Run the tool
                tool_output = search_flights_tool.invoke(tool_call)
                
                # Add the tool result back to the conversation
                from langchain_core.messages import ToolMessage
                messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call["id"]))
            
            # 3. AI responds based on the tool output
            try:
                final_response = llm_with_tools.invoke(messages)
                print("🤖 Agent:", extract_text(final_response))
                messages.append(final_response)
            except Exception as e:
                s = str(e)
                print("\n⚠️  Error generating final response:", s)
                if "RESOURCE_EXHAUSTED" in s or "quota" in s:
                    m = re.search(r"retry in ([0-9.]+)s", s)
                    if not m:
                        m = re.search(r"retryDelay.*?(\d+)s", s)
                    if m:
                        wait_s = float(m.group(1)) if m else 30.0
                        wait_s = min(max(wait_s, 1.0), 300.0)
                        print(f"Quota exhausted — waiting {wait_s:.0f}s then retrying once...")
                        time.sleep(wait_s + 1)
                        try:
                            final_response = llm_with_tools.invoke(messages)
                            print(f"🤖 Agent: {final_response.content}")
                            messages.append(final_response)
                        except Exception as e2:
                            print("Retry failed:", str(e2))
                            print("Check your project's billing/quotas in Google Cloud Console or use a different model/API key.")
                            continue
                    else:
                        print("Quota exhausted. Check billing & quota at https://ai.google.dev/gemini-api/docs/rate-limits")
                        continue
                else:
                    print("Hint: Check your model setting in the GOOGLE_MODEL env var or your API key.")
                    continue
            else:
            # If no tool needed (just chit-chat)
                print("🤖 Agent:", extract_text(ai_msg))
        
        # ... inside search_flights_tool ...

if __name__ == "__main__":
    chat_with_agent()