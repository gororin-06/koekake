"""画面（HTML）を返すルート。いまはトップの掲示板 `/` のみ。"""
from flask import Blueprint, render_template, request

from .db import get_db
from .services import get_shelter_status, key_ok

bp = Blueprint('pages', __name__)


@bp.route('/')
def index():
    db = get_db()
    admin = key_ok(request.args.get('key'))

    # 何件まで表示するか。「もっと見る」で20件ずつ増える（?show=40, 60 ...）。
    # 上限を設けて、極端な値でも一覧クエリが重くならないようにする
    try:
        show = int(request.args.get('show', 20))
    except (TypeError, ValueError):
        show = 20
    show = max(20, min(show, 200))

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
        LIMIT ?
    """, (show,)).fetchall()

    # まだ表示していない親投稿があるか（あれば「もっと見る」を出す）
    total_parents = db.execute(
        f"SELECT COUNT(*) AS c FROM posts "
        f"WHERE is_deleted = 0 AND parent_id IS NULL{hide_resolved}"
    ).fetchone()['c']
    has_more = total_parents > len(posts)

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
                           needs_setup=needs_setup, reply_counts=reply_counts,
                           show=show, has_more=has_more)
