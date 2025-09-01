# 受信者（recipients.json）を読み、全員にテスト通知を送る単体テスト
import os, json, requests
from gist_state import load_json_file

def get_recipients():
    ids = load_json_file("recipients.json", [])
    extra = [u.strip() for u in os.environ.get("LINE_USER_IDS","").split(",") if u.strip()]
    return list(dict.fromkeys(ids + extra))

def line_push_to(access_token: str, user_id: str, message: str):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    body = {"to": user_id, "messages": [{"type": "text", "text": message}]}
    r = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=body, timeout=20)
    print(f"[DEBUG] push -> {user_id} status={r.status_code}")
    if r.status_code >= 300:
        print("[DEBUG] resp:", r.text)

def main():
    access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN","")
    if not access_token:
        print("[ERROR] LINE_CHANNEL_ACCESS_TOKEN missing"); return
    recips = get_recipients()
    print(f"[DEBUG] recipients: {len(recips)} -> {recips}")
    if not recips:
        print("[ERROR] no recipients in recipients.json"); return
    for uid in recips:
        line_push_to(access_token, uid, "［テスト通知］UR監視のPush送信テストです。")

if __name__ == "__main__":
    main()
