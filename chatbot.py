from ChatGPT_HKBU import ChatGPT
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import configparser
import logging
import os
from db import MongoLogger

gpt = None
mongo_logger = None
user_sessions = {}


def load_config():
    config = configparser.ConfigParser()
    config.read("config.ini")
    return config


def get_setting(config, env_name, section, key, fallback=None):
    return os.getenv(env_name) or config.get(section, key, fallback=fallback)


def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

    logging.info("INIT: Loading configuration...")
    config = load_config()

    telegram_token = get_setting(config, "TELEGRAM_TOKEN", "TELEGRAM", "ACCESS_TOKEN")

    if not telegram_token:
        raise ValueError("Missing TELEGRAM token. Set TELEGRAM_TOKEN or config.ini.")

    logging.info("INIT: Connecting the Telegram bot...")
    app = ApplicationBuilder().token(telegram_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    global gpt, mongo_logger
    gpt = ChatGPT(config)
    mongo_logger = MongoLogger(config)

    logging.info("INIT: Registering the message handler...")
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback))

    logging.info("INIT: Initialization done!")
    app.run_polling()


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("UPDATE: %s", update)

    if not update.message or not update.message.text:
        return

    user_id = update.message.from_user.id
    user_text = update.message.text
    username = update.message.from_user.username

    if user_id not in user_sessions:
        user_sessions[user_id] = []

    user_sessions[user_id].append({
        "role": "user",
        "content": user_text
    })

    history = user_sessions[user_id][-10:]

    loading_message = await update.message.reply_text("Thinking...")

    try:
        response = gpt.submit_with_history(history)

        user_sessions[user_id].append({
            "role": "assistant",
            "content": response
        })

        mongo_logger.save_chat_log(
            user_id=user_id,
            username=username,
            message=user_text,
            response=response
        )

        try:
            await loading_message.delete()
        except Exception:
            pass

        await send_long_message(update.message, response)

    except Exception as e:
        try:
            await loading_message.delete()
        except Exception:
            pass

        await update.message.reply_text(f"Error: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I am your AI travel assistant.\n\n"
        "I can help you with:\n"
        "1. Travel itinerary generation\n"
        "2. Travel-related questions\n\n"
        "Examples:\n"
        "- Plan 3 days in Vienna with low budget\n"
        "- What should I pack for Dubai in August?\n"
        "- Suggest a weekend trip to Rome"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "You can ask me travel questions in normal text.\n\n"
        "Examples:\n"
        "- Plan 5 days in Tokyo for food lovers\n"
        "- What is the best time to visit Switzerland?\n"
        "- How can I travel cheaply in Paris?\n"
        "- What food should I try in Japan?"
    )


async def send_long_message(message, text, chunk_size=4000):
    for i in range(0, len(text), chunk_size):
        await message.reply_text(text[i:i + chunk_size])


if __name__ == "__main__":
    main()