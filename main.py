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
    # 同時刻に集中しないよう、15〜60秒のランダム待機
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
    # 予備の手動指定（カンマ区切り）も合成可能
    extra = [u.strip() for u in os.environ.get("LINE_USER_IDS", "").split(",") if u.strip()]
    # 順序を保った重複排除
    return list(dict.fromkeys(ids + extra))

def build_notifications(targets: List[dict]) -> Tuple[List[str], dict]:
    """
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
        prev = state.get(key, {"appear": {}, "vanish": {}})

        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"[ERROR] fetch failed: {name} {url} -> {e}")
            continue

        html_scoped = scope_html(html, selector)
        text = BeautifulSoup(html_scoped, "html.parser").get_text(" ", strip=True)

        cur_appear = check_keywords(text, appear)  # {kw:bool}
        cur_vanish = check_keywords(text, vanish)  # {kw:bool}

        # 出現検知: 前回 False or 未登録 → 今回 True
        appeared = [kw for kw, ok in cur_appear.items() if ok and (prev["appear"].get(kw) is False or kw not in prev["appear"])]
        # 消滅検知: 前回 True → 今回 False
        vanished = [kw for kw, ok in cur_vanish.items() if (prev["vanish"].get(kw) is True) and not ok]

        if appeared or vanished:
            lines = [f"【変化検知】{name}", url]
            if appeared:
                lines.append("▼ 出現したキーワード")
                lines += [f"- {kw}" for kw in appeared]
            if vanished:
                lines.append("▼ 消えたキーワード")
                lines += [f"- {kw}" for kw in vanished]
            notifications.append("\n".join(lines))

        # 状態更新
        state[key] = {"appear": cur_appear, "vanish": cur_vanish}

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
