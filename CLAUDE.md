# こえかけ — 避難所内 情報共有掲示板

## 何を作っているか

千葉県のオープンデータ活用ハッカソン向けのMVP。開発者は1名（チームメンバーは非アクティブ）。
市原市の避難所を想定し、**外部インターネットが落ちても避難所内のローカルWi-Fiだけで動く**
避難者どうしの掲示板を作る。原点は令和元年房総半島台風での開発者自身の避難体験。

行政の防災ポータル（トップダウン型）が拾えない、避難所内のミクロな共助
（物資のSOS、子育て、体調不良）をカバーするのが目的。

## 主張の3本柱

1. 通信が途絶した状況で唯一動く
2. 通信が生きていても「この避難所にいる人だけに届く経路」は存在しない
   （LINEは相手を知らないと送れない／Xは世界中に流れる）
3. 行政の一方向配信では個人の困りごとが拾われない

## 技術構成

- Python 3.11 + Flask + gunicorn
- SQLite（`/data/koekake.db`、Docker名前付きボリュームで永続化）
- 素のHTML/CSS/JS（**外部CDN・Webフォント一切なし**）
- Docker単一コンテナ

起動:
```bash
docker compose run --rm --service-ports flask
```
`--service-ports` がないとポートが公開されない。

ワンショット実行:
```bash
docker compose run --rm flask python seed.py
```

## ディレクトリ

```
koekake-app/
├─ compose.yaml
├─ Dockerfile
├─ requirements.txt      # Flask, gunicorn のみ
└─ app/
    ├─ main.py
    ├─ schema.sql
    ├─ import_shelters.py   # CSV取り込み
    ├─ seed.py              # デモ用初期データ
    ├─ reset_posts.py       # 投稿全削除
    ├─ set_shelter.py       # アクティブ避難所の切替
    ├─ set_disaster.py      # 災害種別の設定
    ├─ hinan-list.csv       # 千葉県 指定緊急避難場所
    ├─ templates/index.html
    └─ static/
        ├─ style.css
        └─ app.js
```

`static/` は `templates/` の中ではなく `main.py` と同階層。

## DBスキーマ

**posts** — 投稿と返信を1テーブルで持つ（`parent_id` が NULL なら親）
`id / parent_id / category / body / author_name / location / author_token /
is_admin / is_resolved / resolved_at / is_pinned / is_deleted / post_at`

- `category`: `sos` / `health` / `child` / `info`
- `author_token`: localStorage の UUID。**認証の代わり**。自分の投稿だけ解決できる
- `is_deleted`: 論理削除。物理削除はしない（誤削除の復旧、デマ対応の記録）
- `post_at`: TEXT の ISO8601。`datetime('now','localtime')`

**shelters** — オープンデータ由来
`id / name / address / prefecture / city / capacity / disaster_*×8 / is_active`

災害種別8カラムはCSVの列をそのまま保持。`is_active = 1` が担当避難所。

**settings** — key-value
`disaster_type` / `active_shelter_id` / `current_evacuees`

## 設計上の制約（守ること）

**SQLite**
- 接続時に必ず `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`
- gunicorn は `-w 1 -k gthread --threads 8`。**ワーカーを増やすと書き込み競合**
- INSERTは1文で完結させる。トランザクションを長く持たない
- 一覧クエリに必ず `LIMIT` と `WHERE is_deleted = 0`

**フロントエンド**
- 古い端末でJS全体が停止するため、以下は使わない:
  `?.` / `??` / `:has()` / CSS Nesting / `<dialog>` / `100vh`
- ES2015相当に抑える（トランスパイル環境なし）
- localStorage は必ず try/catch。iOS プライベートブラウズで例外が出る
- 入力欄の font-size は 18px 以上（iOSのズーム暴発防止）
- **外部リソースを一切読まない**。オフラインで取得待ちが発生する

**API**
- `author_token` をレスポンスに含めない。`is_mine` を計算して返す

