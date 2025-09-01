# UR Vacancy Watcher (GitHub Actions + LINE Messaging API)

- **20分おき**に対象URLをクロールし、指定キーワードから **空きあり/満室** を判定します。
- 判定は **状態トグル型通知**：
  - 「満室 → 空きあり」になった時に通知
  - 「空きあり → 満室」に戻った時に通知
  - 状態が変わらない限り通知しない（月200通の無料枠節約）
- 通知先は LINE Webhook で自動収集（Gist `recipients.json`）。
- 前回状態は Gist `state.json` に保存。

## 構成

- 監視（GitHub Actions）: `.github/workflows/watch.yml`
- 設定（監視対象・キーワード）: `targets.yaml`
- ロジック: `main.py`
- Gist I/O: `gist_state.py`
- 受信者自動収集（さくらレンタルサーバー向け Webhook）: `webhook-sakura/webhook.php`, `.htaccess`

## 事前準備（要点）

1. **Gist（Secret）** を用意
   - `state.json` → `{}` / `recipients.json` → `[]` を置く
   - **Gist ID** を控える
2. **PAT (Fine-grained)** 発行
   - User permissions → **Gists: Read and write**
3. **LINE Developers**
   - Messaging API チャネル作成
   - **チャネルアクセストークン（長期）** と **チャネルシークレット**
4. **Webhook（さくら）**
   - `webhook-sakura/` を公開ディレクトリへアップ
   - `.htaccess` の `SetEnv` を自分の値に置換
   - Webhook URL を LINE の設定に登録 → 接続確認

## GitHub Secrets（Repo Settings → Secrets and variables → Actions）

- `GIST_ID` … Secret Gist の ID
- `GIST_TOKEN` … 上記 PAT（Gists: read/write）
- `LINE_CHANNEL_ACCESS_TOKEN` … LINE チャネルアクセストークン（長期）

> 受信者IDは毎回 Gist `recipients.json` を読み込みます（SecretsにIDは不要）。

## 監視対象の設定

- `targets.yaml` を編集（複数URL可）
- `appear_keywords` … **出現したら空きあり**
- `vanish_keywords` … **消滅したら空きあり**（=「満室文言が消えた」）
- `scope_selector` … CSSセレクタで監視範囲を限定（今回 `#list`）

## 手動テスト

- Actions → ワークフロー → **Run workflow**
- 受信者2名がボットに一言送信し、`recipients.json` にIDが入っていることを確認

## 注意

- サイト規約・robots.txtを遵守し、アクセス間隔は控えめ（本設定は20分おき＋ランダム待機）。
- LINE無料枠（月200通）は **状態変化時のみ通知**で節約。
