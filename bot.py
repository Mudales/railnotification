from decouple import config
import telebot
from telebot.types import (ReplyKeyboardMarkup, KeyboardButton,
                            InlineKeyboardMarkup, InlineKeyboardButton)
from telebot.apihelper import ApiTelegramException
import json
import datetime
import functools
import html

import rail_req
import curlbus_req
import favorites

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

# Favourite-stop buttons are prefixed so they can't collide with the fixed ones.
FAV_PREFIX = '⭐ '


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


def gen_reply_keyboard(user_id=None):
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

    saved = list(favorites.list_for(user_id)) if user_id else []
    for i in range(0, len(saved), 2):
        markup.row(*(KeyboardButton(FAV_PREFIX + name) for name in saved[i:i + 2]))
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


def format_bus_arrivals_html(arrivals, title, subtitle=None, show_line=True,
                             limit=None):
    """Render curlbus arrivals as one short line per bus.

    Destinations are Hebrew, so they go last on each line - mixing RTL text
    into the middle of an LTR line makes Telegram reorder it oddly.

    With `limit`, only the soonest `limit` buses are listed and the rest are
    summed up on a last line, so a busy stop stays readable.
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

    hidden = 0
    if limit is not None and len(arrivals) > limit:
        hidden = len(arrivals) - limit
        arrivals = arrivals[:limit]

    for arrival in arrivals:
        when = arrival['eta'].strftime('%H:%M')
        minutes = arrival['minutes']
        due = "<b>now</b>" if minutes <= 1 else f"<b>{minutes} min</b>"

        row = "🚌 "
        if show_line:
            row += f"<b>{esc(arrival['line'])}</b> · "
        row += f"{due} <i>({when})</i>"

        # A tracked bus is one the feed has a live position for; everything
        # else is the timetable's guess.
        if arrival['tracked']:
            row += " 📍"
            if arrival['distance_km'] is not None:
                row += f"{arrival['distance_km']:.1f}km"

        destination = arrival['destination']
        if destination:
            if len(destination) > MAX_DEST_CHARS:
                destination = destination[:MAX_DEST_CHARS - 1].rstrip() + '…'
            row += f" ← {esc(destination)}"
        header.append(row)

    if hidden:
        header.append(f"<i>+ {hidden} more within "
                      f"{curlbus_req.DEFAULT_WINDOW_MINUTES} min</i>")

    header.append(f"<i>updated {now_hhmmss()}</i>")
    return "\n".join(header)


def now_hhmmss():
    return datetime.datetime.now(curlbus_req.ISRAEL_TZ).strftime('%H:%M:%S')


def refresh_markup(kind, key):
    """A single "refresh" button carrying what to re-query.

    Telegram caps callback_data at 64 bytes, so a bus route travels as its
    index rather than its label.
    """
    if kind == 'b':
        try:
            key = BUS_BUTTONS.index(key)
        except ValueError:
            return None
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton('🔄 Refresh', callback_data=f"{kind}|{key}"))
    return markup


def render_stop(stop_code, use_cache=True):
    stop = curlbus_req.get_stop(stop_code, use_cache=use_cache)

    subtitle = f"Stop {stop['code']}"
    if stop['city']:
        subtitle += f" · {stop['city']}"
    subtitle += f" · next {curlbus_req.DEFAULT_WINDOW_MINUTES} min"

    return format_bus_arrivals_html(
        stop['arrivals'],
        title=stop['name'] or f"Stop {stop['code']}",
        subtitle=subtitle,
        limit=MAX_ARRIVALS,
    )


def render_bus_route(label, use_cache=True):
    route = curlbus_req.BUS_ROUTES[label]
    arrivals = curlbus_req.get_arrivals(
        route['stop'],
        within_minutes=curlbus_req.DEFAULT_WINDOW_MINUTES,
        lines={route['line']},
        use_cache=use_cache,
    )
    return format_bus_arrivals_html(
        arrivals,
        title=label,
        subtitle=f"from {route['stop_name']} (stop {route['stop']})",
        show_line=False,
    )


def send_or_edit(chat_id, message_id, text, markup=None):
    if message_id is None:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
        return
    try:
        bot.edit_message_text(text, chat_id, message_id,
                              parse_mode='HTML', reply_markup=markup)
    except ApiTelegramException as e:
        # Telegram rejects an edit that would change nothing.
        if 'message is not modified' not in str(e):
            raise


def answer_arrivals(chat_id, message_id, kind, key, use_cache=True):
    """Put one arrivals view on screen, as a new message or an edit."""
    try:
        if kind == 's':
            text = render_stop(key, use_cache=use_cache)
        else:
            text = render_bus_route(key, use_cache=use_cache)
    except curlbus_req.CurlbusError as e:
        send_or_edit(chat_id, message_id, f"❌ {esc(e)}")
        return
    except Exception as e:
        print(f"Unexpected error rendering {kind} {key!r}: {e}")
        send_or_edit(chat_id, message_id, "❌ Could not fetch arrivals right now.")
        return

    send_or_edit(chat_id, message_id, text, refresh_markup(kind, key))


@bot.message_handler(commands=['start', 'hello', 'help'])
@restricted_access
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Rail Notification Bot</b>\n"
        "Live trains and buses.\n"
        f"{'━' * 20}\n\n"
        "🚂 <b>Trains</b> - tap a route button for the next departures, "
        "with platform and live delays.\n\n"
        "🚌 <b>Buses</b> - tap a 460 / 464 button for the next buses in "
        "that direction.\n\n"
        "🔢 <b>Any stop</b> - just send a stop number, for example "
        "<code>35096</code>, and get its name plus every line due there in "
        f"the next {curlbus_req.DEFAULT_WINDOW_MINUTES} minutes.\n\n"
        "⭐ <b>Favourites</b> - save the stops you use and they become "
        "buttons.\n\n"
        f"{'━' * 20}\n"
        "<b>Commands</b>\n"
        "/times - show or refresh the buttons\n"
        "/save &lt;code&gt; &lt;name&gt; - e.g. <code>/save 35096 Home</code>\n"
        "/favs - list your saved stops\n"
        "/del &lt;name&gt; - remove one\n"
        "/help - this message\n\n"
        "<i>Buttons gone or out of date? Send /times to bring them back.\n"
        "Stop numbers are printed on the stop sign, and show up in Google "
        "Maps too.\n"
        "📍 means a bus the feed is tracking right now; the distance next to "
        "it is a straight line to the stop, so it can look odd on a winding "
        "route. No 📍 means the time comes from the timetable.\n"
        "🔄 under a reply fetches it again.</i>",
        parse_mode='HTML',
        reply_markup=gen_reply_keyboard(message.from_user.id)
    )


@bot.message_handler(commands=['times','time'])
@restricted_access
def request_route(message):
    bot.send_message(
        message.chat.id,
        "Select a route:",
        reply_markup=gen_reply_keyboard(message.from_user.id)
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

        bot.send_message(message.chat.id, text, parse_mode='HTML',
                         reply_markup=gen_reply_keyboard(message.from_user.id))

    except Exception as e:
        print(f"Error fetching trains: {e}")
        bot.send_message(message.chat.id, f"❌ Error: {e}")


@bot.message_handler(func=lambda message: message.text in curlbus_req.BUS_ROUTES)
@restricted_access
def handle_bus_choice(message):
    placeholder = bot.send_message(message.chat.id, "⏳ Fetching buses...")
    answer_arrivals(message.chat.id, placeholder.message_id, 'b', message.text)


@bot.message_handler(func=lambda message: (message.text or '').strip().isdigit())
@restricted_access
def handle_stop_code(message):
    stop_code = message.text.strip()
    placeholder = bot.send_message(message.chat.id, f"⏳ Checking stop {stop_code}...")
    answer_arrivals(message.chat.id, placeholder.message_id, 's', stop_code)


@bot.message_handler(func=lambda message: (message.text or '').startswith(FAV_PREFIX))
@restricted_access
def handle_favorite_button(message):
    name = message.text[len(FAV_PREFIX):].strip()
    stop_code = favorites.list_for(message.from_user.id).get(name)

    if not stop_code:
        bot.send_message(
            message.chat.id,
            f"🤔 <b>{esc(name)}</b> is not saved any more. /favs shows what is.",
            parse_mode='HTML',
            reply_markup=gen_reply_keyboard(message.from_user.id),
        )
        return

    placeholder = bot.send_message(message.chat.id, f"⏳ Checking {name}...")
    answer_arrivals(message.chat.id, placeholder.message_id, 's', stop_code)


@bot.message_handler(commands=['save'])
@restricted_access
def handle_save(message):
    parts = (message.text or '').split(maxsplit=2)
    if len(parts) < 3:
        bot.send_message(
            message.chat.id,
            "Usage: <code>/save 35096 Home</code>",
            parse_mode='HTML',
        )
        return

    stop_code, name = parts[1].strip(), parts[2]

    # Check the stop exists before saving a button that would always fail.
    try:
        stop = curlbus_req.get_stop(stop_code)
        real_name = stop['name']
    except curlbus_req.UnknownStop as e:
        bot.send_message(message.chat.id, f"❌ {esc(e)}")
        return
    except curlbus_req.CurlbusError as e:
        # The service is down, not the code - take the user's word for it.
        print(f"/save could not verify {stop_code}: {e}")
        real_name = None
    except Exception as e:
        print(f"/save unexpected error for {stop_code}: {e}")
        real_name = None

    try:
        name = favorites.add(message.from_user.id, name, stop_code)
    except favorites.FavoritesError as e:
        bot.send_message(message.chat.id, f"❌ {esc(e)}")
        return

    saved = f"⭐ Saved <b>{esc(name)}</b> as stop {esc(stop_code)}"
    saved += f"\n{esc(real_name)}" if real_name else ""
    bot.send_message(message.chat.id, saved, parse_mode='HTML',
                     reply_markup=gen_reply_keyboard(message.from_user.id))


@bot.message_handler(commands=['favs', 'favourites', 'favorites'])
@restricted_access
def handle_favs(message):
    saved = favorites.list_for(message.from_user.id)
    if not saved:
        bot.send_message(
            message.chat.id,
            "No favourites yet. Save one with <code>/save 35096 Home</code>.",
            parse_mode='HTML',
        )
        return

    lines = ["⭐ <b>Your stops</b>"]
    lines += [f"<code>{esc(code)}</code> · {esc(name)}"
              for name, code in saved.items()]
    lines.append("\n<i>Remove one with /del &lt;name&gt;</i>")
    bot.send_message(message.chat.id, "\n".join(lines), parse_mode='HTML',
                     reply_markup=gen_reply_keyboard(message.from_user.id))


@bot.message_handler(commands=['del', 'delete', 'rm'])
@restricted_access
def handle_delete(message):
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: <code>/del Home</code>",
                         parse_mode='HTML')
        return

    name = parts[1]
    if favorites.remove(message.from_user.id, name):
        text = f"🗑 Removed <b>{esc(name)}</b>."
    else:
        text = f"🤔 No favourite called <b>{esc(name)}</b>. /favs lists them."
    bot.send_message(message.chat.id, text, parse_mode='HTML',
                     reply_markup=gen_reply_keyboard(message.from_user.id))


@bot.callback_query_handler(func=lambda call: (call.data or '')[:2] in ('s|', 'b|'))
@restricted_access
def handle_refresh(call):
    kind, _, key = call.data.partition('|')

    if kind == 'b':
        try:
            key = BUS_BUTTONS[int(key)]
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "That button is out of date.")
            return

    bot.answer_callback_query(call.id, "Refreshing…")
    # Skip the cache: the user is asking precisely because time has passed.
    answer_arrivals(call.message.chat.id, call.message.message_id, kind, key,
                    use_cache=False)


@bot.message_handler(func=lambda message: True)
@restricted_access
def handle_unknown(message):
    bot.send_message(
        message.chat.id,
        "🤔 Not sure what that is.\n"
        "Send a <b>stop number</b> like <code>35096</code>, tap a button, "
        "or see /help.",
        parse_mode='HTML',
        reply_markup=gen_reply_keyboard(message.from_user.id),
    )


print("Bot starting. Allowed IDs:", ALLOWED_USER_IDS)
bot.infinity_polling()
