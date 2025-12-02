import requests
import json
import data
import datetime
import platform
import types 

# Define your API details
API_KEY = "5e64d66cf03f4547bcac5de2de06b566"
API_BASE = 'https://rail-api.rail.co.il/rjpa/api/v1'

# Define the endpoint
endpoint = '/timetable/searchTrain'
url = f"{API_BASE}{endpoint}"


def get_formatted_datetime():
    """
    Gets the current date and time and returns an object
    with formatted 'date' and 'time' attributes.

    Access the formatted parts using .date or .time on the returned object.

    Returns:
        types.SimpleNamespace: An object with attributes:
                                 - date (str): Formatted as "YYYY-MM-DD" (e.g., "2025-12-02")
                                 - time (str): Formatted as "HH:MM" (e.g., "11:23")
    """
    now = datetime.datetime.now()

    # --- Format Time ---
    formatted_time = now.strftime("%H:%M")

    # --- Format Date ---
    # API expects YYYY-MM-DD format (with zero-padded day)
    formatted_date = now.strftime("%Y-%m-%d")

    return types.SimpleNamespace(date=formatted_date, time=formatted_time)


def main(fromStation: int = 5000, toStation: int = 7000):
    # Headers that mimic a real browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/json',
        'ocp-apim-subscription-key': API_KEY,
        'Origin': 'https://www.rail.co.il',
        'Referer': 'https://www.rail.co.il/',
        'sec-ch-ua': '"Chromium";v="142", "Not_A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'DNT': '1'
    }

    # --- Get current time ONCE ---
    current_dt = get_formatted_datetime()
    
    # Payload as dictionary (matches the API structure from your browser example)
    payload = {
        "methodName": "searchTrainLuzForDateTime",
        "fromStation": fromStation,
        "toStation": toStation,
        "date": current_dt.date,
        "hour": current_dt.time,
        "systemType": "2",
        "scheduleType": "ByDeparture",
        "languageId": "English",
        "requestLocation": "{\"latitude\":\"0.0\",\"longitude\":\"0.0\"}",
        "requestIP": "0.0.0.0",
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "screenResolution": "{\"height\":800,\"width\":1280}",
        "searchFromFavorites": False
    }

    # Make the POST request with JSON payload
    try:
        response = requests.post(
            url,
            json=payload,  # Use json= instead of params=
            headers=headers,
            timeout=30
        )
        
        print(f"Response Status: {response.status_code}")
        
        # Process the response
        if response.status_code == 200:
            try:
                response_parsed_data = data.find_closest_trains(
                    data=response.json(), 
                    target_time_str=current_dt.time
                )
                print(json.dumps(response_parsed_data, indent=4))
                return json.dumps(response_parsed_data, indent=4)
            except json.JSONDecodeError:
                print("\nResponse was not in JSON format.")
                print(f"Raw response: {response.text[:500]}")  # Print first 500 chars
                return "\nResponse was not in JSON format."
            except Exception as e:
                print(f"An error occurred while processing the response: {e}")
                return str(e)
        else:
            print(f"\nFailed to get a successful response. Status: {response.status_code}")
            print(f"Response text: {response.text[:500]}")
            return f"\nFailed to get a response. Status: {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return f"Request failed: {e}"


if __name__ == "__main__":
    # Call the main function to execute the request and print the result
    result = main()
    print(result)