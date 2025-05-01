import json
from datetime import datetime, timedelta

def find_closest_trains(data, target_time_str):
    """
    Reads train data from a JSON file, extracts specific fields, and finds
    up to 3 trains closest to the target departure time.

    Finds:
    - The latest train departing up to 15 minutes BEFORE the target time.
    - The earliest two trains departing AT or AFTER the target time.

    Args:
        file_path (str): The full path to the JSON file (e.g., 'response.json').
        target_time_str (str): The target departure time in "HH:MM" format (e.g., "11:45").

    Returns:
        list: A list containing dictionaries of the extracted data for up to 3
              closest trains, or None if an error occurs.
              Returns an empty list if no trains are found in the JSON or match criteria.
    """
    all_trains_data = []
    target_dt = None # Initialize target datetime object
    # print(f"data: {data.json()}")
    try:
        json_data = json.loads(data) # Assuming 'data' is a JSON string

        travels = json_data.get('result', {}).get('travels', [])
        if not travels:
            print("Info: No 'travels' data found in the JSON file.")
            return [] # Return empty list if no travel data

        # --- 2. Prepare Target Time ---
        # Extract date part from the first train's departure time to use with target time
        first_departure_str = travels[0].get('trains', [{}])[0].get('departureTime')
        if not first_departure_str:
             raise ValueError("Could not find a valid departureTime in the first travel entry to establish date.")

        # Ensure the departure string has enough length for date extraction
        if len(first_departure_str) < 10:
            raise ValueError(f"Departure time string '{first_departure_str}' is too short.")
        
        date_part = first_departure_str[:10] # Extract "YYYY-MM-DD"
        target_dt = datetime.strptime(f"{date_part}T{target_time_str}:00", "%Y-%m-%dT%H:%M:%S")

        # --- 3. Extract Data for All Trains ---
        for travel in travels:
             # Each travel object contains a list of trains, usually one
            if not travel.get('trains'):
                continue # Skip if no trains in this travel

            train = travel['trains'][0] # Assuming the first train is the relevant one

            # Parse departure time for comparison
            dep_time_str = train.get('departureTime')
            if not dep_time_str:
                print(f"Warning: Skipping train {train.get('trainNumber')} due to missing departureTime.")
                continue
            
            try:
                dep_time = datetime.fromisoformat(dep_time_str)
            except ValueError:
                print(f"Warning: Skipping train {train.get('trainNumber')} due to invalid departureTime format: {dep_time_str}")
                continue


            # Extract required fields
            train_info = {
                "trainNumber": train.get("trainNumber"),
                "orignStation": train.get("orignStation"), # Key from JSON
                "destinationStation": train.get("destinationStation"), # Key from JSON
                "originPlatform": train.get("originPlatform"), # Key from JSON
                "destPlatform": train.get("destPlatform"), # Key from JSON
                "freeSeats": train.get("freeSeats"), # Key from JSON
                "arrivalTime": train.get("arrivalTime"), # Key from JSON
                "departureTime": dep_time_str, # Keep original string format for output
                "departureDateTime": dep_time, # Keep datetime object for sorting
                "handicap": train.get("handicap"), # Key from JSON
                "crowded": train.get("crowded"), # Key from JSON
                "trainPosition": None # Default to None
            }

            # Check and extract trainPosition if not null
            train_pos = train.get("trainPosition")
            if train_pos is not None:
                 # Extract nested fields only if trainPosition exists
                train_info["trainPosition"] = {
                    "currentLastStation": train_pos.get("currentLastStation"),
                    "nextStation": train_pos.get("nextStation"),
                    "calcDiffMinutes": train_pos.get("calcDiffMinutes") # Very important field
                }

            all_trains_data.append(train_info)
            break

        if not all_trains_data:
             print("Info: No valid train data extracted from the file.")
             return []

        # --- 4. Filter and Sort Trains by Time ---
        trains_before = []
        trains_after = []
        time_window_start = target_dt - timedelta(minutes=15)

        for train in all_trains_data:
            dep_time = train["departureDateTime"]
            if time_window_start <= dep_time < target_dt:
                trains_before.append(train)
            elif dep_time >= target_dt:
                trains_after.append(train)

        # Sort 'before' trains by departure time, descending (closest first)
        trains_before.sort(key=lambda x: x["departureDateTime"], reverse=True)

        # Sort 'after' trains by departure time, ascending (closest first)
        trains_after.sort(key=lambda x: x["departureDateTime"])

        # --- 5. Select the Closest 3 Trains ---
        closest_trains = []

        # Get the latest train within 15 mins before (if any)
        if trains_before:
            closest_trains.append(trains_before[0])

        # Get the next two trains at or after (if any)
        needed_after = 3 - len(closest_trains) # How many more trains we need
        closest_trains.extend(trains_after[:needed_after])

        # --- 6. Clean up data for final output (remove helper datetime field) ---
        for train in closest_trains:
            del train["departureDateTime"]

        return closest_trains


    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file '{data}'. Invalid JSON format.")
        print(f"Details: {e}")
        return None
    except (KeyError, IndexError) as e:
         print(f"Error: JSON structure is not as expected. Missing key or index: {e}")
         return None
    except ValueError as e:
        print(f"Error: Problem with time format or value: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing '{data}': {e}")
        return None

# --- How to Use ---

# # 1. Make sure 'response.json' is in the same directory as your script,
# #    or provide the full path.
# json_file = 'response.json'
# # 2. Choose your target time
# target_time = "11:45" # Example Target Time

# # 3. Call the function
# results = find_closest_trains(json_file, target_time)

# # 4. Print the results
# if results is not None:
#     if results:
#         print(f"\nFound {len(results)} closest trains to target time {target_time}:")
#         for i, train in enumerate(results):
#             print(f"\n--- Train {i+1} ---")
#             # Use json.dumps for pretty printing the dictionary
#             print(json.dumps(train, indent=4, default=str)) # default=str handles datetime if it wasn't removed
#     else:
#         print(f"\nNo trains found matching the time criteria around {target_time}.")
# else:
#     print("\nAn error occurred during processing.")

# Example 2: Different time
# target_time_2 = "18:00"
# results_2 = find_closest_trains(json_file, target_time_2)
# if results_2 is not None:
#      if results_2:
#         print(f"\nFound {len(results_2)} closest trains to target time {target_time_2}:")
#         for i, train in enumerate(results_2):
#             print(f"\n--- Train {i+1} ---")
#             print(json.dumps(train, indent=4, default=str))
#      else:
#         print(f"\nNo trains found matching the time criteria around {target_time_2}.")