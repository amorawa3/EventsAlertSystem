import requests
import schedule
import time
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Updater, MessageHandler, Filters
import pytz
import threading
import time
import logging
from logging.handlers import TimedRotatingFileHandler
import os

# === LOGGING ===
LOG_DIR = "./logs"
LOG_FILE = os.path.join(LOG_DIR, "events.log")


# Make sure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)


# Set up rotating file handler (rotates daily, keeps 1 backup)
handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=1, encoding="utf-8")
handler.setLevel(logging.INFO)

# Log format
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)

# Configure global logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# === CONFIG ===
TEAM_IDS = {
    "USA": "134514",          # US Men's National Team
    "CRC": "134505",          # Costa Rica National Team
    "ATL_FALCONS": "134942",
    "ATL_HAWKS": "134880",
    "ATL_MLB": "135268",      # Atlanta Braves
    "ATL_UTD": "135851",      # Atlanta United
    "GATECH_FOOTBALL": "136893", # Georgia Tech Football
    "GATECH_BASKETBALL": "138614" # Georgia Tech Basketball
}

TEAM_NAME_MAP = {
    "USA": "USA",
    "CRC": "Costa Rica",
    "ATL_FALCONS": "Atlanta Falcons",
    "ATL_HAWKS": "Atlanta Hawks",
    "ATL_MLB": "Atlanta Braves",
    "ATL_UTD": "Atlanta United",
    "GATECH_FOOTBALL": "Georgia Tech Football",
    "GATECH_BASKETBALL": "Georgia Tech Basketball",
    "F1": "Formula 1"
}

TELEGRAM_BOT_TOKEN = "7610082719:AAHKcVe7UnibVB87UrHcz2q7Qm7flnGRUvQ"
TELEGRAM_CHAT_ID = "7635798789"
EASTERN = pytz.timezone("US/Eastern")
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def send_alert(msg):
    logger.info("[TELEGRAM]", msg)
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception(f"[ERROR] Failed to send Telegram message: {e}")

def parse_game_time(date_str):
    # TheSportsDB date format is "YYYY-MM-DD HH:MM:SS"
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    # Assume time is in UTC — convert to Eastern
    dt = pytz.utc.localize(dt).astimezone(EASTERN)
    return dt

def fetch_next_f1_event():
    try:
        url = "https://www.thesportsdb.com/api/v1/json/123/eventsnextleague.php?id=4370"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])

        if not events:
            return None

        next_event = events[0]
        name = next_event["strEvent"]
        date_str = next_event["dateEvent"]
        time_str = next_event["strTime"] or "00:00:00"
        event_dt = datetime.strptime(date_str + " " + time_str, "%Y-%m-%d %H:%M:%S")
        event_dt = pytz.utc.localize(event_dt).astimezone(EASTERN)

        return {
            "team_key": "F1",
            "opponent": name,
            "time": event_dt
        }
    except Exception as e:
        logger.exception(f"⚠️ Failed to fetch F1 event: {e}")
        return None
    
def fetch_games_today():
    today = datetime.now(EASTERN).date()
    all_games = fetch_next_games()
    return [g for g in all_games if g["time"].date() == today]

def fetch_games_tomorrow():
    tomorrow = datetime.now(EASTERN).date() + timedelta(days=1)
    all_games = fetch_next_games()
    return [g for g in all_games if g["time"].date() == tomorrow]

def fetch_next_games():
    games = []
    f1_event = fetch_next_f1_event()
    if f1_event:
        games.append(f1_event)
    for team_key, team_id in TEAM_IDS.items():
        url = f"https://www.thesportsdb.com/api/v1/json/123/eventsnext.php?id={team_id}"
        resp = requests.get(url)
        if resp.status_code != 200:
            logger.warning(f"Failed to fetch for {team_key}: HTTP {resp.status_code}")
            continue
        data = resp.json()
        events = data.get("events")
        if not events:
            continue
        # Get the soonest upcoming event (first in list)
        event = events[0]
        game_time = event.get("dateEvent") + " " + (event.get("strTime") or "00:00:00")
        try:
            game_dt = parse_game_time(game_time)
        except Exception as e:
            logger.exception(f"Failed to parse date/time for {team_key}: {game_time}, error: {e}")
            continue
        home = event.get("strHomeTeam")
        away = event.get("strAwayTeam")
        team_name = event.get("strTeam")
        opponent = away if home == team_name else home
        games.append({
            "team_key": team_key,
            "opponent": opponent,
            "time": game_dt,
        })
    return games

