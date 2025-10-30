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

os.makedirs(LOG_DIR, exist_ok=True)

handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=1, encoding="utf-8")
handler.setLevel(logging.INFO)

formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# === CONFIG ===
TEAM_IDS = {
    "USA": "134514",
    "CRC": "134505",
    "ATL_FALCONS": "134942",
    "ATL_HAWKS": "134880",
    "ATL_MLB": "135268",
    "ATL_UTD": "135851",
    "GATECH_FOOTBALL": "136893",
    "GATECH_BASKETBALL": "138614"
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
    logger.info("[TELEGRAM] " + msg)
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception(f"[ERROR] Failed to send Telegram message: {e}")

def parse_game_time(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
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
        return {"team_key": "F1", "opponent": name, "time": event_dt}
    except Exception as e:
        logger.exception(f"⚠️ Failed to fetch F1 event: {e}")
        return None

def fetch_next_games():
    games = []
    f1_event = fetch_next_f1_event()
    if f1_event:
        games.append(f1_event)

    for team_key, team_id in TEAM_IDS.items():
        url = f"https://www.thesportsdb.com/api/v1/json/123/eventsnext.php?id={team_id}"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch for {team_key}: {e}")
            continue

        events = data.get("events")
        if not events:
            logger.info(f"No events found for {team_key}")
            continue

        event = events[0]
        home = event.get("strHomeTeam")
        away = event.get("strAwayTeam")
        home_id = event.get("idHomeTeam")
        away_id = event.get("idAwayTeam")

        opponent = None
        our_side = "unknown"
        try:
            if home_id and str(home_id) == str(team_id):
                opponent = away
                our_side = "home"
            elif away_id and str(away_id) == str(team_id):
                opponent = home
                our_side = "away"
        except Exception:
            pass

        if opponent is None:
            our_team_name = TEAM_NAME_MAP.get(team_key, "").lower()
            if our_team_name and our_team_name in (home or "").lower():
                opponent = away
                our_side = "home"
            elif our_team_name and our_team_name in (away or "").lower():
                opponent = home
                our_side = "away"
            else:
                opponent = home or away

        logger.info(
            f"[FETCH] {team_key}: home='{home}' (id={home_id}), away='{away}' (id={away_id}), "
            f"our_side={our_side}, opponent='{opponent}'"
        )

        game_time_str = event.get("dateEvent") + " " + (event.get("strTime") or "00:00:00")
        try:
            game_dt = parse_game_time(game_time_str)
        except Exception as e:
            logger.exception(f"Failed to parse date/time for {team_key}: {e}")
            continue

        games.append({"team_key": team_key, "opponent": opponent, "time": game_dt})

    return games

def fetch_games_today():
    today = datetime.now(EASTERN).date()
    all_games = fetch_next_games()
    return [g for g in all_games if g["time"].date() == today]

def fetch_games_tomorrow():
    tomorrow = datetime.now(EASTERN).date() + timedelta(days=1)
    all_games = fetch_next_games()
    return [g for g in all_games if g["time"].date() == tomorrow]

def format_games(games, header):
    if not games:
        return header + "\nNo upcoming games found."
    lines = []
    included_keys = set()
    for g in sorted(games, key=lambda x: x["time"]):
        dt = g["time"]
        date_str = dt.strftime("%b %d")
        time_str = dt.strftime("%I:%M %p ET")
        team_key = g["team_key"]
        opponent = g["opponent"]
        included_keys.add(team_key)
        if team_key == "F1":
            lines.append(f"*Formula 1* races in the *{opponent}* on {date_str}, {time_str}")
        else:
            team_full = TEAM_NAME_MAP.get(team_key, team_key)
            lines.append(f"*{team_full}* vs *{opponent}* on {date_str}, {time_str}")
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
            "- `upcoming games`: Show next scheduled game\n"
            "- `games today`: Show today's games\n"
            "- `help`: Show this help message"
        )
        update.message.reply_text(msg, parse_mode="Markdown")
    else:
        update.message.reply_text("❓ Unknown command. Type `help` to see available commands.", parse_mode="Markdown")

def safe_send_alert_for_game(game, msg):
    """Prevent false alerts by confirming the game date before sending."""
    now = datetime.now(EASTERN)
    game_date = game["time"].date()
    if game_date != now.date():
        logger.warning(
            f"[SKIP ALERT] {TEAM_NAME_MAP.get(game['team_key'], game['team_key'])} vs {game['opponent']} "
            f"is on {game_date}, not today ({now.date()}). Skipping message."
        )
        return
    send_alert(msg)

def schedule_one_hour_warnings(for_tomorrow=False):
    day_label = "tomorrow" if for_tomorrow else "today"
    logger.info(f"Scheduling one-hour warnings and game start alerts for {day_label}...")
    schedule.clear("reminders")
    games = fetch_games_tomorrow() if for_tomorrow else fetch_games_today()
    now = datetime.now(EASTERN)
    for g in games:
        game_time = g["time"]
        logger.info(
            f"[DEBUG] Checking game {g['team_key']} vs {g['opponent']} | game_time={game_time} | now={now}"
        )
        if game_time.date() != (now.date() + timedelta(days=1) if for_tomorrow else now.date()):
            logger.info(f"[SKIP] Game on {game_time.date()} doesn't match {day_label} ({now.date()})")
            continue
        reminder_time = g["time"] - timedelta(hours=1)
        if reminder_time > now:
            reminder_msg = (
                f"⏰ *Reminder:*\n"
                f"*{TEAM_NAME_MAP.get(g['team_key'], g['team_key'])}* vs *{g['opponent']}* "
                f"at {g['time'].strftime('%I:%M %p ET')} (in 1 hour)"
            )
            schedule.every().day.at(reminder_time.strftime("%H:%M")).do(
                lambda g=g, m=reminder_msg: safe_send_alert_for_game(g, m)
            ).tag("reminders")
            logger.info(f"Scheduled reminder for {reminder_time.strftime('%I:%M %p')} ET")
        game_start_time = g["time"]
        if game_start_time > now:
            start_msg = (
                f"🏈 *Game Starting Now!*\n"
                f"*{TEAM_NAME_MAP.get(g['team_key'], g['team_key'])}* vs *{g['opponent']}* "
                f"is starting now ({g['time'].strftime('%I:%M %p ET')})!"
            )
            schedule.every().day.at(game_start_time.strftime("%H:%M")).do(
                lambda g=g, m=start_msg: safe_send_alert_for_game(g, m)
            ).tag("reminders")
            logger.info(f"Scheduled game start alert for {game_start_time.strftime('%I:%M %p')} ET")

def run_scheduler():
    schedule.every().day.at("23:59").do(refresh_reminders)
    schedule.every().day.at("00:01").do(lambda: schedule.clear("reminders"))
    schedule.every().day.at("00:01").do(schedule_one_hour_warnings)
    schedule.every().day.at("10:00").do(alert_games_today)
    schedule.every().day.at("20:00").do(alert_games_tomorrow)
    schedule.every().day.at("20:01").do(schedule_one_hour_warnings, for_tomorrow=True)
    while True:
        schedule.run_pending()
        time.sleep(30)

def refresh_reminders():
    logger.info("23:59 cleanup: refreshing reminders...")
    schedule.clear("reminders")
    schedule_one_hour_warnings()

def alert_games_today():
    games = fetch_games_today()
    msg = format_games(games, "📅 *Today's Games:*")
    logger.info("Sending today's game alert")
    send_alert(msg)

def alert_games_tomorrow():
    games = fetch_games_tomorrow()
    msg = format_games(games, "⏭ *Tomorrow's Games:*")
    logger.info("Sending tomorrow's game alert")
    send_alert(msg)

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
