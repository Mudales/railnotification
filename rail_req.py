from textwrap import indent
import requests
import json # Still useful if the response is JSON
# from data_parser import response_parse # Assuming this is the correct import path   
import data
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
    'date': '2025-05-1',
    'hour': '11:00',
    'scheduleType': 1,
    'systemType': 2,
    'languageId': 'English'
}



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


# Define the headers
def main():
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
    if response and response.status_code == 200:
        # You can access response details like:
        # response.status_code, response.headers, response.text, etc.
        print(response.status_code)  
        json_format = response.json()  

        try:
            response_parsed_data = data.find_closest_trains(data=json_format, target_time_str="10:52")
            print(json.dumps(response_parsed_data , indent=4))# Assuming this function is defined in data_parser.py
            return response_parsed_data
            # return json.dumps(response_parsed_data, indent=4) # Pretty print the parsed data
        except json.JSONDecodeError:
            print("\nResponse was not in JSON format.")
            print(response.text) 
            return response.text# Print the raw text if not JSON
        except Exception as e:
            print(f"An error occurred while processing the response: {e}")
            return e

    else:
        # print("\nFailed to get a response.")
        return "\nFailed to get a response."
    
if __name__ == "__main__":
    # Call the main function to execute the request and print the result
    result = main()
   
    # print(json.dumps(result, indent=4)) # Pretty print the result if it's a dictionary or list