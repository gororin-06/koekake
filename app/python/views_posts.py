"""投稿・返信まわりのAPI：新着ポーリング／作成／解決／編集／リアクション／
ピン留め／削除。ピンと削除は管理者キーが必要。"""
from flask import Blueprint, request, jsonify

from .db import get_db
from .config import CATEGORIES, POST_COOLDOWN_SECONDS
from .services import key_ok

bp = Blueprint('posts', __name__)


@bp.route('/api/posts')
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


@bp.route('/api/posts', methods=['POST'])
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


@bp.route('/api/posts/<int:post_id>/resolve', methods=['POST'])
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


@bp.route('/api/posts/<int:post_id>/edit', methods=['POST'])
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


@bp.route('/api/posts/<int:post_id>/react', methods=['POST'])
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


@bp.route('/api/posts/<int:post_id>/pin', methods=['POST'])
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


@bp.route('/api/posts/<int:post_id>/delete', methods=['POST'])
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
