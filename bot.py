from decouple import config
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import json
import datetime
import functools
import html

import rail_req
import curlbus_req

BOT_API = config("BOT_API")
bot = telebot.TeleBot(BOT_API)

# --- Access Control ---
allowed_ids_str = config('ALLOWED_TELEGRAM_IDS', default='')
ALLOWED_USER_IDS = {
    int(id_str.strip())
    for id_str in allowed_ids_str.split(',')
    if id_str.strip().isdigit()
}

STATIONS = {
    5000: {'Heb': 'לוד', 'Eng': 'Lod'},
    7000: {'Heb': 'קריית גת', 'Eng': 'Kiryat Gat'},
    4600: {'Heb': 'תל אביב - השלום', 'Eng': 'HaShalom'},
}

# Button text → (origin, dest)
BUTTON_LOD_TO_GAT = "Lod → Kiryat Gat"
BUTTON_GAT_TO_LOD = "Kiryat Gat → Lod"
BUTTON_LOD_TO_HASHALOM = "Lod → HaShalom"
BUTTON_HASHALOM_TO_LOD = "HaShalom → Lod"

BUTTON_ROUTES = {
    BUTTON_LOD_TO_GAT: (5000, 7000),
    BUTTON_GAT_TO_LOD: (7000, 5000),
    BUTTON_LOD_TO_HASHALOM: (5000, 4600),
    BUTTON_HASHALOM_TO_LOD: (4600, 5000),
}

# Bus buttons come from curlbus_req.BUS_ROUTES (lines 460 / 464, both directions).
BUS_BUTTONS = list(curlbus_req.BUS_ROUTES)

# Keep the stop reply readable instead of dumping a whole timetable.
MAX_ARRIVALS = 12


def restricted_access(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        update_obj = args[0]
        user_id = None

        if isinstance(update_obj, telebot.types.Message):
            user_id = update_obj.from_user.id
        elif isinstance(update_obj, telebot.types.CallbackQuery):
            user_id = update_obj.from_user.id

        if user_id and user_id in ALLOWED_USER_IDS:
            return func(*args, **kwargs)

        if user_id:
            print(f"Unauthorized: {user_id} tried {func.__name__}")
    return wrapper


def station_name(code):
    s = STATIONS.get(code)
    if not s:
        return f"Station {code}"
    return s['Eng']


def gen_reply_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    markup.row(
        KeyboardButton(BUTTON_LOD_TO_GAT),
        KeyboardButton(BUTTON_GAT_TO_LOD),
    )
    markup.row(
        KeyboardButton(BUTTON_LOD_TO_HASHALOM),
        KeyboardButton(BUTTON_HASHALOM_TO_LOD),
    )
    for i in range(0, len(BUS_BUTTONS), 2):
        markup.row(*(KeyboardButton(label) for label in BUS_BUTTONS[i:i + 2]))
    return markup


def format_train_times_html(train_data, origin_code, dest_code):
    origin_name = station_name(origin_code)
    dest_name = station_name(dest_code)

    if not train_data:
        return f"😕 No upcoming trains from <b>{origin_name}</b> to <b>{dest_name}</b>."

    lines = [f"🚂 <b>{origin_name} → {dest_name}</b>\n{'━' * 24}"]

    for i, train in enumerate(train_data):
        try:
            dep_dt = datetime.datetime.fromisoformat(train['departureTime'])
            arr_dt = datetime.datetime.fromisoformat(train['arrivalTime'])
            dep_time = dep_dt.strftime('%H:%M')
            arr_time = arr_dt.strftime('%H:%M')
            train_num = train.get('trainNumber', 'N/A')
            dep_platform = train.get('originPlatform', '?')

            # Build display with delay
            delay_minutes = 0
            position = train.get('trainPosition')
            if position and 'calcDiffMinutes' in position:
                delay_minutes = position['calcDiffMinutes'] or 0

            if delay_minutes > 0:
                status = "🔴 LATE"
                delayed_dep = dep_dt + datetime.timedelta(minutes=delay_minutes)
                delayed_dep_time = delayed_dep.strftime('%H:%M')
                dep_display = f"<s>{dep_time}</s>  <b><u>{delayed_dep_time}</u></b>"
                delayed_arr = arr_dt + datetime.timedelta(minutes=delay_minutes)
                delayed_arr_time = delayed_arr.strftime('%H:%M')
                arr_display = f"<s>{arr_time}</s>  <b><u>{delayed_arr_time}</u></b>"
                delay_badge = f"  ⚠️ <b><i>+{delay_minutes} min delay</i></b>"
            else:
                status = "🟢 On Time"
                dep_display = f"<b>{dep_time}</b>"
                arr_display = f"<b>{arr_time}</b>"
                delay_badge = ""

            line = (
                f"{status}  |  <b>Train #{train_num}</b>{delay_badge}\n"
                f"  🕐 Departs:  {dep_display}\n"
                f"  🏁 Arrives:    {arr_display}\n"
                f"  🚏 Platform:  <b>{dep_platform}</b>"
            )

            if i < len(train_data) - 1:
                line += f"\n{'─' * 24}"

            lines.append(line)
        except Exception as e:
            print(f"Error formatting train: {e} - {train}")
            lines.append("❗ <i>Error processing one train entry.</i>")

    return "\n\n".join(lines)


# Longest destination name we print before cutting it short.
MAX_DEST_CHARS = 32


def esc(text):
    """Escape only what Telegram's HTML mode cares about: & < >."""
    return html.escape(str(text), quote=False)


def format_bus_arrivals_html(arrivals, title, subtitle=None, show_line=True):
    """Render curlbus arrivals as one short line per bus.

    Destinations are Hebrew, so they go last on each line - mixing RTL text
    into the middle of an LTR line makes Telegram reorder it oddly.
    """
    header = [f"🚍 <b>{esc(title)}</b>"]
    if subtitle:
        header.append(f"<i>{esc(subtitle)}</i>")
    header.append('━' * 20)

    if not arrivals:
        header.append(
            "😕 Nothing due in the next "
            f"{curlbus_req.DEFAULT_WINDOW_MINUTES} minutes."
        )
        return "\n".join(header)

    for arrival in arrivals:
        when = arrival['eta'].strftime('%H:%M')
        minutes = arrival['minutes']
        due = "<b>now</b>" if minutes <= 1 else f"<b>{minutes} min</b>"

        row = "🚌 "
        if show_line:
            row += f"<b>{esc(arrival['line'])}</b> · "
        row += f"{due} <i>({when})</i>"

        destination = arrival['destination']
        if destination:
            if len(destination) > MAX_DEST_CHARS:
                destination = destination[:MAX_DEST_CHARS - 1].rstrip() + '…'
            row += f" ← {esc(destination)}"
        header.append(row)

    return "\n".join(header)


@bot.message_handler(commands=['start', 'hello', 'help'])
@restricted_access
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "👋 Welcome to <b>Rail Notification Bot</b>!\n\n"
        "Use /times to get the route keyboard.\n"
        "Send a <b>bus stop number</b> (e.g. <code>35096</code>) to see what is "
        f"arriving there in the next {curlbus_req.DEFAULT_WINDOW_MINUTES} minutes.",
        parse_mode='HTML'
    )


