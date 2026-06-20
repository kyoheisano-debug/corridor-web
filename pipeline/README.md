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
- **要確認**: エンドポイント/フィールド名は `https://seedance2.ai/api-docs`（要ログイン）の仕様に
  合わせて `providers.py` のデフォルトを置いている。差異があれば `.env` の
  `SEEDANCE2_*` で上書き可能（コード改修不要）。下記「seedance2.ai の設定確認」参照。
- image-to-video の参照画像は既定で **base64 で埋め込み**。APIがURL指定なら `SEEDANCE2_IMAGE_AS_URL=1`。
- 価格感: Seedance は概ね **$0.10/秒前後**。5話計約409秒 → 1パス$40前後。リテイクを見込む。

### seedance2.ai の設定確認（最初の1回）
api-docs を見て、実際の値と次の既定が合っているか確認する:

| .env キー | 既定値 | 確認ポイント |
|---|---|---|
| `SEEDANCE2_VIDEO_CREATE` | `/v1/videos/generations` | 動画タスク作成の POST パス |
| `SEEDANCE2_IMAGE_CREATE` | `/v1/images/generations` | 画像タスク作成の POST パス |
| `SEEDANCE2_VIDEO_MODEL` | `seedance-2.0` | 動画モデル名 |
| `SEEDANCE2_IMAGE_MODEL` | `seedance-2.0-image` | 画像モデル名 |

レスポンスの task id / video url のフィールド名は複数候補を自動探索する実装（`_dig`）。
それでも拾えない場合はエラーに「check field mapping」と出るので、api-docs の実フィールドを共有のこと。

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
