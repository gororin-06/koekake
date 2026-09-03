import os
import sqlite3
from flask import Flask, render_template, request, jsonify, g

app = Flask(__name__)

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')
CATEGORIES = ('sos', 'health', 'child', 'info')


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


@app.route('/')
def index():
    db = get_db()

    posts = db.execute("""
        SELECT * FROM posts
        WHERE is_deleted = 0 AND parent_id IS NULL
        ORDER BY is_pinned DESC, id DESC
        LIMIT 20
    """).fetchall()

    row = db.execute(
        "SELECT name FROM shelters WHERE is_active = 1"
    ).fetchone()
    shelter_name = row['name'] if row else '避難所（未設定）'

    return render_template('index.html', posts=posts, shelter_name=shelter_name)
@app.route('/api/posts', methods=['POST'])
def create_post():
    data = request.get_json()

    body = (data.get('body') or '').strip()
    category = data.get('category')
    token = data.get('token')

    if not body or category not in CATEGORIES or not token:
        return jsonify({'error': 'invalid'}), 400

    db = get_db()
    cur = db.execute("""
        INSERT INTO posts (parent_id, category, body, author_name, location, author_token)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data.get('parent_id'),
        category,
        body[:500],
        (data.get('author_name') or '').strip() or None,
        (data.get('location') or '').strip() or None,
        token,
    ))
    db.commit()

    return jsonify({'id': cur.lastrowid}), 201


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