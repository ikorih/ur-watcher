import json
import os
import requests

GIST_TOKEN = os.environ["GIST_TOKEN"]
GIST_ID = os.environ["GIST_ID"]

API_URL = f"https://api.github.com/gists/{GIST_ID}"
HEADERS = {
    "Authorization": f"Bearer {GIST_TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "ur-vacancy-watcher",
}

def _get_gist_json():
    r = requests.get(API_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

def load_json_file(filename: str, default):
    data = _get_gist_json()
    files = data.get("files", {})
    content = files.get(filename, {}).get("content", None)
    if content is None:
        return default
    try:
        return json.loads(content)
    except Exception:
        return default

def save_json_file(filename: str, data):
    payload = {
        "files": {
            filename: {
                "content": json.dumps(data, ensure_ascii=False, indent=2)
            }
        }
    }
    r = requests.patch(API_URL, headers=HEADERS, json=payload, timeout=20)
    r.raise_for_status()

# state.json（監視の前回状態）
def load_state() -> dict:
    return load_json_file("state.json", {})

def save_state(state: dict):
    save_json_file("state.json", state)
