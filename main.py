import os
import time
import random
import hashlib
import requests
import yaml
from bs4 import BeautifulSoup
from gist_state import load_state, save_state

UA = "Mozilla/5.0 (compatible; ur-vacancy-watcher/1.0)"

def jitter_sleep():
    # 10分ジョブでもアクセス集中を避けるため±30〜60秒程度の待機
    sec = random.randint(15, 60)
    time.sleep(sec)

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

def check_keywords(text: str, keywords: list[str]) -> dict:
    found = {}
    lower = text.lower()
    for kw in keywords or []:
        if kw.lower() in lower:
            found[kw] = True
        else:
            found[kw] = False
    return found

def line_notify(message: str):
    tokens = os.environ.get("LINE_NOTIFY_TOKENS", "")
    tokens = [t.strip() for t in tokens.split(",") if t.strip()]
    if not tokens:
        print("[WARN] LINE_NOTIFY_TOKENS is empty")
        return
    for tok in tokens:
        try:
            requests.post(
                "https://notify-api.line.me/api/notify",
                headers={"Authorization": f"Bearer {tok}"},
                data={"message": message},
                timeout=20
            )
        except Exception as e:
            print(f"[ERROR] LINE notify failed for a token: {e}")

def main():
    jitter_sleep()

    with open("targets.yaml", "r", encoding="utf-8") as f:
        targets = yaml.safe_load(f)

    state = load_state()  # { target_key: { "appear":{kw:bool}, "vanish":{kw:bool} } }

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

        # 出現検知: 前回 False → 今回 True
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

        # 状態更新（次回比較用）
        state[key] = {
            "appear": cur_appear,
            "vanish": cur_vanish,
        }

    # 保存＆通知
    save_state(state)

    if notifications:
        # 1通にまとめて送信（スパム防止）
        body = f"監視結果（{time.strftime('%Y-%m-%d %H:%M:%S')}）\n\n" + "\n\n".join(notifications)
        line_notify(body)
    else:
        print("[INFO] No changes.")

if __name__ == "__main__":
    main()
