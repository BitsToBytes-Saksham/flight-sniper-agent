import os
import json
import urllib.request
import urllib.error


def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY environment variable is not set.")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode()
        except Exception:
            err = str(e)
        print("HTTP error when listing models:", err)
        return
    except Exception as e:
        print("Error when calling ListModels:", str(e))
        return

    models = data.get("models") or data.get("modelSummaries") or []
    if not models:
        print(json.dumps(data, indent=2))
        return

    print("Available models (summary):\n")
    for m in models:
        name = m.get("name") or m.get("model") or str(m)
        print(f"- {name}")
        # Print a compact summary of the model object
        try:
            # show supported methods if present
            supports = m.get("supported_generation_methods") or m.get("supportedMethods") or m.get("capabilities")
            if supports:
                print("  Supported:", supports)
        except Exception:
            pass


if __name__ == "__main__":
    list_models()
