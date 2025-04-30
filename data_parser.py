import json

def json_load(file_path):
    """
    Load JSON data from a file and return it as a dictionary.
    
    :param file_path: Path to the JSON file.
    :return: Parsed JSON data as a dictionary.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return None
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{file_path}'")
        return None
    
    


def response_parse(data):
    extracted_trains = []

    # data = json.load(data)
    travels = data.get('result', {}).get('travels', [])
    for travel in travels:
        train = travel['trains'][0]

        train_info = {
            "trainNumber": train.get("trainNumber"),
            "orignStation": train.get("orignStation"),
            "destinationStation": train.get("destinationStation"),
            "originPlatform": train.get("originPlatform"),
            "destPlatform": train.get("destPlatform"),
            "freeSeats": train.get("freeSeats"),
            "arrivalTime": train.get("arrivalTime"),
            "departureTime": train.get("departureTime"), # Keep original string
            "handicap": train.get("handicap"),
            "crowded": train.get("crowded"),
            "trainPosition": None # Initialize as None
        }
        train_pos_data = train.get("trainPosition")
        if train_pos_data is not None:
            train_info["trainPosition"] = {
                "currentLastStation": train_pos_data.get("currentLastStation"),
                "nextStation": train_pos_data.get("nextStation"),
                "calcDiffMinutes": train_pos_data.get("calcDiffMinutes")
            }
        else:
            train_info["trainPosition"] = "######"
        # Append the train info to the list
        extracted_trains.append(train_info)

    return extracted_trains

