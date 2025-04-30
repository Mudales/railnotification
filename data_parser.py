import json
import os

# def json_loader(file_path):
#     with open(file_path, 'r') as file:
#         data = json.load(file)
#     return data

def response_parse(data):
    extracted_trains = []

    # data = json.load(data)
    travels = data.get('result', {}).get('travels', [])
    for travel in travels:
        train = travel['trains'][0]
        
        print(train.get("trainPosition"))
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
        extracted_trains.append(train_info)

    return extracted_trains

        