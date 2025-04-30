import requests
import json # Still useful if the response is JSON

def simple_get_request(url: str, params: dict = None, headers: dict = None):
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers
        )
        print(f"Request finished with Status Code: {response.status_code}")

        return response

    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

# --- Example Usage based on your previous context ---

# Define your API details
API_KEY = "4b0d355121fe4e0bb3d86e902efe9f20" # Use your actual API key
API_BASE = 'https://israelrail.azurefd.net/rjpa-prod/api/v1'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'

# Define the endpoint
endpoint = '/timetable/searchTrainLuzForDateTime'
url = f"{API_BASE}{endpoint}"

# Define the query parameters as a dictionary
params = {
    'fromStation': 5000,
    'toStation': 7000,
    'date': '2025-04-23',
    'hour': '11:15',
    'scheduleType': 1,
    'systemType': 2,
    'languageId': 'English'
}

# Define the headers
headers = {
    'User-Agent': USER_AGENT,
    "ocp-apim-subscription-key": API_KEY # Make sure this key is valid for the API
}

# Make the GET request using the simplified function
response = simple_get_request(
    url,
    params=params,
    headers=headers
)

# Process the response
if response:
    # You can access response details like:
    # response.status_code
    # response.headers
    # response.text (raw body as string)
    # response.json() (body as Python dict/list, if it's valid JSON)

    try:
        # Attempt to parse the response body as JSON
        data = response.json()['result']["travels"]

        # print("\nResponse Data (first 500 characters):")
        print(json.dumps(data, indent=4)[:700] + "...") # Print a snippet
        with open('data.json', 'w') as newdata:
            json.dump(response.json(), newdata, indent=4)
                
        
        # print(json.dumps(data, indent=2)) # Uncomment to print full data
    except json.JSONDecodeError:
        print("\nResponse was not in JSON format.")
        print("Response body:")
        print(response.text) # Print the raw text if not JSON
    except Exception as e:
         print(f"An error occurred while processing the response: {e}")

else:
    print("\nFailed to get a response.")