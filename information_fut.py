import requests
import json
from datetime import datetime

# Configuration
API_URL = "https://fut.phys.au.dk/observe/api/telescope_status.php"
API_TOKEN = "observe-api-Aipaiye2"

try:
    # Set up headers with token and make a request to the API
    headers = {
        'X-API-Token': API_TOKEN,
        'User-Agent': 'TelescopeTest/1.0'
    }
    response = requests.get(API_URL, headers=headers, timeout=10)

    if response.status_code == 200:
        data = response.json()

        # raw JSON (for debugging)
        print("RAW JSON:")
        print(json.dumps(data, indent=2))
        print("\n" + "="*50)

        # Pretty print
        print("TELESCOPE INFORMATION")
        print("="*50)
        for key, value in data.items():
            if key == 'timestamp':
                readable_time = datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
                print(f"{key:20}: {readable_time}")
            elif isinstance(value, bool):
                print(f"{key:20}: {'Yes' if value else 'No'}")
            elif value is None:
                print(f"{key:20}: Not set")
            else:
                print(f"{key:20}: {value}")

    else:
        print(f"Error: HTTP {response.status_code}")
        print(f"Response: {response.text}")

except requests.exceptions.RequestException as e:
    print(f"Connection error: {e}")
except json.JSONDecodeError as e:
    print(f"JSON parsing error: {e}")