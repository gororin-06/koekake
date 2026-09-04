"""開発用: アクティブな避難所を切り替える

  一覧から探す:  python set_shelter.py 八幡東
  IDで確定する:  python set_shelter.py --id 1550
  今の設定を見る: python set_shelter.py
"""
import os
import sqlite3
import sys

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')

DISASTERS = [
    ('disaster_flood', '洪水'),
    ('disaster_landslide_etc', '崖崩れ等'),
    ('disaster_stormsurge', '高潮'),
    ('disaster_earthquake', '地震'),
    ('disaster_tsunami', '津波'),
    ('disaster_large_scale_fire', '大規模火事'),
    ('disaster_inland_flooding', '内水氾濫'),
    ('disaster_volcanicactivity', '火山現象'),
]


def show_current(conn):
    row = conn.execute(
        'SELECT * FROM shelters WHERE is_active = 1'
    ).fetchone()

    if row is None:
        print('アクティブな避難所は設定されていません')
        return

    print(f"現在: [{row['id']}] {row['name']}")
    print(f"  {row['city']} / {row['address']}")
    print(f"  想定収容: {row['capacity']}")
    ok = [label for col, label in DISASTERS if row[col]]
    print(f"  対応災害: {'、'.join(ok) if ok else 'なし'}")


def activate(conn, shelter_id):
    row = conn.execute(
        'SELECT id, name FROM shelters WHERE id = ?', (shelter_id,)
    ).fetchone()

    if row is None:
        print(f'ID {shelter_id} は見つかりません')
        return

    conn.execute('UPDATE shelters SET is_active = 0')
    conn.execute('UPDATE shelters SET is_active = 1 WHERE id = ?', (shelter_id,))
    conn.commit()
    print(f"→ [{row['id']}] {row['name']} に切り替えました\n")
    show_current(conn)


def search(conn, keyword):
    rows = conn.execute("""
        SELECT id, name, city FROM shelters
        WHERE name LIKE ? ORDER BY id LIMIT 30
    """, (f'%{keyword}%',)).fetchall()

    if not rows:
        print(f'「{keyword}」に一致する避難所はありません')
        return

    if len(rows) == 1:
        activate(conn, rows[0]['id'])
        return

    print(f'{len(rows)} 件みつかりました:')
    for r in rows:
        print(f"  [{r['id']}] {r['name']}  ({r['city']})")
    print('\nIDを指定してください:  python set_shelter.py --id <ID>')


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    args = sys.argv[1:]

    if not args:
        show_current(conn)
    elif args[0] == '--id' and len(args) > 1:
        activate(conn, int(args[1]))
    else:
        search(conn, args[0])

    conn.close()


if __name__ == '__main__':
    main()