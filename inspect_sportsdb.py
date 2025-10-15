import requests
import json

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

for team_key, team_id in TEAM_IDS.items():
    url = f"https://www.thesportsdb.com/api/v1/json/123/eventsnext.php?id={team_id}"
    print(f"\n=== {team_key} ===")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        events = data.get("events", [])
        if not events:
            print("No events found.")
            continue

        # Print the first event pretty-formatted
        print(json.dumps(events[0], indent=2))
    except Exception as e:
        print(f"Error fetching {team_key}: {e}")
