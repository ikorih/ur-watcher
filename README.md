# UR Vacancy Watcher (GitHub Actions + LINE Messaging API)

- 10分おきに対象URLをクロールし、指定キーワードの **出現**／**消滅** を検知して LINE に通知します。
- 通知先は LINE Webhook 経由で自動収集（Gist `recipients.json`）します。
- 前回状態は Gist `state.json` に保存し、差分のみ通知します。

## 構成

- 監視（GitHub Actions）: `.github/workflows/watch.yml`
- 設定（監視対象・キーワード）: `targets.yaml`
- ロジック: `main.py`
- Gist I/O: `gist_state.py`
- 受信者自動収集（LINE Webhook 受け口・さくらサーバー向け）: `webhook-sakura/webhook.php`, `.htaccess`

## 事前準備

1. **Gist（Secret）** を作成
   - `state.json` → `{}`
   - `recipients.json` → `[]`
   - **Gist ID** を控える。
2. **PAT (Fine-grained)** を発行
   - _User permissions → Gists: Read and write_
   - これを `GIST_TOKEN` として使用。
3. **LINE Developers**
   - Messaging API チャネル作成
   - **チャネルアクセストークン（長期）** と **チャネルシークレット** を控える。

## さくらのレンタルサーバーに Webhook を設置

- `webhook-sakura/` の2ファイルを公開ディレクトリへアップ（例 `/www/line-webhook/`）
- `.htaccess` の `SetEnv` をあなたの値に書き換え
- LINE の **Webhook URL** に `https://<your-domain>/line-webhook/webhook.php`
- Webhook「接続確認」→ `Success`

### 動作

- 友だち追加 or 初回メッセージ で `userId` を Gist の `recipients.json` に追記
- 登録者へ「登録ありがとうございます…」と1回 Push

## GitHub Secrets（リポジトリの Settings → Secrets and variables → Actions）

- `GIST_ID` … Secret Gist の ID
- `GIST_TOKEN` … 上記 PAT（Gists: read/write）
- `LINE_CHANNEL_ACCESS_TOKEN` … LINE チャネルアクセストークン（長期）

> 受信者IDは毎回 Gist `recipients.json` を読み込みます（SecretsにIDを入れる必要はありません）。

## 監視対象の設定

- `targets.yaml` を編集（複数URL可、キーワードは配列）
- `appear_keywords` … **出現したら通知**
- `vanish_keywords` … **消えたら通知**
- `scope_selector` … ページ内の特定範囲だけを対象にしたい場合に CSS セレクタで指定（空なら全体）

## 手動テスト

- GitHub の Actions → ワークフロー → **Run workflow**
- 通知が届けばOK。10分ごとの定期実行は自動で動きます（UTC基準）。

## 注意

- サイト規約と robots.txt を厳守し、過度のリクエストは避けてください。
- LINEの無料枠・レート制限に留意してください（本スクリプトは少人数・低頻度想定）。
