import os
import time
import random
import hashlib
import requests
import yaml
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple

from gist_state import load_state, save_state, load_json_file

UA = "Mozilla/5.0 (compatible; ur-vacancy-watcher/1.0)"

def jitter_sleep():
    # 実行が重ならないように15〜60秒のランダム待機
    time.sleep(random.randint(15, 60))

def fetch_html(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text

def scope_html(html: str, selector: str | None) -> str:
    if not selector:
        return html
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(selector)
    return str(node) if node else html

def check_keywords(text: str, keywords: List[str]) -> Dict[str, bool]:
    found = {}
    lower = text.lower()
    for kw in keywords or []:
        found[kw] = kw.lower() in lower
    return found

def decide_availability(cur_appear: dict, cur_vanish: dict) -> bool:
    """
    True: 空きあり, False: 満室
    ルール:
      - appear キーワードのどれかが出ていれば「空きあり」
      - vanish キーワードが1つも見つからなければ「空きあり」
      - vanish キーワードのどれかが見つかれば「満室」
    """
    any_appear = any(cur_appear.values()) if cur_appear else False
    any_vanish_present = any(cur_vanish.values()) if cur_vanish else False
    if any_appear:
        return True
    if cur_vanish and not any_vanish_present:
        return True
    return False

def line_push_to(access_token: str, user_id: str, message: str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    r = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        json=body,
        timeout=20,
    )
    if r.status_code >= 300:
        print(f"[ERROR] LINE push failed ({user_id}): {r.status_code} {r.text}")

def get_recipients() -> List[str]:
    ids = load_json_file("recipients.json", [])
    extra = [u.strip() for u in os.environ.get("LINE_USER_IDS", "").split(",") if u.strip()]
    return list(dict.fromkeys(ids + extra))  # 重複除去

def build_notifications(targets: List[dict]) -> Tuple[List[str], dict]:
    """
    状態が変わった建物だけ通知する。
    returns (notifications, new_state)
    """
    state = load_state()
    notifications = []

    for t in targets:
        name = t["name"]
        url = t["url"]
        selector = t.get("scope_selector") or ""
        appear = t.get("appear_keywords") or []
        vanish = t.get("vanish_keywords") or []

        key = hashlib.sha1((name + "|" + url).encode("utf-8")).hexdigest()[:16]
        prev = state.get(key, {"appear": {}, "vanish": {}, "status": None})

        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"[ERROR] fetch failed: {name} {url} -> {e}")
            continue

        html_scoped = scope_html(html, selector)
        text = BeautifulSoup(html_scoped, "html.parser").get_text(" ", strip=True)

        cur_appear = check_keywords(text, appear)  # {kw:bool}
        cur_vanish = check_keywords(text, vanish)  # {kw:bool}

        # 現在の可用状態を判定
        available_now = decide_availability(cur_appear, cur_vanish)
        prev_status = prev.get("status")

        # 状態が変わった時だけ通知
        if prev_status is not None and (prev_status is not available_now):
            if available_now:
                # 空きが出た
                lines = [f"【空きが出ました】{name}", url]
            else:
                # 満室に戻った
                lines = [f"【満室に戻りました】{name}", url]
            notifications.append("\n".join(lines))

        # 状態更新（次回比較用）
        state[key] = {
            "appear": cur_appear,
            "vanish": cur_vanish,
            "status": available_now,
        }

    return notifications, state

def main():
    jitter_sleep()

    with open("targets.yaml", "r", encoding="utf-8") as f:
        targets = yaml.safe_load(f)

    notifications, new_state = build_notifications(targets)

    # 保存（次回比較用）
    save_state(new_state)

    if notifications:
        body = f"監視結果（{time.strftime('%Y-%m-%d %H:%M:%S')}）\n\n" + "\n\n".join(notifications)
        access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
        recipients = get_recipients()
        if not access_token or not recipients:
            print("[WARN] Missing LINE token or no recipients; skip notify.")
            return
        for uid in recipients:
            line_push_to(access_token, uid, body)
    else:
        print("[INFO] No changes.")

if __name__ == "__main__":
    main()
