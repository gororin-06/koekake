"""SQLite 接続のライフサイクルとスキーマ初期化。

- get_db()   : リクエストごとに1接続を使い回す（WAL等のPRAGMAを必ず設定）
- close_db() : リクエスト終了時に閉じる（main.py で teardown に登録）
- init_db()  : 起動時にスキーマ適用＋不足列のマイグレーション
"""
import sqlite3
from flask import g

from config import DB_PATH


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
