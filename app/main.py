import os
import sqlite3
import csv
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')
CATEGORIES = ('sos', 'health', 'child', 'info')

# 管理者キー。?key=... で照合する簡易認証。LAN内デモ用（本番運用向けではない）
ADMIN_KEY = os.environ.get('KOEKAKE_ADMIN_KEY', 'honbu')

# 連投防止：同一端末(token)の最短投稿間隔（秒）。管理者は除外
POST_COOLDOWN_SECONDS = 10

# settings.disaster_type のキー → (sheltersの列, 日本語ラベル)
DISASTER_TYPES = {
    'flood':      ('disaster_flood', '洪水'),
    'landslide':  ('disaster_landslide_etc', '崖崩れ・土石流・地滑り'),
    'stormsurge': ('disaster_stormsurge', '高潮'),
    'earthquake': ('disaster_earthquake', '地震'),
    'tsunami':    ('disaster_tsunami', '津波'),
    'fire':       ('disaster_large_scale_fire', '大規模な火事'),
    'inland':     ('disaster_inland_flooding', '内水氾濫'),
    'volcano':    ('disaster_volcanicactivity', '火山現象'),
}


def get_shelter_status(db):
    """アクティブ避難所と設定中の災害種別を突き合わせて返す。

    - shelter_name    : 常に文字列（避難所未設定でもフォールバック）
    - disaster_label  : 判定できないときは None（テンプレは何も出さない）
    - is_compatible   : True=対応 / False=非対応 / None=判定不能
    """
    shelter = db.execute(
        "SELECT * FROM shelters WHERE is_active = 1"
    ).fetchone()
    shelter_name = shelter['name'] if shelter else '避難所（未設定）'

    row = db.execute(
        "SELECT value FROM settings WHERE key = 'disaster_type'"
    ).fetchone()
    key = row['value'] if row else None

    # 管理者が --hide にしていればバナーを出さない（既定は表示）
    brow = db.execute(
        "SELECT value FROM settings WHERE key = 'disaster_banner'"
    ).fetchone()
    banner_on = not (brow and brow['value'] == 'off')

    label = None
    is_compatible = None
    # 災害種別が未設定・不明、避難所が未設定、またはバナー非表示なら判定を出さない
    if banner_on and shelter is not None and key in DISASTER_TYPES:
        col, label = DISASTER_TYPES[key]
        is_compatible = bool(shelter[col])

    # 避難所の詳細（左上タップで表示）
    details = None
    if shelter is not None:
        supported = [lbl for k, (col, lbl) in DISASTER_TYPES.items() if shelter[col]]
        details = {
            'address': shelter['address'] or '',
            'city': shelter['city'] or '',
            'prefecture': shelter['prefecture'] or '',
            'capacity': shelter['capacity'],
            'disasters': supported,
        }

    return {
        'shelter_name': shelter_name,
        'disaster_label': label,
        'is_compatible': is_compatible,
        'details': details,
    }


def get_db():
    if 'db' not in g:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA foreign_keys=ON')
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        with open('schema.sql', encoding='utf-8') as f:
            conn.executescript(f.read())
        # 既存DBにリアクション列が無ければ追加（マイグレーション）
        for col in ('reaction_helpful', 'reaction_seen'):
            try:
                conn.execute(
                    f'ALTER TABLE posts ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0'
                )
            except sqlite3.OperationalError:
                pass  # 既に存在する

def _cap_to_int(v):
    """想定収容人数の表記ゆれを整数に。'8,889人（敷地面積…）'→8889、空/不明→0"""
    if not v:
        return 0
    digits = ''
    for ch in str(v):
        if ch.isdigit():
            digits += ch
        elif ch == ',':
            continue
        else:
            break  # 先頭の数値だけ採用
    return int(digits) if digits else 0


def _to_flag(v):
    """災害種別列の表記ゆれを 1/0 に。'1'/'○'/'〇' 等→1、'※1'・空など→0"""
    return 1 if str(v).strip() in ('1', '○', '〇', '◯', 'TRUE', 'True') else 0


