import json

# with open(file="response.json", mode='r') as data:
#     fullresult = json.load(data)
#     travels = fullresult["result"]["travels"]
#     print(travels['trainNumber'])
#     # for train in travels:
#     #     print(train[0])
#         # print(train["departureTime"])
#         # print(train["arrivalTime"])
#         # print(train["originPlatform"])
#         # print(train["destPlatform"])
#     # print(travels[0])



def extract_train_info(json_data):
  """
  Extracts specific train information from the given JSON data.

  Args:
    json_data: A dictionary representing the parsed JSON data.

  Returns:
    A list of dictionaries, where each dictionary contains the
    'orignStation', 'destinationStation', 'originPlatform',
    'destPlatform', and 'arrivalTime' for each train.
  """
  extracted_data = []
  if json_data and json_data.get("result") and json_data["result"].get("travels"):
    for travel in json_data["result"]["travels"]:
      if travel.get("trains"):
        for train in travel["trains"]:
          train_info = {
              "orignStation": train.get("orignStation"),
              "destinationStation": train.get("destinationStation"),
              "originPlatform": train.get("originPlatform"),
              "destPlatform": train.get("destPlatform"),
              "arrivalTime": train.get("arrivalTime")
          }
          extracted_data.append(train_info)
  return extracted_data


with open(file="response.json", mode='r') as data:
    data = json.load(data)
    train_details = extract_train_info(data)
    print(train_details)
    