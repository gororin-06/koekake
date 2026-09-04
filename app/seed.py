"""デモ用の初期データを投入する。既存の投稿は消える"""
import os
import sqlite3

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')

# 管理者と、避難者3人ぶんの端末トークン
ADMIN = 'seed-admin'
T1 = 'seed-user-1'
T2 = 'seed-user-2'
T3 = 'seed-user-3'


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute('DELETE FROM posts')
    cur.execute("DELETE FROM sqlite_sequence WHERE name = 'posts'")

    def post(category, body, token, location=None,
             is_admin=0, is_pinned=0, is_resolved=0, minutes_ago=0, parent_id=None):
        cur.execute("""
            INSERT INTO posts
              (parent_id, category, body, location, author_token,
               is_admin, is_pinned, is_resolved, resolved_at, post_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                    datetime('now', 'localtime', ?))
        """, (
            parent_id, category, body, location, token,
            is_admin, is_pinned, is_resolved,
            "datetime('now','localtime')" if is_resolved else None,
            f'-{minutes_ago} minutes',
        ))
        return cur.lastrowid

    # 本部からのおしらせ（ピン留め）
    post('info',
         '【給水車の到着】本日19:00より、体育館north側の入り口で給水を行います。'
         'ペットボトルや水筒をお持ちの方はご持参ください。'
         '歩行が難しい方は係員がお届けしますのでお声がけください。',
         ADMIN, location='本部受付', is_admin=1, is_pinned=1, minutes_ago=25)

    # 未解決のSOS（デモの主役。ここに返信して解決させる）
    post('sos',
         '毛布が1枚たりず、寒さで震えています。'
         '大人用の毛布か厚手の防寒着を余分にお持ちの方はいらっしゃいませんか。',
         T1, location='B-12', minutes_ago=8)

    # 子育て + 返信あり
    parent = post('child',
                  '子ども（3歳）が暗くて不安がって泣き止みません。'
                  'もし絵本やおもちゃ、折り紙を少し貸していただける方がいればとても助かります。',
                  T2, location='A-03', minutes_ago=18)
    post('info',
         '折り紙とアンパンマンの絵本が2冊あります。'
         '今からA-03ブロックにお持ちしましょうか。',
         T3, location='D-08', minutes_ago=12, parent_id=parent)

    # 解決済み（グレーアウトの見本）
    post('child',
         '乳幼児用の液体ミルクを探しています。常温で飲めるタイプをお持ちの方、ご協力お願いします。',
         T3, location='C-05', is_resolved=1, minutes_ago=70)

    # 体調
    post('health',
         '持病の薬を家に置いてきてしまいました。'
         '救護所がいつ開くかご存じの方はいらっしゃいますか。',
         T2, location='A-11', minutes_ago=35)

    conn.commit()

    n = cur.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
    print(f'{n} 件を投入しました')

    conn.close()


if __name__ == '__main__':
    main()