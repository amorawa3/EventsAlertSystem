import requests
import schedule
import time
from datetime import datetime, timedelta
from telegram import Bot
from telegram.ext import Updater, MessageHandler, Filters
import pytz
import threading
import logging
from logging.handlers import TimedRotatingFileHandler
import os

# === LOGGING ===
LOG_DIR = "./logs"
LOG_FILE = os.path.join(LOG_DIR, "events.log")

# Make sure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Set up rotating file handler (rotates daily, keeps 7 backups)
handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=7, encoding="utf-8")
handler.setLevel(logging.INFO)

# Log format
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)

# Configure global logger (file only — as requested)
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

TELEGRAM_BOT_TOKEN = "7776029372:AAF6p__5OrxhKCHl_VJKEJEYFX8ZO_JMkuk"
TELEGRAM_CHAT_ID = "7635798789"
EASTERN = pytz.timezone("US/Eastern")
bot = Bot(token=TELEGRAM_BOT_TOKEN)


# ---------- Utilities ----------
def send_alert(msg):
    """
    Send a message to the configured Telegram chat and log it.
    """
    logger.info("[TELEGRAM] %s", msg.replace("\n", " | "))
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception(f"[ERROR] Failed to send Telegram message: {e}")


def safe_parse_datetime_from_thesportsdb(date_str, time_str):
    """
    Parse TheSportsDB date+time fields robustly.
    date_str: "YYYY-MM-DD" or ISO date/time
    time_str: "HH:MM:SS" or None
    Returns timezone-aware datetime in EASTERN.
    """
    # Many TheSportsDB endpoints provide dateEvent and strTime.
    # We'll try multiple parse attempts and always return an aware datetime in EASTERN.
    dt = None
    # Case 1: combined "YYYY-MM-DD HH:MM:SS"
    if date_str and time_str:
        combined = f"{date_str} {time_str}"
        try:
            naive = datetime.strptime(combined, "%Y-%m-%d %H:%M:%S")
            # TheSportsDB times are usually UTC or have strTimeLocal; assume UTC unless strTimeLocal present/used.
            dt = pytz.utc.localize(naive).astimezone(EASTERN)
            return dt
        except Exception:
            pass

    # Case 2: date_str might be ISO timestamp already
    if date_str:
        try:
            # Try parsing ISO-like timestamp
            # Accept "YYYY-MM-DDTHH:MM:SS" too
            iso_candidate = date_str
            if "T" in iso_candidate:
                # if it has timezone, datetime.fromisoformat will handle offsets
                try:
                    parsed = datetime.fromisoformat(iso_candidate)
                    if parsed.tzinfo is None:
                        parsed = pytz.utc.localize(parsed)
                    dt = parsed.astimezone(EASTERN)
                    return dt
                except Exception:
                    pass
            # Fallback: date only
            try:
                naive = datetime.strptime(date_str, "%Y-%m-%d")
                # assume midnight UTC for date-only (rare)
                dt = pytz.utc.localize(naive).astimezone(EASTERN)
                return dt
            except Exception:
                pass
        except Exception:
            pass

    # Final fallback: now (should not happen but prevents crashes)
    logger.warning("Could not parse date/time: date_str=%r time_str=%r — falling back to now (UTC->ET)", date_str, time_str)
    return datetime.now(pytz.utc).astimezone(EASTERN)


def schedule_job_with_date_check(run_dt, func, tag="reminders"):
    """
    Schedule a daily job at run_dt's clock time, but include a date check inside the job so
    it will only run on the run_dt.date(). This is Option 2 (date-check inside job).
    run_dt must be timezone-aware in EASTERN.
    func is a zero-argument callable to run (e.g., a lambda that sends a message).
    """
    # The scheduler uses local time string "HH:MM"
    hhmm = run_dt.strftime("%H:%M")

    def job_wrapper(target_date=run_dt.date(), inner_func=func):
        now_et = datetime.now(EASTERN)
        if now_et.date() != target_date:
            logger.info("[SCHED-SKIP] Scheduled job at %s skipped because target_date=%s != now=%s",
                        hhmm, target_date, now_et.date())
            return
        try:
            inner_func()
        except Exception as e:
            logger.exception("[SCHED-ERR] Error running scheduled job at %s: %s", hhmm, e)

    # Register job daily at hh:mm; tag it so we can clear later
    schedule.every().day.at(hhmm).do(job_wrapper).tag(tag)
    logger.info("[SCHED] Registered daily job at %s for date %s (tag=%s)", hhmm, run_dt.date(), tag)


