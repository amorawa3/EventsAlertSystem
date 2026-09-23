import os
import time

import requests


INTERVAL_SECONDS = 30
DISCORD_API_URL = "https://discord.com/api/v10"
DISCORD_USER_ID = "339982527840387074"


def get_required_setting(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} environment variable is required")
    return value


def send_test_message(token, channel_id):
    response = requests.post(
        f"{DISCORD_API_URL}/channels/{channel_id}/messages",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
        },
        json={"content": f"<@{DISCORD_USER_ID}> hello"},
        timeout=10,
    )
    response.raise_for_status()
    print("Sent: hello", flush=True)


def main():
    token = get_required_setting("DISCORD_BOT_TOKEN")
    channel_id = get_required_setting("DISCORD_CHANNEL_ID")

    print("Sending a mention with 'hello' every 30 seconds. Press Ctrl+C to stop.", flush=True)
    while True:
        try:
            send_test_message(token, channel_id)
        except requests.RequestException as exc:
            print(f"Failed to send test message: {exc}", flush=True)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nNotification test stopped.", flush=True)
