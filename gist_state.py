import json
import os
import requests

GIST_TOKEN = os.environ["GIST_TOKEN"]
GIST_ID = os.environ["GIST_ID"]

API_URL = f"https://api.github.com/gists/{GIST_ID}"
HEADERS = {
    "Authorization": f"token {GIST_TOKEN}",
    "Accept": "application/vnd.github+json",
}

FILENAME = "state.json"

def load_state() -> dict:
    r = requests.get(API_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    files = r.json().get("files", {})
    content = files.get(FILENAME, {}).get("content", "{}")
    try:
        return json.loads(content)
    except:
        return {}

def save_state(state: dict):
    data = {
        "files": {
            FILENAME: {
                "content": json.dumps(state, ensure_ascii=False, indent=2)
            }
        }
    }
    r = requests.patch(API_URL, headers=HEADERS, json=data, timeout=20)
    r.raise_for_status()
