# CLAUDE.md — Corridor プロジェクト

Claude Code がこのリポジトリで作業するためのガイド。

## このプロジェクトは何か

ベトナム史を題材にした**縦型ショートアニメ**を、**Seedance（動画生成AI）**で制作・配信する事業
「Corridor」。DramaBox 型（数話無料→課金）のモデルを、AI生成のオリジナルアニメで展開する。
背景・戦略は `docs/` を参照（まず `docs/roadmap.md` の意思決定ログを読むこと）。

## ドキュメントの地図

- `docs/market-research.md` — 市場・競合・権利の調査
- `docs/roadmap.md` — フェーズ別計画と**意思決定ログ（最重要・常に最新化する）**
- `docs/content/vietnam-concept.md` — 第1作の企画
- `docs/content/character-design.md` — キャラ設定（Seedance参照プロンプト）
- `docs/content/vietnam-ep01-script.md` — 第1話の脚本（ショットリスト）
- `pipeline/` — 制作自動化パイプライン（下記）

## 制作自動化の方針（Claude Code が担う中核）

最終的に Claude Code が制作の大部分を回せる状態を目指す。標準フローは:

1. **脚本を書く**: `docs/content/<series>-epNN-script.md` にショットリスト形式で執筆。
2. **構造化スペックに変換**: 脚本を `pipeline/episodes/epNN.json` に落とす
   （`mode`/`characters`/`duration`/`prompt` 等。書式は `pipeline/README.md`）。
3. **新キャラがいれば** `pipeline/characters.json` に参照プロンプトを追加。
4. **ドライランで検証**: `python3 pipeline/generate.py --episode pipeline/episodes/epNN.json --provider mock`
   → `output/<ep>/manifest.json` と `*.request.json` でプロンプト/参照/尺をレビュー。
5. **本番生成**: `--provider fal`（要 `pipeline/.env`）。`--only` でショット単位リテイク。
6. **意思決定ログを更新**: 変更点を `docs/roadmap.md` に追記。

### 「第◯話を作って」と言われたら
上記 1→6 を実行する。まず脚本（戦い重視・毎話クリフハンガー・60〜90秒）を書き、
ユーザーに方向性を確認してから JSON 化・ドライランまで進める。実APIの本番生成は
キー設定とコストが絡むため、ユーザーの明示的な合意を取ってから行う。

## 守るべき制作ルール

- **ビジュアル**: 日本TVアニメ調・**顔は日本人寄り**、衣装/世界観は13世紀大越。
- **トーン**: 戦い重視（バトル7：恋愛3）。恋愛は戦いに絡める従属軸。
- **史実の扱い**: 史実ベース＋デフォルメ。国民的英雄（陳興道など）は敬意をもって描き、
  脚色・恋愛・ギャグは架空キャラ（ヒロイン マイ等）や仲間に厚く乗せる。
- **キャラ一貫性**: 参照画像を先に固定し i2v で生成。`characters.json` を唯一の正とする。

## 約束事

- `.env` と `pipeline/output/` はコミットしない（`.gitignore` 済み）。
- 秘密情報・APIキーをコード/ドキュメント/コミットに残さない。
- 作業ブランチ: `claude/anime-streaming-app-jp-m66hea`。