## UI方針

判断基準は「**疲れた高齢者が、暗い体育館で、片手で、初見で使えるか**」。

- 基準幅 375px（iPhone SE）。最大600pxでセンタリング
- 本文18px、ボタン20px。一般的な基準より大きめ
- 定型文ボタンは高さ64px以上、1列
- ハンバーガーメニューは使わない。隠さない
- **白背景**。暗所では白い画面の方が手元が見える
- 色分けは色だけに頼らず、アイコンと文字ラベルを併置
- **解決済みは消さない**。グレーアウト＋打ち消し線で残す。
  「助け合いが起きている」ことの可視化がこのアプリの価値
- 起動時のスプラッシュ・ロゴなし。アニメーションは `:active` のみ
- ただし**送信ボタンの即時disableは必須**（連打による二重投稿を防ぐ）
- エラー文に技術用語を出さない。次に何をすればいいかを書く
- 見た目はiOS寄り（`-apple-system`、角丸14px、面の重なりで階層表現）。
  ただしコントラストは落とさない

## 意図的に作らないもの

以下は「実装漏れ」ではなく**設計判断**。復活させないこと。

- **ログイン/認証** — 受付を通れない人（体調不良・乳児連れ・夜間到着）を排除するため
- **mDNS（hinan.local）** — Androidで名前解決が不安定、Docker Desktopから広告できない
- **PWA / Service Worker** — HTTPSが必要。かつサーバーが同一LAN内なのでキャッシュ不要
- **WebSocket** — ポーリングで足りる
- **MariaDB** — 障害点が増える。この規模ではSQLiteの方が速い
- 備品管理、気象庁API、近隣避難所の距離計算（緯度経度はCSVに無し）

## 現在の状態

**動いている**
- Docker環境、DB3テーブル、CSV取り込み（千葉県全件）
- タイムライン表示（サーバーサイドレンダリング20件）
- 投稿フロー（カテゴリ→定型文→送信、場所をlocalStorageに記憶）
- 解決トグル＋グレーアウト
- リプライ
- 災害種別の適合判定と警告表示

**未実装**
- `author_token` がHTMLに `data-owner` として露出している → `is_mine` 方式へ
- カテゴリタブのフィルタ（見た目だけ）
- ポーリング（差分取得 `?since=<id>`、新着バー、自動スクロールしない）
- 管理者機能（`?key=xxx` でピン留め・削除）

## 残タスク（優先度順）

1. `author_token` の露出修正
2. カテゴリタブのフィルタ
3. ポーリング（デモ中は2〜3秒間隔）
4. 管理者機能（最小限）
5. README（起動コマンドを1行目に）

## デモ台本（40秒）

```
1. 「このPCがAPです。外部ネットは繋がっていません」
2. スマホで開く（プロジェクタにはPCブラウザ）
3. 定型文で投稿
4. プロジェクタ側に出現
5. PC側から返信 → 解決 → グレーアウト
6. 「これがオフラインで完結しています」
```

デモの核はこの一周。**ここに関係ない機能は後回し**。

## 当日までの準備

- [ ] ファイアウォール受信規則（`New-NetFirewallRule -LocalPort 8080 -Profile Any`）
- [ ] モバイルホットスポット → スマホ（機内モード+Wi-Fi）から `192.168.137.1:8080` 到達確認
- [ ] **Android実機で表示・JS動作を確認**（DevToolsでは再現しない問題がある）
- [ ] `docker save` でイメージをtar化（ネット断の保険）
- [ ] 動作中の画面録画（デモ失敗時の保険）
- [ ] scrcpy をUSB接続で通しておく

## 環境メモ

- Windows + Docker Desktop
- PowerShell では `curl` が `Invoke-WebRequest` のエイリアス。**`curl.exe` と書く**
- DBはバインドマウントにしない。Windows+SQLiteでファイルロックが壊れる