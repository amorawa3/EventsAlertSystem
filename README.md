Got it ✅ — here’s the entire thing (everything from top to bottom) formatted as a single README.md file so you can copy and paste directly into your project without losing formatting.


---

# 🏟️ Events Alert System (EAS)

The **Events Alert System (EAS)** is a Python-based Discord bot that automatically sends daily game alerts for your favorite teams.
It’s designed to run continuously on a Raspberry Pi and start automatically when the system boots.

---

## ⚽ Features

- Sends **daily Discord alerts** for your favorite teams (Braves, Falcons, Hawks, Atlanta United, USMNT, Costa Rica, etc.)
- Pulls real-time data from **TheSportsDB API**
- Automatically sends:
  - **10 AM ET** → Today’s games  
  - **8 PM ET** → Tomorrow’s games
- Runs 24/7 using **systemd** for automatic startup
- Compatible with **Python 3.13**
- Uses a **Python virtual environment (venv)** for isolated dependencies
- Fully self-contained and portable — no global package changes

---

## 🧰 Requirements

- Raspberry Pi running Raspberry Pi OS (or any Debian-based Linux)
- Python **3.13+**
- Internet connection
- Discord application and bot token from the [Discord Developer Portal](https://discord.com/developers/applications)
- Discord channel ID where alerts should be posted

---

## ⚙️ Installation Guide

Follow these steps carefully to set up the bot from scratch.

---

### **1️⃣ Clone the repository**

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/EventsAlertSystem.git
cd EventsAlertSystem/events-alert-system


---

2️⃣ Create a Python virtual environment

A virtual environment isolates your project’s dependencies from system-wide Python packages.

python3 -m venv venv

This creates a folder called venv/ inside your project directory containing its own copy of Python and pip.


---

3️⃣ Activate the virtual environment

source venv/bin/activate

You should now see (venv) before your terminal prompt, meaning the venv is active.


---

4️⃣ Install dependencies

Install all required packages from the provided requirements.txt file:

pip install -r requirements.txt

Once complete, deactivate the environment:

deactivate


---

5️⃣ Verify the installation

You can manually start the script to ensure it runs correctly:

source venv/bin/activate
python events_alert_system.py

If no errors appear, press Ctrl + C to stop it, then deactivate:

deactivate


---

📦 requirements.txt

This file defines all packages needed by the bot.
It’s preconfigured for Python 3.13 compatibility.

discord.py>=2.4,<3
filetype
schedule
pytz
requests

Why these versions?

discord.py → Discord API client used for bot connectivity and messages.

filetype → replacement for deprecated imghdr

schedule, pytz, requests → used for scheduling, time zones, and API calls



---

💬 Discord Configuration

1. Create a bot application in the [Discord Developer Portal](https://discord.com/developers/applications).


2. Add a Bot user, copy its token, and keep it secret.


3. Enable the **Message Content Intent** under the bot's privileged gateway intents.


4. Set the required environment variables before starting the bot:

```bash
export DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN"
export DISCORD_CHANNEL_ID="YOUR_DISCORD_CHANNEL_ID"
```

Invite the bot to your server with the `bot` OAuth2 scope and permissions to view and send messages in the target channel. Enable Developer Mode in Discord to copy the channel ID.


---

🔁 Set Up Automatic Startup with systemd

This ensures the bot starts automatically when your Raspberry Pi boots.


---

1️⃣ Create a systemd service file

sudo nano /etc/systemd/system/events-alert.service

Paste this configuration:

[Unit]
Description=Events Alert System
After=network.target

[Service]
Type=simple
User=amorawa3
WorkingDirectory=/home/amorawa3/EventsAlertSystem/events-alert-system
ExecStart=/home/amorawa3/EventsAlertSystem/events-alert-system/venv/bin/python /home/amorawa3/EventsAlertSystem/events-alert-system/events_alert_system.py
Restart=always

[Install]
WantedBy=multi-user.target

> ⚠️ Adjust the username (amorawa3) and paths if your directory differs.




---

2️⃣ Enable and start the service

Reload systemd to recognize the new service:

sudo systemctl daemon-reload
sudo systemctl enable events-alert.service
sudo systemctl start events-alert.service


---

3️⃣ Check service status

To verify the bot is running:

sudo systemctl status events-alert.service

You should see a green “active (running)” status.


---

4️⃣ View real-time logs

journalctl -u events-alert.service -f

To stop or restart the service:

sudo systemctl stop events-alert.service
sudo systemctl restart events-alert.service


---

🧩 How the Virtual Environment Works

The venv is a self-contained sandbox containing its own Python and libraries.

ExecStart in the systemd file directly points to your venv’s Python binary.

You never need to manually “activate” the venv for the service — systemd handles it automatically.


This setup ensures:

No interference with system Python packages.

Predictable, stable operation even after OS or Python updates.



---

🔄 Updating the Bot or Dependencies

If you modify the code or update dependencies:

cd ~/EventsAlertSystem/events-alert-system
source venv/bin/activate
pip install -r requirements.txt --upgrade
deactivate
sudo systemctl restart events-alert.service


---

🩵 Troubleshooting

Problem	Cause	Fix

No module named imghdr	Python 3.13 removed imghdr	Fixed via filetype dependency
Discord bot does not connect	Invalid token or missing Message Content Intent	Check the Discord Developer Portal settings and environment variable
Discord bot cannot send	Incorrect channel ID or missing permissions	Verify the channel ID and grant View Channel and Send Messages
Service won’t start	Wrong path in systemd file	Double-check paths and username



---

🧠 Developer Notes

The system runs two daily checks:

10 AM ET → today’s games

8 PM ET → tomorrow’s games


Built around schedule and pytz for reliable timing.

Game data is fetched from TheSportsDB.

Discord messages are sent via discord.py API calls.



---

🧰 Commands Summary

Command	Description

source venv/bin/activate	Activate the virtual environment
deactivate	Exit the virtual environment
pip install -r requirements.txt	Install all dependencies
sudo systemctl restart events-alert.service	Restart the bot service
journalctl -u events-alert.service -f	View live logs



---

🩵 Credits

Created and maintained by Andrew Morawa
Designed to provide automated daily sports alerts for:

Atlanta Braves ⚾

Atlanta Hawks 🏀

Atlanta Falcons 🏈

Atlanta United ⚽

USMNT 🇺🇸

Costa Rica National Team 🇨🇷



---

📄 License

This project is open-source and free to use under the MIT License.

---

✅ You can now copy **everything above** into your file  
`~/EventsAlertSystem/events-alert-system/README.md`  

Would you like me to also include a small ready-to-copy `events-alert.service` file and a `requirements-freeze.txt` (based on the exact versions currently installed in your venv) to ensure perfect reproducibility if you ever reinstall?