@bot.message_handler(commands=['times','time'])
@restricted_access
def request_route(message):
    bot.send_message(
        message.chat.id,
        "Select a route:",
        reply_markup=gen_reply_keyboard()
    )


@bot.message_handler(func=lambda message: message.text in BUTTON_ROUTES)
@restricted_access
def handle_route_choice(message):
    origin_code, dest_code = BUTTON_ROUTES[message.text]

    bot.send_message(message.chat.id, f"⏳ Fetching trains...")

    try:
        times_data = rail_req.main(fromStation=origin_code, toStation=dest_code)

        if times_data:
            text = format_train_times_html(times_data, origin_code, dest_code)
        else:
            text = f"😕 No train data found."

        bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=gen_reply_keyboard())

    except Exception as e:
        print(f"Error fetching trains: {e}")
        bot.send_message(message.chat.id, f"❌ Error: {e}")


@bot.message_handler(func=lambda message: message.text in curlbus_req.BUS_ROUTES)
@restricted_access
def handle_bus_choice(message):
    route = curlbus_req.BUS_ROUTES[message.text]

    bot.send_message(message.chat.id, "⏳ Fetching buses...")

    try:
        arrivals = curlbus_req.get_arrivals(
            route['stop'],
            within_minutes=curlbus_req.DEFAULT_WINDOW_MINUTES,
            lines={route['line']},
        )
    except curlbus_req.CurlbusError as e:
        bot.send_message(message.chat.id, f"❌ {e}", reply_markup=gen_reply_keyboard())
        return
    except Exception as e:
        print(f"Unexpected error fetching buses: {e}")
        bot.send_message(message.chat.id, "❌ Could not fetch bus times right now.",
                         reply_markup=gen_reply_keyboard())
        return

    text = format_bus_arrivals_html(
        arrivals,
        title=message.text,
        subtitle=f"from {route['stop_name']} (stop {route['stop']})",
        show_line=False,
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML',
                     reply_markup=gen_reply_keyboard())


@bot.message_handler(func=lambda message: (message.text or '').strip().isdigit())
@restricted_access
def handle_stop_code(message):
    stop_code = message.text.strip()

    bot.send_message(message.chat.id, f"⏳ Checking stop {stop_code}...")

    try:
        arrivals = curlbus_req.get_arrivals(stop_code)
    except curlbus_req.CurlbusError as e:
        bot.send_message(message.chat.id, f"❌ {e}", reply_markup=gen_reply_keyboard())
        return
    except Exception as e:
        print(f"Unexpected error fetching stop {stop_code}: {e}")
        bot.send_message(message.chat.id, "❌ Could not fetch arrivals right now.",
                         reply_markup=gen_reply_keyboard())
        return

    text = format_bus_arrivals_html(
        arrivals[:MAX_ARRIVALS],
        title=f"Stop {stop_code}",
        subtitle=f"next {curlbus_req.DEFAULT_WINDOW_MINUTES} minutes",
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML',
                     reply_markup=gen_reply_keyboard())


print("Bot starting. Allowed IDs:", ALLOWED_USER_IDS)
bot.infinity_polling()
