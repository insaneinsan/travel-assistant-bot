from ChatGPT_HKBU import ChatGPT
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import configparser
import logging
import os
import time
from db import MongoLogger
import time
import threading

APP_START_TIME = time.time()

METRICS = {
    "status": "starting",
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "total_response_time": 0.0,
    "last_error": None
}

gpt = None
mongo_logger = None
user_sessions = {}

def get_metrics_snapshot():
    uptime_seconds = round(time.time() - APP_START_TIME, 2)

    completed = METRICS["successful_requests"] + METRICS["failed_requests"]
    avg_response_time = 0.0
    if completed > 0:
        avg_response_time = round(METRICS["total_response_time"] / completed, 2)

    return {
        "status": METRICS["status"],
        "uptime_seconds": uptime_seconds,
        "total_requests": METRICS["total_requests"],
        "successful_requests": METRICS["successful_requests"],
        "failed_requests": METRICS["failed_requests"],
        "average_response_time_seconds": avg_response_time,
        "last_error": METRICS["last_error"]
    }
def log_metrics_periodically():
    while True:
        logger.info("METRICS_SNAPSHOT | %s", get_metrics_snapshot())
        time.sleep(300)  # every 5 minutes
def load_config():
    config = configparser.ConfigParser()
    config.read("config.ini")
    return config

def get_setting(config, env_name, section, key, fallback=None):
    return os.getenv(env_name) or config.get(section, key, fallback=fallback)

def setup_logging():
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=logging.INFO
    )
    return logging.getLogger("travel_bot")

logger = setup_logging()

def detect_intent(text: str) -> str:
    text = text.lower()

    if any(word in text for word in ["plan", "itinerary", "trip", "travel plan", "days in"]):
        return "itinerary"
    if any(word in text for word in ["pack", "packing"]):
        return "packing"
    if any(word in text for word in ["food", "eat", "restaurant"]):
        return "food"
    if any(word in text for word in ["weather", "temperature", "rain"]):
        return "weather"
    if any(word in text for word in ["transport", "bus", "metro", "taxi", "train"]):
        return "transport"

    return "general_travel"

def main():
    logger.info("INIT | loading configuration")
    config = load_config()

    telegram_token = get_setting(config, "TELEGRAM_TOKEN", "TELEGRAM", "ACCESS_TOKEN")
    if not telegram_token:
        raise ValueError("Missing TELEGRAM token. Set TELEGRAM_TOKEN or config.ini.")

    logger.info("INIT | connecting telegram bot")
    app = ApplicationBuilder().token(telegram_token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    global gpt, mongo_logger
    gpt = ChatGPT(config)
    mongo_logger = MongoLogger(config)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, callback))

    METRICS["status"] = "running"

    metrics_thread = threading.Thread(target=log_metrics_periodically, daemon=True)
    metrics_thread.start()

    logger.info("INIT | bot started successfully")
    app.run_polling()

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time = time.time()
    METRICS["total_requests"] += 1

    if not update.message or not update.message.text:
        logger.warning("MESSAGE | skipped non-text update")
        return

    user_id = update.message.from_user.id
    username = update.message.from_user.username or "unknown"
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    user_text = update.message.text.strip()

    logger.info(
        "MESSAGE_RECEIVED | user_id=%s | username=%s | chat_id=%s | text=%s",
        user_id, username, chat_id, user_text[:300]
    )

    if user_id not in user_sessions:
        user_sessions[user_id] = []

    user_sessions[user_id].append({
        "role": "user",
        "content": user_text
    })

    history = user_sessions[user_id][-10:]
    intent = detect_intent(user_text)

    logger.info(
        "INTENT_DETECTED | user_id=%s | intent=%s | history_size=%s",
        user_id, intent, len(history)
    )

    loading_message = await update.message.reply_text("Thinking...")

    try:
        logger.info("LLM_REQUEST_START | user_id=%s | intent=%s", user_id, intent)
        response = gpt.submit_with_history(history)
        logger.info("LLM_REQUEST_SUCCESS | user_id=%s | response_len=%s", user_id, len(response))

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
        logger.info("DB_LOG_SAVED | user_id=%s", user_id)

        try:
            await loading_message.delete()
        except Exception:
            logger.warning("LOADING_MESSAGE_DELETE_FAILED | user_id=%s", user_id)

        await send_long_message(update.message, response)

        duration = time.time() - start_time
        METRICS["successful_requests"] += 1
        METRICS["total_response_time"] += duration

        logger.info(
            "REQUEST_SUCCESS | user_id=%s | duration=%.2fs",
            user_id, duration
        )


    except Exception as e:
        duration = time.time() - start_time
        METRICS["failed_requests"] += 1
        METRICS["total_response_time"] += duration
        METRICS["last_error"] = str(e)

        logger.exception(
            "REQUEST_FAILED | user_id=%s | duration=%.2fs | error=%s",
            user_id, duration, str(e)
        )

        await update.message.reply_text(
            "Sorry, something went wrong while processing your request."
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("COMMAND_START | user_id=%s", update.effective_user.id if update.effective_user else "unknown")
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
    logger.info("COMMAND_HELP | user_id=%s", update.effective_user.id if update.effective_user else "unknown")
    await update.message.reply_text(
        "You can ask me travel questions in normal text.\n\n"
        "Examples:\n"
        "- Plan 5 days in Tokyo for food lovers\n"
        "- What is the best time to visit Switzerland?\n"
        "- How can I travel cheaply in Paris?\n"
        "- What food should I try in Japan?"
    )

async def send_long_message(message, text, chunk_size=4000):
    total_chunks = (len(text) + chunk_size - 1) // chunk_size
    logger.info("SEND_LONG_MESSAGE | chunks=%s | text_len=%s", total_chunks, len(text))

    for i in range(0, len(text), chunk_size):
        await message.reply_text(text[i:i + chunk_size])

if __name__ == "__main__":
    main()