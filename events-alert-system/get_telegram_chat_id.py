from telegram import Bot

TOKEN = "7776029372:AAF6p__5OrxhKCHl_VJKEJEYFX8ZO_JMkuk"
bot = Bot(token=TOKEN)

# Get the last update (someone sent a message to the bot)
updates = bot.get_updates()

if not updates:
    print("No messages found. Send /start to the bot first.")
else:
    for update in updates:
        if update.message:
            print("Chat ID:", update.message.chat.id)
