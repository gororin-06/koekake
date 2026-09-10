"""負荷テスト用のサンプル投稿を大量投入する。

- **100件ずつ**（バッチ）INSERTし、バッチごとにコミットする
  （トランザクションを長く持たない＝書き込み競合を避ける。CLAUDE.mdの制約に合わせる）
- 既定では既存の投稿を消さずに**追記**する（負荷を何度でも積み上げられる）
- カテゴリ・場所・端末トークン・投稿時刻・解決/ピン/本部/リアクションを散らし、
  実データに近いタイムラインを作る

使い方:
  python python/loadtest_seed.py                 # 100件 追加
  python python/loadtest_seed.py 1000            # 1000件 追加（100件ずつ10バッチ）
  python python/loadtest_seed.py 1000 --reset    # 先に全削除してから1000件
  python python/loadtest_seed.py 500 --replies 0.3   # うち約3割を返信にする

Docker ワンショット:
  docker compose run --rm flask python python/loadtest_seed.py 1000

DBパスは環境変数 KOEKAKE_DB（既定 /data/koekake.db）。
"""
import argparse
import os
import random
import sqlite3
import time

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')
BATCH = 100  # 100件ずつコミット

# カテゴリと出現比率（sosと体調を厚めに＝SOSの負荷を想定）
CATEGORY_WEIGHTS = [
    ('sos', 40), ('health', 25), ('child', 20), ('info', 15),
]

# カテゴリ別の本文テンプレ。末尾に数量や番号を付けて重複を避ける
BODIES = {
    'sos': [
        '水がほしいです。飲用のペットボトルを分けていただけませんか',
        '毛布がたりません。厚手の防寒着でも助かります',
        '食べ物がほしいです。乾パンやレトルトなど日持ちするもの',
        '日用品（歯ブラシ・タオル・生理用品）を探しています',
        'モバイルバッテリーか充電できる場所はありませんか',
        'カセットコンロのガスボンベが残っている方いませんか',
    ],
    'health': [
        '持病の薬を家に置いてきてしまいました。救護所はいつ開きますか',
        '熱が38度あります。解熱剤をお持ちの方いませんか',
        '足をひねって歩けません。湿布か包帯を分けてください',
        'マスクが切れました。予備をお持ちの方いらっしゃいますか',
        '血圧の薬が明日で切れます。相談できる方はいますか',
    ],
    'child': [
        '粉ミルクを探しています。常温で作れるお湯もあると助かります',
        'おむつ（Mサイズ）が不足しています。分けていただけませんか',
        '離乳食のストックが尽きそうです。ゆずれる方いませんか',
        '子どもが暗くて泣き止みません。絵本やおもちゃを貸してください',
        '子ども用の着替えがありません。5歳くらいのサイズを探しています',
    ],
    'info': [
        'ゆずれるカイロが多めにあります。必要な方お声がけください',
        '本部前で給水をやっているそうです',
        'お手伝いできます。力仕事や運搬など声かけてください',
        'トイレは体育館北側が使えるようになりました',
        '毛布を2枚ゆずれます。C区画にいます',
    ],
}

# 返信で使う相づち（親投稿に対する反応）
REPLIES = [
    'こちらに予備があります。今から届けましょうか',
    'B区画にありました。取りに来られますか',
    '同じものを探しています。見つかったら共有します',
    '本部に在庫があるか聞いてみます',
    '少しなら分けられます。場所はどちらですか',
    'お大事に。係の人に伝えておきました',
]


def weighted_category():
    r = random.randint(1, sum(w for _, w in CATEGORY_WEIGHTS))
    acc = 0
    for cat, w in CATEGORY_WEIGHTS:
        acc += w
        if r <= acc:
            return cat
    return 'info'


def random_location():
    return random.choice('ABCDEFGH') + '-' + str(random.randint(1, 40)).zfill(2)