def import_shelters():
    csv_path = os.environ.get(
        'KOEKAKE_SHELTER_CSV',
        '/app/hinan-list.csv'
    )

    if not os.path.exists(csv_path):
        print(f'避難所CSVがありません: {csv_path}')
        return

    db = get_db()

    # すでにデータがあるなら二重登録しない
    count = db.execute(
        "SELECT COUNT(*) AS c FROM shelters"
    ).fetchone()['c']

    if count > 0:
        print(f'避難所データは既に {count} 件あります')
        return

    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)

        imported = 0

        for row in reader:
            db.execute("""
                INSERT INTO shelters (
                    id,
                    name,
                    address,
                    prefecture,
                    city,
                    disaster_flood,
                    disaster_landslide_etc,
                    disaster_stormsurge,
                    disaster_earthquake,
                    disaster_tsunami,
                    disaster_large_scale_fire,
                    disaster_inland_flooding,
                    disaster_volcanicactivity,
                    is_active,
                    capacity
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['NO']),
                row['名称'],
                row['住所'],
                row['都道府県名'],
                row['市区町村名'],
                _to_flag(row['災害種別_洪水']),
                _to_flag(row['災害種別_崖崩れ、土石流及び地滑り']),
                _to_flag(row['災害種別_高潮']),
                _to_flag(row['災害種別_地震']),
                _to_flag(row['災害種別_津波']),
                _to_flag(row['災害種別_大規模な火事']),
                _to_flag(row['災害種別_内水氾濫']),
                _to_flag(row['災害種別_火山現象']),
                0,  # is_active は管理者が選択する運用状態。CSVの重複フラグは使わない
                _cap_to_int(row['想定収容人数']),
            ))

            imported += 1

    db.commit()

    print(f'避難所データを {imported} 件登録しました')

def key_ok(key):
    """管理者キーの照合。空・不一致は False"""
    return bool(key) and key == ADMIN_KEY


@app.route('/')
def index():
    db = get_db()
    admin = key_ok(request.args.get('key'))

    # 解決から30分たった投稿は利用者の一覧から隠す（管理者には常に見せる）
    hide_resolved = "" if admin else (
        " AND NOT (is_resolved = 1 AND resolved_at IS NOT NULL"
        " AND resolved_at <= datetime('now','localtime','-1 minutes'))"
    )
    # 並び：ピン留め → 未解決を先に（解決済みは下へ）→ 体調（緊急性が高い）→ 新しい順
    posts = db.execute(f"""
        SELECT * FROM posts
        WHERE is_deleted = 0 AND parent_id IS NULL{hide_resolved}
        ORDER BY is_pinned DESC, is_resolved ASC, (category = 'health') DESC, id DESC
        LIMIT 20
    """).fetchall()

    # スレッド表示用：全階層の返信を親IDでまとめる（返信への返信も辿れるように）
    replies = {}
    reply_rows = db.execute("""
        SELECT * FROM posts
        WHERE is_deleted = 0 AND parent_id IS NOT NULL
        ORDER BY id ASC
        LIMIT 500
    """).fetchall()
    for r in reply_rows:
        replies.setdefault(r['parent_id'], []).append(r)

    # 各投稿のスレッド内の返信総数（子孫を全部数える）→ プルダウンの「返信N件」に使う
    def _count_desc(pid):
        total = 0
        stack = list(replies.get(pid, []))
        while stack:
            node = stack.pop()
            total += 1
            stack.extend(replies.get(node['id'], []))
        return total
    reply_counts = {p['id']: _count_desc(p['id']) for p in posts}

    status = get_shelter_status(db)

    # ポーリングの起点。この時点で存在する最大IDより後を「新着」とみなす
    mrow = db.execute("SELECT MAX(id) AS m FROM posts").fetchone()
    since_id = mrow['m'] or 0

    # 「今日」の判定に使う。post_at と同じ localtime で出して日付ズレを防ぐ
    today = db.execute("SELECT date('now','localtime') AS d").fetchone()['d']

    # 担当避難所が未設定なら初回セットアップ（避難所選択）画面を出す
    needs_setup = db.execute(
        "SELECT 1 FROM shelters WHERE is_active = 1 LIMIT 1"
    ).fetchone() is None

    return render_template('index.html',
                           posts=posts, replies=replies, status=status,
                           since_id=since_id, admin=admin, today=today,
                           needs_setup=needs_setup, reply_counts=reply_counts)


init_db()

with app.app_context():
    import_shelters()


@app.route('/sheltercount')
def sheltercount():
    db = get_db()

    row = db.execute(
        "SELECT COUNT(*) AS c FROM shelters"
    ).fetchone()

    return jsonify({
        'count': row['c']
    })


# =========================
# 避難所選択
# =========================

@app.route('/api/shelters/<int:shelter_id>/select', methods=['POST'])
def select_shelter(shelter_id):
    db = get_db()

    # このselect前に担当避難所が無ければ「初回セットアップ」＝この端末を管理者にする
    was_setup = db.execute(
        "SELECT 1 FROM shelters WHERE is_active = 1 LIMIT 1"
    ).fetchone() is None

    row = db.execute(
        "SELECT id, name FROM shelters WHERE id = ?",
        (shelter_id,)
    ).fetchone()

    if row is None:
        return jsonify({'error': 'not found'}), 404

    # いったん全部解除
    db.execute(
        "UPDATE shelters SET is_active = 0"
    )

    # 選択した避難所だけ有効化
    db.execute(
        "UPDATE shelters SET is_active = 1 WHERE id = ?",
        (shelter_id,)
    )

    # settingsにも記録
    db.execute("""
        INSERT INTO settings (key, value)
        VALUES ('active_shelter_id', ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (str(shelter_id),))

    db.commit()

    resp = {'ok': True, 'id': row['id'], 'name': row['name']}
    if was_setup:
        # 初回セットアップした端末に管理者モードURLを渡す（新しいタブで開く用）
        resp['admin_url'] = '/?key=' + ADMIN_KEY
    return jsonify(resp)


# =========================
# 市区町村一覧
# =========================

@app.route('/api/cities', methods=['GET'])
def list_cities():
    """避難所データに存在する市区町村の一覧。q で部分一致フィルタ。"""
    q = (request.args.get('q') or '').strip()
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT DISTINCT city FROM shelters "
            "WHERE city IS NOT NULL AND city != '' AND city LIKE ? "
            "ORDER BY city LIMIT 60",
            ('%' + q + '%',)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT DISTINCT city FROM shelters "
            "WHERE city IS NOT NULL AND city != '' ORDER BY city LIMIT 60"
        ).fetchall()
    return jsonify({'cities': [r['city'] for r in rows]})