def format_games(games, header):
    if not games:
        return header + "\nNo upcoming games found."

    lines = []
    included_keys = set()

    for g in sorted(games, key=lambda x: x["time"]):
        dt = g["time"]
        date_str = dt.strftime("%b %d")         # e.g., "Jul 27"
        time_str = dt.strftime("%I:%M %p ET")   # e.g., "09:00 AM ET"
        team_key = g["team_key"]
        opponent = g["opponent"]
        included_keys.add(team_key)

        if team_key == "F1":
            lines.append(f"*Formula 1* races in the *{opponent}* on {date_str}, {time_str}")
        else:
            team_full = TEAM_NAME_MAP.get(team_key, team_key)
            lines.append(f"*{team_full}* vs *{opponent}* on {date_str}, {time_str}")

    # Add "no games scheduled" message for teams not included
    for key, name in TEAM_NAME_MAP.items():
        if key not in included_keys:
            lines.append(f"No games currently scheduled for *{name}* on TheSportsDB.")

    return header + "\n\n" + "\n\n".join(lines)

def handle_message(update, context):
    text = update.message.text.lower().strip()

    if text == "upcoming games":
        games = fetch_next_games()
        msg = format_games(games, "🔜 *Upcoming Games:*")
        update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "games today":
        games = fetch_games_today()
        msg = format_games(games, "📅 *Games Today:*")
        update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "help":
        msg = (
            "🤖 *Available Commands:*\n"
            "- `upcoming games`: Show the next scheduled game for each team\n"
            "- `games today`: Show all games scheduled for today\n"
            "- `help`: Show this help message"
        )
        update.message.reply_text(msg, parse_mode="Markdown")

    else:
        update.message.reply_text(
            "❓ Unknown command. Type `help` to see available commands.",
            parse_mode="Markdown"
        )

def alert_games_today():
    games = fetch_games_today()
    msg = format_games(games, "📅 *Today's Games:*")
    logger.info("Sending today's game alert:\n%s", msg)
    send_alert(msg)

def alert_games_tomorrow():
    games = fetch_games_tomorrow()
    msg = format_games(games, "⏭ *Tomorrow's Games:*")
    logger.info("Sending tomorrow's game alert:\n%s", msg)
    send_alert(msg)

def schedule_one_hour_warnings(for_tomorrow=False):
    day_label = "tomorrow" if for_tomorrow else "today"
    logger.info(f"Scheduling one-hour warnings for {day_label}'s games...")

    # Clear only old reminder jobs
    schedule.clear("reminders")

    # Pick correct fetcher
    games = fetch_games_tomorrow() if for_tomorrow else fetch_games_today()
    now = datetime.now(EASTERN)

    for g in games:
        reminder_time = g["time"] - timedelta(hours=1)

        # Skip games that start in less than 1 hour or already passed
        if reminder_time <= now:
            continue

        msg = (
            f"⏰ *Reminder:*\n"
            f"*{TEAM_NAME_MAP.get(g['team_key'], g['team_key'])}* "
            f"play vs *{g['opponent']}* at {g['time'].strftime('%I:%M %p ET')} "
            f"(in 1 hour)"
        )

        # Tag these jobs as "reminders" so we can clear them later
        schedule.every().day.at(reminder_time.strftime("%H:%M")).do(
            lambda m=msg: send_alert(m)
        ).tag("reminders")

        logger.info(f"Scheduled reminder at {reminder_time.strftime('%I:%M %p')} ET: {msg}")


def run_scheduler():
    # Clear reminders at 23:59 and re-add for any games still today
    schedule.every().day.at("23:59").do(refresh_reminders)

    # Full reset at 00:01 for the new day
    schedule.every().day.at("00:01").do(lambda: schedule.clear("reminders"))
    schedule.every().day.at("00:01").do(schedule_one_hour_warnings)

    # 10 AM → summary of today
    schedule.every().day.at("10:00").do(alert_games_today)

    # 8 PM → summary of tomorrow
    schedule.every().day.at("20:00").do(alert_games_tomorrow)

    # 8 PM → tomorrow’s reminders
    schedule.every().day.at("20:01").do(schedule_one_hour_warnings, for_tomorrow=True)

    while True:
        schedule.run_pending()
        time.sleep(30)

def refresh_reminders():
    logger.info("23:59 cleanup: clearing reminders and re-adding for late games")
    schedule.clear("reminders")
    schedule_one_hour_warnings()

def main():
    while True:
        try:
            logger.info("[INFO] Starting Telegram bot polling...")

            updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
            dispatcher = updater.dispatcher
            dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

            updater.start_polling(drop_pending_updates=True)
            threading.Thread(target=run_scheduler, daemon=True).start()
            schedule_one_hour_warnings()

            updater.idle()
        except Exception as e:
            logger.error(f"[ERROR] Bot crashed: {e}. Restarting in 10 seconds...")
            time.sleep(10)


if __name__ == "__main__":
    main()
