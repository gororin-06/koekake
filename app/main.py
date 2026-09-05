import os
import sqlite3
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')
CATEGORIES = ('sos', 'health', 'child', 'info')

# 管理者キー。?key=... で照合する簡易認証。LAN内デモ用（本番運用向けではない）
ADMIN_KEY = os.environ.get('KOEKAKE_ADMIN_KEY', 'honbu')

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

    return {
        'shelter_name': shelter_name,
        'disaster_label': label,
        'is_compatible': is_compatible,
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


init_db()


def key_ok(key):
    """管理者キーの照合。空・不一致は False"""
    return bool(key) and key == ADMIN_KEY


@app.route('/')
def index():
    db = get_db()
    admin = key_ok(request.args.get('key'))

    posts = db.execute("""
        SELECT * FROM posts
        WHERE is_deleted = 0 AND parent_id IS NULL
        ORDER BY is_pinned DESC, id DESC
        LIMIT 20
    """).fetchall()

    # 表示中の親に対する返信をまとめて取る
    replies = {}
    if posts:
        ids = [p['id'] for p in posts]
        ph = ','.join('?' * len(ids))
        rows = db.execute(f"""
            SELECT * FROM posts
            WHERE is_deleted = 0 AND parent_id IN ({ph})
            ORDER BY id ASC
        """, ids).fetchall()
        for r in rows:
            replies.setdefault(r['parent_id'], []).append(r)

    status = get_shelter_status(db)

    # ポーリングの起点。この時点で存在する最大IDより後を「新着」とみなす
    mrow = db.execute("SELECT MAX(id) AS m FROM posts").fetchone()
    since_id = mrow['m'] or 0

    # 「今日」の判定に使う。post_at と同じ localtime で出して日付ズレを防ぐ
    today = db.execute("SELECT date('now','localtime') AS d").fetchone()['d']

    return render_template('index.html',
                           posts=posts, replies=replies, status=status,
                           since_id=since_id, admin=admin, today=today)


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

    db = get_db()
    cur = db.execute("""
        INSERT INTO posts (parent_id, category, body, author_name, location,
                           author_token, is_admin, is_pinned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('parent_id'),
        category,
        body[:500],
        (data.get('author_name') or '').strip() or None,
        (data.get('location') or '').strip() or None,
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