# =========================
# 避難所検索
# =========================

@app.route('/api/shelters', methods=['GET'])
def search_shelters():
    q = (request.args.get('q') or '').strip()
    field = request.args.get('field', 'all')

    db = get_db()

    # 災害→市町村→施設フロー：city 指定なら、その市町村の避難所を disaster 対応順で返す
    # （対応しない避難所は除外せず、優先順位を下げて含める）
    city = request.args.get('city')
    disaster = request.args.get('disaster')
    if city:
        col = DISASTER_TYPES[disaster][0] if disaster in DISASTER_TYPES else None
        order = (col + " DESC, name") if col else "name"
        where = "city = ?"
        params = [city]
        # 避難所名・住所でのテキスト絞り込み（施設が多い市区町村向け）
        if q:
            like = '%' + q + '%'
            where += " AND (name LIKE ? OR address LIKE ?)"
            params.extend([like, like])
        rows = db.execute(
            f"SELECT * FROM shelters WHERE {where} ORDER BY {order} LIMIT 50",
            params
        ).fetchall()
        out = []
        for row in rows:
            ds = [lbl for k, (c, lbl) in DISASTER_TYPES.items() if row[c]]
            item = {
                'id': row['id'], 'name': row['name'],
                'address': row['address'] or '', 'city': row['city'] or '',
                'prefecture': row['prefecture'] or '', 'capacity': row['capacity'],
                'disasters': ds, 'is_active': bool(row['is_active']),
            }
            if col:
                item['is_compatible'] = bool(row[col])
            out.append(item)
        return jsonify({'shelters': out, 'count': len(out)})

    # キーワードが無いときは全件を返さない（数千件の巨大レスポンスを防ぐ）
    if not q:
        return jsonify({'shelters': [], 'count': 0})

    params = []

    if q:
        like = '%' + q + '%'

        if field == 'name':
            where = "name LIKE ?"
            params = [like]

        elif field == 'address':
            where = "address LIKE ?"
            params = [like]

        elif field == 'city':
            where = "city LIKE ?"
            params = [like]

        else:
            where = """
                (
                    name LIKE ?
                    OR address LIKE ?
                    OR prefecture LIKE ?
                    OR city LIKE ?
                )
            """
            params = [like, like, like, like]

        sql = f"""
            SELECT
                id,
                name,
                address,
                prefecture,
                city,
                capacity,
                disaster_flood,
                disaster_landslide_etc,
                disaster_stormsurge,
                disaster_earthquake,
                disaster_tsunami,
                disaster_large_scale_fire,
                disaster_inland_flooding,
                disaster_volcanicactivity,
                is_active
            FROM shelters
            WHERE {where}
            ORDER BY name
            LIMIT 50
        """

    rows = db.execute(sql, params).fetchall()

    disaster_labels = [
        ('disaster_flood', '洪水'),
        ('disaster_landslide_etc', '崖崩れ・土石流・地滑り'),
        ('disaster_stormsurge', '高潮'),
        ('disaster_earthquake', '地震'),
        ('disaster_tsunami', '津波'),
        ('disaster_large_scale_fire', '大規模な火事'),
        ('disaster_inland_flooding', '内水氾濫'),
        ('disaster_volcanicactivity', '火山現象'),
    ]

    result = []

    for row in rows:
        disasters = []

        for column, label in disaster_labels:
            if row[column]:
                disasters.append(label)

        result.append({
            'id': row['id'],
            'name': row['name'],
            'address': row['address'] or '',
            'prefecture': row['prefecture'] or '',
            'city': row['city'] or '',
            'capacity': row['capacity'],
            'disasters': disasters,
            'is_active': bool(row['is_active'])
        })

    return jsonify({
        'shelters': result,
        'count': len(result)
    })

    
