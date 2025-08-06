from telegram import Bot

TOKEN = "7610082719:AAHKcVe7UnibVB87UrHcz2q7Qm7flnGRUvQ"

bot = Bot(token=TOKEN)
updates = bot.get_updates()

for update in updates:
    print(update.message.chat.id)