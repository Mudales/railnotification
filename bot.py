from decouple import config
import telebot
import rail_req

# print(rail_req.response)


BOT_API = config("BOT_API")
bot = telebot.TeleBot(BOT_API) # type: ignore


@bot.message_handler(commands=['start', 'hello', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Hi, i'am bot Rail lates ")

@bot.message_handler(commands=['times'])
def phone(message):
    bot.reply_to(message, f"this the time of the train: {rail_req.main()}")
    # bot.send_message(message.chat.id, f"this the time of the train: {rail_req.main()}")
    



@bot.message_handler()
def genric_reply(message):
    bot.reply_to(message, "hi there, i am a bot")
    bot.reply_to(message, "how can i help you?")
 
 
bot.infinity_polling()