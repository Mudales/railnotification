import requests
import json # Still useful if the response is JSON
import data
import datetime
import platform
import types 



# Define your API details
API_KEY = "4b0d355121fe4e0bb3d86e902efe9f20" # Use your actual API key
API_BASE = 'https://israelrail.azurefd.net/rjpa-prod/api/v1'
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'

# Define the endpoint
endpoint = '/timetable/searchTrainLuzForDateTime'
url = f"{API_BASE}{endpoint}"


def get_formatted_datetime():
  """
  Gets the current date and time and returns an object
  with formatted 'date' and 'time' attributes.

  Access the formatted parts using .date or .time on the returned object.

  Returns:
      types.SimpleNamespace: An object with attributes:
                               - date (str): Formatted as "YYYY-MM-D" (e.g., "2025-05-1")
                               - time (str): Formatted as "HH:MM" (e.g., "11:23")
  """
  now = datetime.datetime.now()

  # --- Format Time ---
  # %H: Hour (24-hour clock, zero-padded)
  # %M: Minute (zero-padded)
  formatted_time = now.strftime("%H:%M")

  # --- Format Date ---
  # %Y: Year with century
  # %m: Month as a zero-padded decimal number
  # %-d: Day of the month as a decimal number (no padding on Linux/macOS)
  # %#d: Day of the month as a decimal number (no padding on Windows)

  # Choose the correct non-padded day format code based on OS
  if platform.system() == "Windows":
      day_format_code = "%#d"
  else: # Linux, macOS, other POSIX
      day_format_code = "%-d"

  # Construct the full format string for the date
  date_format_string = f"%Y-%m-{day_format_code}"
  formatted_date = now.strftime(date_format_string)

  # --- Create and return the object ---
  # SimpleNamespace allows creating an object with arbitrary attributes
  return types.SimpleNamespace(date=formatted_date, time=formatted_time)



# def simple_get_request(url: str, params: dict = None, headers: dict = None):
#     try:
#         response = requests.get(
#             url,
#             params=params,
#             headers=headers
#         )
#         print(f"Request finished with Status Code: {response.status_code}")

#         return response

#     except requests.exceptions.RequestException as e:
#         print(f"Error making request: {e}")
#         return None
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
#         return None

# # --- Example Usage based on your previous context ---


# Define the headers
def main(fromStation: int = 5000, toStation: int = 7000):
    headers = {
    'User-Agent': USER_AGENT,
    "ocp-apim-subscription-key": API_KEY # Make sure this key is valid for the API
    }
    
    params = {
    'fromStation': fromStation,
    'toStation': toStation,
    'date': get_formatted_datetime().date,
    'hour': get_formatted_datetime().time,
    'scheduleType': 1,
    'systemType': 2,
    'languageId': 'English'
    }


    # Make the GET request using the simplified function
    response = requests.get(
            url,
            params=params,
            headers=headers
        )

    # Process the response
    if response and response.status_code == 200:
        # You can access response details like:
        # response.status_code, response.headers, response.text, etc.
        print(response.status_code)  

        try:
            response_parsed_data = data.find_closest_trains(data=response.json(), target_time_str=get_formatted_datetime().time) # Assuming this function is defined in data.py
            # print(json.dumps(response_parsed_data, indent=4)) # Pretty print the result if it's a dictionary or list
            return json.dumps(response_parsed_data, indent=4) # Return the parsed data as a JSON string
        except json.JSONDecodeError:
            print("\nResponse was not in JSON format.")
            # print(response.text) 
            return "\nResponse was not in JSON format." # Print the raw text if not JSON
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