# ---------- Data fetching ----------
def fetch_next_f1_event():
    try:
        url = "https://www.thesportsdb.com/api/v1/json/123/eventsnextleague.php?id=4370"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        if not events:
            logger.info("[F1] No events found")
            return None

        # Find the first game whose start time is still in the future
        now_et = datetime.now(EASTERN)
        event = None

        for ev in events:
            date_field = ev.get("dateEvent")
            time_field = ev.get("strTime") or "00:00:00"
            ev_dt = safe_parse_datetime_from_thesportsdb(date_field, time_field)
            logger.info("[FUTURE-CHECK] Candidate event dt=%s now=%s", ev_dt.isoformat(), now_et.isoformat())

            if ev_dt > now_et:
                # THIS is the correct next game
                event = ev
                logger.info("[FUTURE-CHECK] --> SELECTED this as next event")
                break

        # If all events are in the past, fall back to events[0] anyway
        if not event:
            event = events[0]
            logger.info("[FUTURE-CHECK] All events were in the past, falling back to events[0]")
        next_event = event
        name = next_event.get("strEvent")
        date_str = next_event.get("dateEvent")
        time_str = next_event.get("strTime") or "00:00:00"
        event_dt = safe_parse_datetime_from_thesportsdb(date_str, time_str)

        logger.info("[F1] Next: %s @ %s (ET)", name, event_dt.isoformat())
        return {"team_key": "F1", "opponent": name, "time": event_dt}
    except Exception as e:
        logger.exception(f"⚠️ Failed to fetch F1 event: {e}")
        return None


def fetch_next_games():
    """
    Fetch the next upcoming event for each configured team.
    Returns list of dicts: {team_key, opponent, time}
    """
    games = []
    f1_event = fetch_next_f1_event()
    if f1_event:
        games.append(f1_event)

    for team_key, team_id in TEAM_IDS.items():
        url = f"https://www.thesportsdb.com/api/v1/json/123/eventsnext.php?id={team_id}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"Failed to fetch for {team_key}: {e}")
            continue

        events = data.get("events")
        if not events:
            logger.info(f"No events found for {team_key}")
            continue

        # Use the soonest upcoming event
        # Find the first game whose start time is still in the future
        now_et = datetime.now(EASTERN)
        event = None

        for ev in events:
            date_field = ev.get("dateEvent")
            time_field = ev.get("strTime") or "00:00:00"
            ev_dt = safe_parse_datetime_from_thesportsdb(date_field, time_field)

            logger.info("[FUTURE-CHECK] Candidate event dt=%s now=%s", ev_dt.isoformat(), now_et.isoformat())

            if ev_dt > now_et:
                # THIS is the correct next game
                event = ev
                logger.info("[FUTURE-CHECK] --> SELECTED this as next event")
                break

        # If all events are in the past, fall back to events[0] anyway
        if not event:
            event = events[0]
            logger.info("[FUTURE-CHECK] All events were in the past, falling back to events[0]")

        # Raw fields from API
        home = event.get("strHomeTeam")
        away = event.get("strAwayTeam")
        home_id = event.get("idHomeTeam")
        away_id = event.get("idAwayTeam")

        # Determine opponent by comparing IDs first (most reliable)
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
            our_side = "unknown"

        # Fallback: string match (case-insensitive) against TEAM_NAME_MAP if IDs not present/matching
        if opponent is None:
            our_team_name = TEAM_NAME_MAP.get(team_key, "").lower()
            if our_team_name and our_team_name in (home or "").lower():
                opponent = away
                our_side = "home"
            elif our_team_name and our_team_name in (away or "").lower():
                opponent = home
                our_side = "away"
            else:
                # Final fallback: pick the other non-empty field
                opponent = home or away
                our_side = "unknown"

        # Parse time robustly
        date_field = event.get("dateEvent")
        time_field = event.get("strTime") or "00:00:00"
        game_dt = safe_parse_datetime_from_thesportsdb(date_field, time_field)

        # Log details for debugging (important fields)
        logger.info(
            "[FETCH] TeamKey=%s team_id=%s | Home='%s' (id=%s) | Away='%s' (id=%s) | OurSide=%s | Opponent='%s' | event_date=%s strTime=%s => parsed=%s",
            team_key, team_id, home, home_id, away, away_id, our_side, opponent, date_field, time_field,
            game_dt.isoformat()
        )

        games.append({
            "team_key": team_key,
            "opponent": opponent,
            "time": game_dt,
        })

    return games


def fetch_games_today():
    today = datetime.now(EASTERN).date()
    all_games = fetch_next_games()
    filtered = [g for g in all_games if g["time"].date() == today]
    logger.info("[FETCH-TODAY] Found %d games for %s", len(filtered), today)
    return filtered


def fetch_games_tomorrow():
    tomorrow = (datetime.now(EASTERN).date() + timedelta(days=1))
    all_games = fetch_next_games()
    filtered = [g for g in all_games if g["time"].date() == tomorrow]
    logger.info("[FETCH-TOMORROW] Found %d games for %s", len(filtered), tomorrow)
    return filtered


