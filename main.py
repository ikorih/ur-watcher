import os
import time
import random
import hashlib
import requests
import yaml
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional

from gist_state import load_state, save_state, load_json_file

UA = "Mozilla/5.0 (compatible; ur-vacancy-watcher/1.0)"

def jitter_sleep():
    # 実行が重ならないように15〜60秒のランダム待機
    time.sleep(random.randint(15, 60))

def fetch_html_requests(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.text

def fetch_visible_text_playwright(url: str, selector: Optional[str]) -> str:
    # Playwright で可視テキストを取得（innerText）
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(user_agent=UA, viewport={"width":1200, "height":1600})
        page = ctx.new_page()
        page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        # 追加の待機（リクエスト完了やレンダリング終了を少し待つ）
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except:
            pass
        if selector:
            # セレクタが存在しない場合は body を fallback
            loc = page.locator(selector)
            if loc.count() > 0:
                text = loc.first.inner_text(timeout=10_000)
            else:
                text = page.locator("body").inner_text(timeout=10_000)
        else:
            text = page.locator("body").inner_text(timeout=10_000)
        browser.close()
        return text

def fetch_page_text(url: str, selector: Optional[str], engine: str) -> str:
    """
    engine: "requests" | "playwright"
    - requests: HTMLからテキスト抽出（JS未対応）
    - playwright: JS実行後の可視テキストで判定
    """
    if engine == "playwright":
        return fetch_visible_text_playwright(url, selector)
    # requests 経路はこれまで通り
    html = fetch_html_requests(url)
    if selector:
        soup = BeautifulSoup(html, "html.parser")
        node = soup.select_one(selector)
        html = str(node) if node else html
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

def check_keywords(text: str, keywords: List[str]) -> Dict[str, bool]:
    found = {}
    lower = text.lower()
    for kw in keywords or []:
        found[kw] = kw.lower() in lower
    return found

def decide_availability(cur_appear: dict, cur_vanish: dict):
    """
    return: True(空きあり) / False(満室) / None(判断不能)
    ルール:
      - appear のどれか True → True
      - vanish のどれか True → False
      - どちらもヒットなし → None（前回状態を維持）
    """
    if cur_appear and any(cur_appear.values()):
        return True
    if cur_vanish and any(cur_vanish.values()):
        return False
    return None

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
    # 順序を保った重複排除
    return list(dict.fromkeys(ids + extra))

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
        engine = (t.get("engine") or "requests").lower()

        key = hashlib.sha1((name + "|" + url).encode("utf-8")).hexdigest()[:16]
        prev = state.get(key, {"appear": {}, "vanish": {}, "status": None})

        try:
            text = fetch_page_text(url, selector, engine)
        except Exception as e:
            print(f"[ERROR] fetch failed: {name} {url} -> {e}")
            continue

        cur_appear = check_keywords(text, appear)   # {kw: bool}
        cur_vanish = check_keywords(text, vanish)   # {kw: bool}

        decision = decide_availability(cur_appear, cur_vanish)
        prev_status = prev.get("status")

        # 未知(None)のときは前回状態を維持し、通知もしない
        available_now = prev_status if decision is None else decision

        # 状態が変わった時だけ通知（prev_status が None の初回は通知しない）
        if (prev_status is not None) and (available_now is not None) and (prev_status is not available_now):
            if available_now:
                lines = [f"【空きが出ました】{name}", url]
            else:
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
