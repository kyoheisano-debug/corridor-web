# corridor-web

日本アニメ版ショートドラマ事業(プロジェクト「Corridor」)の管理ウェブ／ドキュメント基盤リポジトリ。

DramaBox 型の縦型ショートドラマモデルを、**日本のアニメクオリティ**で展開することを目指す事業の、
戦略・調査・管理ツールを集約する。

## 事業の4つの軸

1. アプリケーション（視聴者向け iOS / Android）
2. 管理ウェブ（コンテンツ・課金・ユーザー管理）← 本リポジトリの将来の主目的
3. アニメ動画の制作（小説・各国の歴史を題材にしたショートアニメ）
4. SNS マーケティング導線（TikTok / Instagram Reels → 数話無料 → 課金）

## 進め方（合意済みの方針）

- **需要検証ファースト**: アプリ・管理ウェブの本格開発前に、パイロット作品を SNS で検証する
- **制作手法**: AI + 人手のハイブリッド（コストと品質のバランス型）
- 詳細は [`docs/`](./docs/) を参照

## ドキュメント

- [`docs/market-research.md`](./docs/market-research.md) — 市場・競合・権利の調査レポート（2026-06 時点）
- [`docs/roadmap.md`](./docs/roadmap.md) — フェーズ別ロードマップと意思決定ログ
- [`docs/content/vietnam-concept.md`](./docs/content/vietnam-concept.md) — 第1作 企画（ベトナム史シリーズ）
- [`docs/content/vietnam-season1-arc.md`](./docs/content/vietnam-season1-arc.md) — シーズン1 全体構成（無料→課金の流れ）
- [`docs/content/character-design.md`](./docs/content/character-design.md) — キャラ設定 & ビジュアルバイブル（Seedanceプロンプト付き）
- [`docs/content/vietnam-ep01-script.md`](./docs/content/vietnam-ep01-script.md) — 第1話 脚本「握り潰したミカン」（ショットリスト）
- [`docs/content/vietnam-ep02-script.md`](./docs/content/vietnam-ep02-script.md) — 第2話 脚本「初陣」
- [`docs/content/vietnam-ep03-script.md`](./docs/content/vietnam-ep03-script.md) — 第3話 脚本「焦土」

## 制作パイプライン

- [`pipeline/`](./pipeline/) — 脚本(JSON) → Seedance で動画を自動生成するパイプライン（キー不要のドライラン付き）。手順は [`pipeline/README.md`](./pipeline/README.md)
- [`CLAUDE.md`](./CLAUDE.md) — Claude Code で制作を自動化するためのガイド
