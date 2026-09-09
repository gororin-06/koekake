# main.py 解説（関数別）

こえかけの `app/main.py` が何をしているかを、上から関数ごとにまとめたメモ。

## リクエストの流れ（先に全体像）

1. **起動時**：モジュール読み込みで `init_db()` → `import_shelters()` が一度だけ走る（gunicorn 起動時）。
2. **リクエストごと**：`get_db()` で接続を開く → ルート関数が処理 → `close_db()` で閉じる。
3. **画面**は `index()` が組み立てて `index.html` に渡す。投稿・避難所・管理操作はすべて `/api/...` の JSON API をフロント（`app.js`）が叩く。

---

## 冒頭（グローバル設定）

- `app = Flask(__name__)` … Flask アプリ本体。
- `DB_PATH` … SQLite の場所（環境変数、既定 `/data/koekake.db`）。
- `CATEGORIES` … 投稿カテゴリの許可リスト（`sos / health / child / info`）。
- `ADMIN_KEY` … 管理者キー（`?key=` 照合用、既定 `honbu`）。
- `DISASTER_TYPES` … 災害キー → (sheltersの列名, 日本語ラベル) の対応表。災害バナー判定に使う。

## DB・起動まわり

- **`get_db()`** … 1リクエストにつき1本の SQLite 接続を作って `g`（リクエストローカル）に保持。WAL / busy_timeout 等の PRAGMA をここで設定。以後同じリクエスト内では使い回す。
- **`close_db(exc)`** … リクエスト終了時（teardown）に接続を閉じる。
- **`init_db()`** … `schema.sql` を実行してテーブルを作成（`CREATE TABLE IF NOT EXISTS` なので既存データは消えない）。
- **`_cap_to_int(v)`** … 「想定収容人数」の表記ゆれ（`8,889人（…）`）から先頭の数値だけ取り出す。空/不明は 0。
- **`_to_flag(v)`** … 災害種別セルを 1/0 に正規化（`1` / `○` 等→1、`※1` や空→0）。
- **`import_shelters()`** … CSV（`hinan-list.csv`）を読み `shelters` に一括 INSERT。**すでにデータがあればスキップ**（`count > 0`）。`is_active` は必ず 0（＝避難所は管理者が後で選ぶ）。
- **起動シーケンス** … モジュール読み込み時に `init_db()` → `import_shelters()` を実行。gunicorn 起動時に一度だけ走る。

## 共通ヘルパ

- **`key_ok(key)`** … 管理者キーの照合。空や不一致は `False`。pin / delete / debug / 本部投稿で使う。
- **`get_shelter_status(db)`** … アクティブ避難所と `settings.disaster_type` を突き合わせ、テンプレ用の辞書 `{shelter_name, disaster_label, is_compatible}` を返す。バナー非表示 (`--hide`) や未設定なら判定を出さない（`None`）。

## ページ

- **`index()` — `GET /`** … トップページ。やること：
  1. `admin`（`?key=` が正しいか）判定
  2. 投稿を**最新20件**取得（親のみ・未削除・ピン優先）＋その返信をまとめ取り
  3. `get_shelter_status` で災害バナー情報
  4. `since_id`（新着チェックの起点＝現在の最大ID）
  5. `today`（日付表示用）
  6. `needs_setup`（アクティブ避難所が無ければ初期設定画面を出す）
  7. これらを `index.html` に渡してレンダリング

## 避難所 API

- **`sheltercount()` — `GET /sheltercount`** … 避難所の件数を返すだけ（動作確認用）。
- **`select_shelter(id)` — `POST /api/shelters/<id>/select`** … 全避難所を `is_active=0` にしてから指定IDだけ有効化、`settings.active_shelter_id` にも記録。**初回セットアップ（それまで未設定）のときだけ** レスポンスに `admin_url:/?key=honbu` を含める（＝新しいタブで管理者モードを開く用）。
- **`search_shelters()` — `GET /api/shelters`** … `q`（キーワード）と `field`（all/name/address/city）で LIKE 検索。**空クエリは空を返す**（全件ダンプ防止）、最大 **50件**。各避難所の対応災害を日本語ラベルの配列にして返す。

## 投稿 API

- **`poll_posts()` — `GET /api/posts`** … `since` より後の未削除投稿の**件数だけ**返す。新着バーの検知用（描画はしない）。
- **`create_post()` — `POST /api/posts`** … 投稿・返信の作成。body / category / token を検証。`is_admin` は**キーが正しいときだけ**立ち、本部投稿はピン留めもされる。作成したIDを返す。
- **`resolve_post(id)` — `POST /api/posts/<id>/resolve`** … 解決/未解決のトグル。**自分の投稿（token一致）だけ**操作可（他人は 403）。
- **`pin_post(id)` — `POST /api/posts/<id>/pin`** … ピン留めトグル。**管理者キー必須**。
- **`delete_post(id)` — `POST /api/posts/<id>/delete`** … **論理削除**（`is_deleted=1`、物理削除しない）。管理者キー必須。

## 管理・デバッグ

- **`debug_action()` — `POST /api/debug`** … 管理者キー必須の DEBUG 操作。`action` で分岐：
  - `change_shelter` … 避難所を解除（→選択画面へ）
  - `reset` … 避難所＋設定をリセット（投稿は残す）
  - `clear_posts` … 投稿を物理削除（FK対策で返信→親の順）
  - `seed` … `seed.py` を呼んでテストデータ投入

## ユーティリティ

- **`ping()` — `GET /ping`** … 「OK」を返す生存確認。
- **`dbcheck()` — `GET /dbcheck`** … テーブル一覧を返す確認用。
- **`if __name__ == '__main__'`** … `python main.py` で直接起動したときだけ開発サーバを起動。**本番はここを通らず gunicorn が `main:app` を読み込む**（Dockerfile の CMD）。

---

## 補足メモ

- `/api/posts` は **GET（新着件数）と POST（作成）で別関数**。同じパスにメソッド違いで割り当てている。
- `select_shelter` にはキー照合が無い＝**セットアップ中は誰でも選択できる**。初回だけ `admin_url` を渡す設計で「最初に設定した人＝管理者」を実現している（LAN内デモ前提）。
- 認証は `author_token`（localStorage）と `ADMIN_KEY` の2本立て。厳密な認証は意図的に持たない（避難所で受付を通れない人を排除しないため）。