@app.route('/api/posts')

def poll_posts():
    """新着の差分検知。since より後の未削除投稿の件数だけ返す。

    描画はしない（クライアントはリロードで取り直す）。返信も1件として数える。
    """
    try:
        since = int(request.args.get('since', 0))
    except (TypeError, ValueError):
        since = 0

    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) AS c FROM posts WHERE id > ? AND is_deleted = 0",
        (since,)
    ).fetchone()

    return jsonify({'count': row['c']})

@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()

    body = (data.get('body') or '').strip()
    category = data.get('category')
    token = data.get('token')

    if not body or category not in CATEGORIES or not token:
        return jsonify({'error': 'invalid'}), 400

    # 本部からのおしらせは管理者キーが正しいときだけ。本部投稿は先頭に固定する
    is_admin = 1 if (data.get('is_admin') and key_ok(data.get('key'))) else 0

    # 場所は必須（本部投稿は除く）。投稿・リプライとも
    location = (data.get('location') or '').strip()
    if not is_admin and not location:
        return jsonify({'error': 'need_location'}), 400

    db = get_db()

    # 連投防止：管理者以外は直近 POST_COOLDOWN_SECONDS 秒以内の投稿を弾く
    if not is_admin:
        recent = db.execute(
            "SELECT COUNT(*) AS c FROM posts WHERE author_token = ? "
            "AND post_at > datetime('now','localtime', ?)",
            (token, '-{} seconds'.format(POST_COOLDOWN_SECONDS))
        ).fetchone()['c']
        if recent > 0:
            return jsonify({'error': 'too_fast'}), 429

    cur = db.execute("""
        INSERT INTO posts (parent_id, category, body, author_name, location,
                           author_token, is_admin, is_pinned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('parent_id'),
        category,
        body[:500],
        (data.get('author_name') or '').strip() or None,
        location or None,
        token,
        is_admin,
        is_admin,
    ))
    db.commit()

    return jsonify({'id': cur.lastrowid}), 201

@app.route('/api/posts/<int:post_id>/resolve', methods=['POST'])
def resolve_post(post_id):
    data = request.get_json() or {}
    token = data.get('token')

    if not token:
        return jsonify({'error': 'invalid'}), 400

    db = get_db()
    row = db.execute(
        'SELECT author_token, is_resolved FROM posts WHERE id = ? AND is_deleted = 0',
        (post_id,)
    ).fetchone()

    if row is None:
        return jsonify({'error': 'not found'}), 404

    # 自分の投稿だけ操作できる
    if row['author_token'] != token:
        return jsonify({'error': 'forbidden'}), 403

    if row['is_resolved']:
        db.execute(
            'UPDATE posts SET is_resolved = 0, resolved_at = NULL WHERE id = ?',
            (post_id,)
        )
    else:
        db.execute(
            "UPDATE posts SET is_resolved = 1, resolved_at = datetime('now','localtime') WHERE id = ?",
            (post_id,)
        )
    db.commit()

    return jsonify({'ok': True})

@app.route('/api/posts/<int:post_id>/edit', methods=['POST'])
def edit_post(post_id):
    """自分の投稿の本文を編集。token一致が必須（自分の投稿だけ）。"""
    data = request.get_json(silent=True) or {}
    token = data.get('token')
    body = (data.get('body') or '').strip()

    if not token or not body:
        return jsonify({'error': 'invalid'}), 400

    db = get_db()
    row = db.execute(
        'SELECT author_token FROM posts WHERE id = ? AND is_deleted = 0', (post_id,)
    ).fetchone()
    if row is None:
        return jsonify({'error': 'not found'}), 404
    if row['author_token'] != token:
        return jsonify({'error': 'forbidden'}), 403

    db.execute('UPDATE posts SET body = ? WHERE id = ?', (body[:500], post_id))
    db.commit()

    return jsonify({'ok': True})


@app.route('/api/posts/<int:post_id>/react', methods=['POST'])
def react_post(post_id):
    """リアクション（助かった/確認した）の加減算。1端末1回はクライアント側で制御。"""
    data = request.get_json(silent=True) or {}
    col = {'helpful': 'reaction_helpful', 'seen': 'reaction_seen'}.get(data.get('type'))
    if col is None:
        return jsonify({'error': 'invalid'}), 400

    op = data.get('op', 'add')

    db = get_db()
    row = db.execute(
        f'SELECT {col} AS c FROM posts WHERE id = ? AND is_deleted = 0', (post_id,)
    ).fetchone()
    if row is None:
        return jsonify({'error': 'not found'}), 404

    newval = max(0, row['c'] - 1) if op == 'remove' else row['c'] + 1
    db.execute(f'UPDATE posts SET {col} = ? WHERE id = ?', (newval, post_id))
    db.commit()

    return jsonify({'ok': True, 'count': newval})


@app.route('/api/posts/<int:post_id>/pin', methods=['POST'])
def pin_post(post_id):
    data = request.get_json(silent=True) or {}
    if not key_ok(data.get('key')):
        return jsonify({'error': 'forbidden'}), 403

    db = get_db()
    row = db.execute(
        'SELECT is_pinned FROM posts WHERE id = ? AND is_deleted = 0', (post_id,)
    ).fetchone()
    if row is None:
        return jsonify({'error': 'not found'}), 404

    newval = 0 if row['is_pinned'] else 1
    db.execute('UPDATE posts SET is_pinned = ? WHERE id = ?', (newval, post_id))
    db.commit()

    return jsonify({'ok': True, 'is_pinned': newval})


@app.route('/api/posts/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    data = request.get_json(silent=True) or {}
    if not key_ok(data.get('key')):
        return jsonify({'error': 'forbidden'}), 403

    # 論理削除のみ（物理削除はしない。誤削除の復旧・デマ対応の記録のため）
    db = get_db()
    cur = db.execute(
        'UPDATE posts SET is_deleted = 1 WHERE id = ? AND is_deleted = 0', (post_id,)
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({'error': 'not found'}), 404

    return jsonify({'ok': True})


@app.route('/api/debug', methods=['POST'])
def debug_action():
    """管理者モードのDEBUG操作。key照合必須。開発・デモ用。"""
    data = request.get_json(silent=True) or {}
    if not key_ok(data.get('key')):
        return jsonify({'error': 'forbidden'}), 403

    action = data.get('action')
    db = get_db()

    if action == 'change_shelter':
        # 担当避難所を解除 → 次の表示で避難所選択画面に戻る
        db.execute("UPDATE shelters SET is_active = 0")
        db.commit()

    elif action == 'reset':
        # 避難所と設定をリセット（投稿は残す）→ 初回セットアップ状態へ
        db.execute("UPDATE shelters SET is_active = 0")
        db.execute(
            "DELETE FROM settings WHERE key IN "
            "('disaster_type', 'disaster_banner', 'active_shelter_id')"
        )
        db.commit()

    elif action == 'clear_posts':
        # 投稿を全削除（デバッグ用の物理削除）。自己参照FK対策で返信→親の順に消す
        db.execute("DELETE FROM posts WHERE parent_id IS NOT NULL")
        db.execute("DELETE FROM posts")
        db.execute("DELETE FROM sqlite_sequence WHERE name = 'posts'")
        db.commit()

    elif action == 'seed':
        # デモ用テストデータを投入（seed.py を再利用。既存投稿は置き換わる）
        import seed
        seed.main()

    else:
        return jsonify({'error': 'invalid action'}), 400

    return jsonify({'ok': True})


@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """接続端末の生存報告。last_seen を更新し、直近5分の接続数を返す。"""
    data = request.get_json(silent=True) or {}
    token = data.get('token')

    db = get_db()
    if token:
        db.execute(
            "INSERT INTO sessions (token, last_seen) VALUES (?, datetime('now','localtime')) "
            "ON CONFLICT(token) DO UPDATE SET last_seen = excluded.last_seen",
            (token,)
        )
        db.commit()

    # 30秒ごとにハートビートが来る前提。90秒(=2回分の猶予)を過ぎたら離脱とみなす
    active = db.execute(
        "SELECT COUNT(*) AS c FROM sessions "
        "WHERE last_seen > datetime('now','localtime','-90 seconds')"
    ).fetchone()['c']

    return jsonify({'sessions': active})


@app.route('/ping')
def ping():
    return "<h1 style='font-size:80px'>OK</h1>"


@app.route('/dbcheck')
def dbcheck():
    rows = get_db().execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return str([r['name'] for r in rows])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)