from decouple import config
import re
from telebot import types
from telebot.types import KeyboardButton
import telebot


api_key = config("api_key")
bot = telebot.TeleBot(api_key)


button1 = KeyboardButton("choose Catgegory")

@bot.message_handler(commands=['start', 'hello', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Hi, i'am bot that will help you to get a name for phone number")

@bot.message_handler()
def phone(message):
    button1 = KeyboardButton("choose Catgegory")
    pattern = "^\\+?\\d{1,4}?[-.\\s]?\\(?\\d{1,3}?\\)?[-.\\s]?\\d{1,4}[-.\\s]?\\d{1,4}[-.\\s]?\\d{1,9}$"
    if re.match(pattern, str(message.text)):
        response_api = Response_me_api(number=message.text, accessnumber='972539567647')
        bot.reply_to(message, response_api.result)
    else:
        bot.reply_to(message, 'send me 9 or 10 digit phone number ')
        print(message)


bot.infinity_polling()