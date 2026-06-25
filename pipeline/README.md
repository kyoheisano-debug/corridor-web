# Corridor 制作パイプライン（Seedance 自動化）

脚本の構造化スペック（`episodes/*.json`）から、Seedance でショットごとの動画を
自動生成するパイプライン。**キャラ参照画像を先に固定 → image-to-video** で
キャラ一貫性を担保する。Claude Code が将来「第◯話を生成して」で回せる構造。

## 構成

```
pipeline/
├── characters.json        # スタイルトークン + 各キャラの参照画像プロンプト（唯一の正）
├── episodes/ep01.json     # 第1話の構造化スペック（S1〜S9のショット）
├── providers.py           # 生成プロバイダ（mock / fal / kie）
├── generate.py            # オーケストレータ（CLI）
├── .env.example           # APIキーのテンプレ（.env にコピーして記入）
└── output/                # 生成物（gitignore。manifest.json / refs / clips）
```

## クイックスタート（キー不要・ドライラン）

```bash
cd pipeline
python3 generate.py --episode episodes/ep01.json --provider mock
```

`output/ep01/` に各ショットのプレースホルダと、**実際にAPIへ送る payload（`*.request.json`）**、
全体の `manifest.json` が出力される。**プロンプト・参照画像の紐付け・尺をキー消費ゼロでレビュー**できる。

## 本番生成（seedance2.ai 経由＝本プロジェクトの契約先）

```bash
cd pipeline
cp .env.example .env         # SEEDANCE2_API_KEY に sk_live_... を記入
set -a; . ./.env; set +a     # .env を環境変数に読み込む
python3 generate.py --episode episodes/ep01.json --provider seedance2
```

- 標準ライブラリのみで動作（`requests` 不要）。Bearer 認証・非同期タスク（作成→ポーリング）に対応。
- 既定値は **実 API（seedance2.ai）で疎通確認済み**。差異があれば `.env` の
  `SEEDANCE2_*` で上書き可能（コード改修不要）。下記「seedance2.ai の設定」参照。
- image-to-video の参照画像は既定で **base64 で埋め込み**。APIがURL指定なら `SEEDANCE2_IMAGE_AS_URL=1`。
- 価格感: Seedance は概ね **$0.10/秒前後**。5話計約409秒 → 1パス$40前後。リテイクを見込む。
- **ネットワーク要件**: API は `seedance2.ai`、生成物の配信は `cdn.seedance2.ai`。
  egress 制限のある環境では **両ホストを許可**すること（CDN が塞がれると生成は成功するが
  ダウンロードのみ失敗し、エラーに動画 URL を残す）。

### seedance2.ai の設定（疎通確認済みの実値）

| .env キー | 既定値 | 備考 |
|---|---|---|
| `SEEDANCE2_BASE_URL` | `https://seedance2.ai/api` | API は `/api` プレフィックス配下 |
| `SEEDANCE2_VIDEO_CREATE` | `/v1/videos/generations` | 動画タスク作成の POST パス |
| `SEEDANCE2_IMAGE_CREATE` | `/v1/images/generations` | 画像タスク作成の POST パス |
| `SEEDANCE2_TASK_STATUS` | `/v1/tasks` | 進捗ポーリング（`GET /v1/tasks/{id}`、作成パスとは別系統） |
| `SEEDANCE2_VIDEO_MODEL` | `seedance-2-0` | 動画モデル名（`seedance-2-0-fast` も可） |
| `SEEDANCE2_IMAGE_MODEL` | `seedance-2-0-image` | 画像モデル名 |
| `SEEDANCE2_USER_AGENT` | `corridor-pipeline/1.0` | Cloudflare が `Python-urllib/*` を 403 で弾くため明示指定 |

実 API の形状: 作成 → `{"taskId": "...", "credits": N}` / ポーリング →
`{"status": "completed", "data": {"results": ["https://cdn.seedance2.ai/...mp4"]}}`。
`duration` は **4〜15 の整数**。これらは `_dig` の候補に含めてある。

## よく使うオプション

```bash
# 特定ショットだけ再生成（プロンプト調整のリテイク）
python3 generate.py --episode episodes/ep01.json --provider fal --only S6 S9

# キャラ参照画像をキャッシュ再利用（毎回作り直さない）
python3 generate.py --episode episodes/ep01.json --provider fal --skip-refs
```

## 制作ワークフロー（フェーズ0）

1. `characters.json` のプロンプトで**参照画像を生成・確定**（破綻なくキャラが立つまで調整）。
2. `--skip-refs` で参照を固定したまま、ショットを生成。
3. ショット単位で `--only` を使い、気に入るまでリテイク。
4. 採用クリップを編集・音入れ（ffmpeg等。結合工程は今後 `assemble.py` を追加予定）。
5. 60秒前後のSNS版に再構成 → TikTok/Reels へ投稿し反応を計測（フェーズ0 KPI）。

## スペックの書き方（episodes/*.json）

| フィールド | 意味 |
|---|---|
| `mode` | `t2v`（テキスト→動画）/ `i2v`（参照画像→動画。キャラ一貫性用） |
| `characters` | 登場キャラID（先頭が i2v の参照画像に使われる primary） |
| `duration` | ショット尺（秒） |
| `prompt` | 英語のショット記述（先頭にスタイルトークンが自動付与される） |
| `dialogue` / `narration` / `caption` | 音声・テロップ用テキスト（生成には未使用、編集工程で使用） |

## プロバイダの追加

`providers.py` の `VideoProvider` を継承し、`generate_image` / `generate_video` を実装して
`PROVIDERS` に登録するだけ。オーケストレータ側は無改修。
`KieProvider` は雛形（実装待ち）、`VolcengineProvider` は公式API用の差し込み口。

## 注意

- `.env` と `output/` は**コミットしない**（`.gitignore` 済み）。
- Seedance の商用利用・著作権の規約を確認のうえ運用すること（権利方針は `docs/roadmap.md` 参照）。