# ---------- Formatting / Handlers ----------
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


# ---------- Alerts & Scheduler ----------
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


def schedule_one_hour_warnings(for_tomorrow=False):
    """
    Build schedule entries for one-hour reminders and game start alerts.
    Uses schedule_job_with_date_check to ensure each scheduled job checks the target date at runtime.
    """
    day_label = "tomorrow" if for_tomorrow else "today"
    logger.info("Scheduling one-hour warnings and game start alerts for %s", day_label)

    # Clear only old reminder jobs
    schedule.clear("reminders")

    # Pick correct fetcher
    games = fetch_games_tomorrow() if for_tomorrow else fetch_games_today()
    now = datetime.now(EASTERN)

    for g in games:
        game_time = g["time"]
        # Debug log for what's being scheduled
        logger.info("[SCHED-PLAN] Team=%s Opp=%s game_time=%s now=%s",
                    g.get("team_key"), g.get("opponent"), game_time.isoformat(), now.isoformat())

        # Skip games not in the target date (extra safety)
        # This is a quick filter so we don't attempt to schedule obviously wrong times
        # but the real guard is the date-check inside scheduled job (Option 2).
        if for_tomorrow:
            target_date = (now.date() + timedelta(days=1))
        else:
            target_date = now.date()
        if game_time.date() != target_date:
            logger.info("[SCHED-SKIP] Not scheduling %s (%s) because event.date=%s != target=%s",
                        g.get("team_key"), g.get("opponent"), game_time.date(), target_date)
            continue

        # 1-hour reminder
        reminder_time = game_time - timedelta(hours=1)
        if reminder_time > now:
            reminder_msg = (
                f"⏰ *Reminder:*\n"
                f"*{TEAM_NAME_MAP.get(g['team_key'], g['team_key'])}* "
                f"play vs *{g['opponent']}* at {game_time.strftime('%I:%M %p ET')} "
                f"(in 1 hour)"
            )
            # schedule a job that will only run on the intended date
            schedule_job_with_date_check(reminder_time, lambda m=reminder_msg: send_alert(m), tag="reminders")
            logger.info("[SCHED] Planned 1-hour reminder for %s at %s (ET)", g.get("team_key"), reminder_time.strftime("%Y-%m-%d %H:%M"))

        # Game start alert
        if game_time > now:
            start_msg = (
                f"🏁 *Game Starting Now!*\n"
                f"*{TEAM_NAME_MAP.get(g['team_key'], g['team_key'])}* vs *{g['opponent']}* is starting now at "
                f"{game_time.strftime('%I:%M %p ET')}!"
            )
            schedule_job_with_date_check(game_time, lambda m=start_msg: send_alert(m), tag="reminders")
            logger.info("[SCHED] Planned start alert for %s at %s (ET)", g.get("team_key"), game_time.strftime("%Y-%m-%d %H:%M"))


def run_scheduler():
    # 23:59 cleanup: clear reminders (keeps the log) and re-add for late games
    schedule.every().day.at("23:59").do(refresh_reminders)

    # Full reset at 00:01 for the new day
    schedule.every().day.at("00:01").do(lambda: schedule.clear("reminders"))
    schedule.every().day.at("00:01").do(schedule_one_hour_warnings)

    # 10 AM → summary of today
    schedule.every().day.at("10:00").do(alert_games_today)

    # 8 PM → summary of tomorrow
    schedule.every().day.at("20:00").do(alert_games_tomorrow)

    # 8:01 PM → tomorrow’s reminders (build reminders for tomorrow)
    schedule.every().day.at("20:01").do(schedule_one_hour_warnings, for_tomorrow=True)

    logger.info("Scheduler started")
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.exception("[SCHED-LOOP] Exception in run_pending: %s", e)
        time.sleep(30)


def refresh_reminders():
    logger.info("23:59 cleanup: clearing reminders and re-adding for late games")
    schedule.clear("reminders")
    # Rebuild for any games still today
    schedule_one_hour_warnings()


# ---------- Main ----------
def main():
    while True:
        try:
            logger.info("[INFO] Starting Telegram bot polling...")

            updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
            dispatcher = updater.dispatcher
            dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

            updater.start_polling(drop_pending_updates=True)

            # Start scheduler thread
            t = threading.Thread(target=run_scheduler, daemon=True)
            t.start()

            # Initial build of reminders for today
            schedule_one_hour_warnings()

            updater.idle()
        except Exception as e:
            logger.exception("[MAIN] Bot crashed: %s. Restarting in 10 seconds...", e)
            time.sleep(10)


if __name__ == "__main__":
    main()
