from decouple import config
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import json
import datetime
import platform
import functools # Import functools for the decorator

import rail_req

BOT_API = config("BOT_API")
bot = telebot.TeleBot(BOT_API)

# --- !!! --- Configuration: Allowed User IDs --- !!! ---
# Replace these example IDs with the actual Telegram User IDs you want to allow.
# Get user IDs from bots like @userinfobot
allowed_ids_str = config('ALLOWED_TELEGRAM_IDS', default='')
ALLOWED_USER_IDS = {
    int(id_str.strip())
    for id_str in allowed_ids_str.split(',')
    if id_str.strip().isdigit() # Ensure it's a digit before converting
}

# --- !!! ------------------------------------------ !!! ---


# --- Decorator Function for Access Control ---
def restricted_access(func):
    """
    Decorator that restricts access to bot handlers to allowed user IDs.
    """
    @functools.wraps(func) # Preserves function metadata
    def wrapper(*args, **kwargs):
        # Extract the message or call object from the arguments
        # Handlers usually receive 'message' or 'call' as the first argument
        update_obj = args[0]

        user_id = None
        user_info_str = "Unknown user" # For logging

        if isinstance(update_obj, telebot.types.Message):
            user_id = update_obj.from_user.id
            username = update_obj.from_user.username
            user_info_str = f"User {user_id} (@{username})"
        elif isinstance(update_obj, telebot.types.CallbackQuery):
            user_id = update_obj.from_user.id
            username = update_obj.from_user.username
            user_info_str = f"User {user_id} (@{username})"
        else:
            # Could be another type of update, log it if necessary
            print(f"Warning: Unknown update type received in restricted_access: {type(update_obj)}")
            return # Don't process unknown types

        # Check if the user ID is allowed
        if user_id in ALLOWED_USER_IDS:
            # If allowed, execute the original handler function
            # print(f"Authorized access for {user_info_str} to {func.__name__}") # Optional: Log authorized access
            return func(*args, **kwargs)
        else:
            # If not allowed, log it and optionally notify the user (or just ignore)
            print(f"Unauthorized access attempt by {user_info_str} for {func.__name__}")
            # Optionally send a message (might alert unwanted users):
            # try:
            #     chat_id = update_obj.message.chat.id if hasattr(update_obj, 'message') else update_obj.chat.id
            #     bot.send_message(chat_id, "Sorry, you are not authorized to use this bot.")
            # except Exception as e:
            #     print(f"Error sending unauthorized message: {e}")
            return # Stop processing

    return wrapper
# --- End of Decorator ---


# --- Apply the decorator to your handlers ---

# Define button texts (keep these)
BUTTON_LOD = "From Lod"
BUTTON_KIRYAT_GAT = "From Kiryat Gat"

# Function to generate Reply Keyboard (keep this)
def gen_reply_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    button_lod = KeyboardButton(BUTTON_LOD)
    button_kiryat_gat = KeyboardButton(BUTTON_KIRYAT_GAT)
    markup.add(button_lod, button_kiryat_gat)
    return markup

# Formatting function (keep this)
def format_train_times_html(train_data, origin_code, dest_code):
    # ... (keep your existing formatting logic here) ...
    station_map = { 7000: "Kiryat Gat", 5000: "Lod", 8550: "Beer Sheva Center" }
    origin_name = station_map.get(origin_code, f"Station {origin_code}")
    dest_name = station_map.get(dest_code, f"Station {dest_code}")
    if not train_data: return f"😕 Sorry, no upcoming trains found from <b>{origin_name}</b> to <b>{dest_name}</b>."
    output_lines = [f"🚂 <b>Upcoming Trains: {origin_name} → {dest_name}</b>\n"]
    for train in train_data:
        try:
            dep_dt = datetime.datetime.fromisoformat(train['departureTime']); arr_dt = datetime.datetime.fromisoformat(train['arrivalTime'])
            dep_time_fmt = dep_dt.strftime('%H:%M'); arr_time_fmt = arr_dt.strftime('%H:%M')
            train_num = train.get('trainNumber', 'N/A'); dep_platform = train.get('originPlatform', '?')
            delay_str = ""
            position = train.get('trainPosition')
            if position and 'calcDiffMinutes' in position:
                delay = position['calcDiffMinutes']
                if delay > 0: delay_str = f"  <i>(Est. Delay: {delay} min)</i>"
            line = (f"<b>Train #: {train_num}</b>\n"
                    f"  departing at <b>{dep_time_fmt}</b> (Platform {dep_platform})\n"
                    f"  arriving at <b>{arr_time_fmt}</b>{delay_str}")
            output_lines.append(line)
        except Exception as e: print(f"Error formatting train entry: {e} - Data: {train}"); output_lines.append("❗️<i>Error processing one train entry.</i>")
    return "\n\n".join(output_lines)


@bot.message_handler(commands=['start', 'hello', 'help'])
@restricted_access # <--- Apply decorator
def send_welcome(message):
    bot.reply_to(message, "Hi, I am the Rail Lates Bot. How can I assist you?\nsend /times to get Keyboard")

@bot.message_handler(commands=['times'])
@restricted_access # <--- Apply decorator
def request_location_choice(message):
    bot.send_message(message.chat.id,
                     "Let me know from where you want to leave:",
                     reply_markup=gen_reply_keyboard())

@bot.message_handler(func=lambda message: message.text in [BUTTON_LOD, BUTTON_KIRYAT_GAT])
@restricted_access # <--- Apply decorator
def handle_location_choice(message):
    origin_code = None
    dest_code = None
    action_message = None

    if message.text == BUTTON_LOD:
        origin_code = 5000; dest_code = 7000
        action_message = f"Fetching train times from {BUTTON_LOD} to {BUTTON_KIRYAT_GAT}..."
    elif message.text == BUTTON_KIRYAT_GAT:
        origin_code = 7000; dest_code = 5000
        action_message = f"Fetching train times from {BUTTON_KIRYAT_GAT} to {BUTTON_LOD}..."

    if origin_code and dest_code and action_message:
        bot.send_message(message.chat.id, action_message)
        try:
            raw_response_string = rail_req.main(fromStation=origin_code, toStation=dest_code)
            times_data = None
            if raw_response_string:
                try: times_data = json.loads(raw_response_string)
                except json.JSONDecodeError as json_err:
                    print(f"JSON Decode Error: {json_err}"); print(f"Raw response was: {raw_response_string}")
                    bot.send_message(message.chat.id, "Sorry, received unusable data from the train API.")
                    return
            if times_data:
                formatted_output = format_train_times_html(times_data, origin_code, dest_code)
                bot.send_message(message.chat.id, formatted_output, parse_mode='HTML')
            else:
                 bot.send_message(message.chat.id, f"😕 No train data found for the selected route.")
        except Exception as e:
            bot.send_message(message.chat.id, f"Sorry, an error occurred while fetching train times: {e}")
            print(f"Error in handle_location_choice during API call or processing: {e}")

# You might want to restrict this too, or remove it if it's just for debugging
# @bot.message_handler(func=lambda message: True)
# @restricted_access # <--- Apply decorator if keeping it
# def echo_all(message):
# 	bot.reply_to(message, f"I didn't understand that. Try /times or /help.")


print("Bot starting with access restricted to User IDs:", ALLOWED_USER_IDS)
bot.infinity_polling()
print("Bot stopped.")