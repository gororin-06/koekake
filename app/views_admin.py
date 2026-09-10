"""管理者ツール（旧DEBUG）：避難所変更・完全初期化・投稿全削除・テストデータ投入。
すべて管理者キーの照合が必須。開発・デモ用。"""
from flask import Blueprint, request, jsonify

from db import get_db
from services import key_ok

bp = Blueprint('admin', __name__)


@bp.route('/api/debug', methods=['POST'])
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
        # 完全初期化：避難所・設定・投稿をすべて消して初回セットアップ状態へ戻す
        db.execute("UPDATE shelters SET is_active = 0")
        db.execute(
            "DELETE FROM settings WHERE key IN "
            "('disaster_type', 'disaster_banner', 'active_shelter_id')"
        )
        # 投稿も物理削除（自己参照FK対策で返信→親の順に消す）
        db.execute("DELETE FROM posts WHERE parent_id IS NOT NULL")
        db.execute("DELETE FROM posts")
        db.execute("DELETE FROM sqlite_sequence WHERE name = 'posts'")
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
