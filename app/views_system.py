"""システム系の小さなエンドポイント：接続端末数（ハートビート）・疎通確認・
利用者用アクセス先（この端末のLAN IP）の提示。"""
import os
import socket

from flask import Blueprint, request, jsonify

from db import get_db

bp = Blueprint('system', __name__)


def _detect_ips():
    """この端末のIPv4候補を集める。

    注意：本番はDockerコンテナ内で動くため、ここで拾えるのはコンテナ側の
    アドレス（172.x など）になりがちで、スマホから到達できるホスト（PC）の
    ホットスポットIP（例 192.168.137.1）とは一致しない。
    そのため確実な値は環境変数 KOEKAKE_HOST_IP（ホスト側で検出して注入）を優先する。
    ここで返す候補はあくまで補助。
    """
    ips = []

    def _add(ip):
        if ip and ip not in ips and not ip.startswith('127.'):
            ips.append(ip)

    # OSが外向き経路に選ぶNICのアドレス（実際にはパケットを送らない）
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('192.168.137.1', 9))  # ホットスポットのゲートウェイ想定・到達不要
            _add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass

    # ホスト名解決でも候補を拾う
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            _add(info[4][0])
    except OSError:
        pass

    return ips


@bp.route('/api/access')
def access_info():
    """利用者用アクセス先の手がかりを返す。

    - host      : 最も確実なアクセス先ホスト（環境変数があればそれ）。無ければ ''
    - source    : 'env'（注入・権威）/ 'auto'（自動検出・弱い）/ 'none'
    - candidates: 参考のIPv4候補一覧

    URL自体はクライアント側で組み立てる（管理者が使っているポートを使うため）。
    """
    env_ip = (os.environ.get('KOEKAKE_HOST_IP') or '').strip()
    candidates = _detect_ips()
    if env_ip:
        host, source = env_ip, 'env'
    elif candidates:
        host, source = candidates[0], 'auto'
    else:
        host, source = '', 'none'
    return jsonify({'host': host, 'source': source, 'candidates': candidates})


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


@bp.route('/ping')
def ping():
    return "<h1 style='font-size:80px'>OK</h1>"


@bp.route('/dbcheck')
def dbcheck():
    rows = get_db().execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return str([r['name'] for r in rows])