def main():
    ap = argparse.ArgumentParser(description='負荷テスト用の投稿を100件ずつ投入する')
    ap.add_argument('total', nargs='?', type=int, default=100,
                    help='投入する総件数（既定100）。100件ずつバッチ投入する')
    ap.add_argument('--reset', action='store_true',
                    help='投入前に既存の投稿を全削除してIDを振り直す')
    ap.add_argument('--replies', type=float, default=0.15,
                    help='返信にする割合 0.0〜1.0（既定0.15）')
    ap.add_argument('--tokens', type=int, default=200,
                    help='擬似端末トークンの数＝投稿者の多様性（既定200）')
    ap.add_argument('--span-hours', type=int, default=48,
                    help='投稿時刻を散らす範囲（直近この時間内。既定48）')
    args = ap.parse_args()

    total = max(0, args.total)
    reply_ratio = min(max(args.replies, 0.0), 1.0)
    tokens = ['lt-user-' + str(i) for i in range(max(1, args.tokens))]

    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute('PRAGMA synchronous=NORMAL')
    cur = conn.cursor()

    if args.reset:
        cur.execute('DELETE FROM posts')
        cur.execute("DELETE FROM sqlite_sequence WHERE name = 'posts'")
        conn.commit()
        print('既存の投稿を全削除しました')

    # 返信の親候補（既存の親投稿ID）を読み込む。以降、新規の親も足していく
    parent_ids = [row[0] for row in cur.execute(
        'SELECT id FROM posts WHERE parent_id IS NULL AND is_deleted = 0 '
        'ORDER BY id DESC LIMIT 2000'
    ).fetchall()]

    span_minutes = max(1, args.span_hours * 60)
    started = time.time()
    inserted = 0

    def make_row():
        # 返信にするか（親候補があるときだけ）
        as_reply = parent_ids and random.random() < reply_ratio
        minutes_ago = random.randint(0, span_minutes)
        token = random.choice(tokens)

        if as_reply:
            parent_id = random.choice(parent_ids)
            body = random.choice(REPLIES)
            return (parent_id, 'info', body, None, token, 0, 0, 0, None, minutes_ago)

        category = weighted_category()
        body = random.choice(BODIES[category]) + '（' + str(random.randint(1, 99)) + '）'
        is_admin = 1 if random.random() < 0.03 else 0
        is_pinned = 1 if (is_admin and random.random() < 0.3) else 0
        # SOS/体調/子育ては一定割合が解決済み（グレーアウトの見本）
        is_resolved = 0
        if category in ('sos', 'health', 'child') and random.random() < 0.25:
            is_resolved = 1
        location = None if is_admin else random_location()
        return (None, category, body, location, token,
                is_admin, is_pinned, is_resolved,
                'resolved' if is_resolved else None, minutes_ago)

    sql = """
        INSERT INTO posts
          (parent_id, category, body, location, author_token,
           is_admin, is_pinned, is_resolved, resolved_at,
           reaction_helpful, post_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                datetime('now', 'localtime', ?))
    """

    while inserted < total:
        n = min(BATCH, total - inserted)
        new_parents = []
        for _ in range(n):
            (parent_id, category, body, location, token,
             is_admin, is_pinned, is_resolved, resolved_flag, minutes_ago) = make_row()
            resolved_at = None
            if resolved_flag == 'resolved':
                # 投稿より後の時刻で解決したことにする
                solved = max(0, minutes_ago - random.randint(1, 30))
                resolved_at = cur.execute(
                    "SELECT datetime('now','localtime', ?)", (f'-{solved} minutes',)
                ).fetchone()[0]
            reaction = random.choice([0, 0, 0, 1, 2, 3, 5, 8])
            cur.execute(sql, (
                parent_id, category, body, location, token,
                is_admin, is_pinned, is_resolved, resolved_at,
                reaction, f'-{minutes_ago} minutes',
            ))
            # 新しい親投稿は返信先候補に加える
            if parent_id is None:
                new_parents.append(cur.lastrowid)
        conn.commit()  # 100件ごとにコミット
        parent_ids.extend(new_parents)
        if len(parent_ids) > 4000:      # 候補が増えすぎないよう間引く
            parent_ids = parent_ids[-4000:]
        inserted += n
        print(f'  {inserted}/{total} 件 投入…')

    elapsed = time.time() - started
    grand = cur.execute('SELECT COUNT(*) FROM posts WHERE is_deleted = 0').fetchone()[0]
    conn.close()
    rate = inserted / elapsed if elapsed > 0 else 0
    print(f'完了：{inserted} 件を投入（{elapsed:.2f}秒 / {rate:.0f} 件/秒）。'
          f'現在の有効投稿は {grand} 件です')


if __name__ == '__main__':
    main()
