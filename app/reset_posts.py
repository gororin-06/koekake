"""投稿を全件削除する。開発中の掃除用"""
import os
import sqlite3

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')

conn = sqlite3.connect(DB_PATH)
n = conn.execute('SELECT COUNT(*) FROM posts').fetchone()[0]

conn.execute('DELETE FROM posts')
# IDを1から振り直す
conn.execute("DELETE FROM sqlite_sequence WHERE name = 'posts'")
conn.commit()
conn.close()

print(f'{n} 件を削除しました')