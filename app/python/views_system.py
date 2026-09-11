"""システム系の小さなエンドポイント：接続端末数（ハートビート）。

利用者用アクセス先のIP自動検出は廃止した（Dockerコンテナ内では 172.x など
スマホから到達できないアドレスになるため）。アクセスQRは管理者が
この端末のIPを手入力して生成する（static/app.js の access パネル）。"""
from flask import Blueprint, request, jsonify

from .db import get_db

bp = Blueprint('system', __name__)


@bp.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """接続端末の生存報告。last_seen を更新し、直近5分の接続数を返す。"""
    data = request.get_json(silent=True) or {}
    token = data.get('token')

    db = get_db()
    if token:
        db.execute(
            "INSERT INTO sessions (token, last_seen) VALUES (?, datetime('now','localtime')) "
            "ON CONFLICT(token) DO UPDATE SET last_seen = excluded.last_seen",
            (token,)
        )
        db.commit()

    # 30秒ごとにハートビートが来る前提。90秒(=2回分の猶予)を過ぎたら離脱とみなす
    active = db.execute(
        "SELECT COUNT(*) AS c FROM sessions "
        "WHERE last_seen > datetime('now','localtime','-90 seconds')"
    ).fetchone()['c']

    return jsonify({'sessions': active})
