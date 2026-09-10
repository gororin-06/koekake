"""ルートに依存しないドメインロジック（避難所ステータス算出・管理者キー照合）。

ここは Flask のリクエスト文脈を知らず、db 接続を引数で受け取る純粋な処理に寄せる。
テストや再利用がしやすいように view から切り離してある。
"""
from .config import ADMIN_KEY, DISASTER_TYPES


def key_ok(key):
    """管理者キーの照合。空・不一致は False"""
    return bool(key) and key == ADMIN_KEY


def get_shelter_status(db):
    """アクティブ避難所と設定中の災害種別を突き合わせて返す。

    - shelter_name    : 常に文字列（避難所未設定でもフォールバック）
    - disaster_label  : 判定できないときは None（テンプレは何も出さない）
    - is_compatible   : True=対応 / False=非対応 / None=判定不能
    """
    shelter = db.execute(
        "SELECT * FROM shelters WHERE is_active = 1"
    ).fetchone()
    shelter_name = shelter['name'] if shelter else '避難所（未設定）'

    row = db.execute(
        "SELECT value FROM settings WHERE key = 'disaster_type'"
    ).fetchone()
    key = row['value'] if row else None

    # 管理者が --hide にしていればバナーを出さない（既定は表示）
    brow = db.execute(
        "SELECT value FROM settings WHERE key = 'disaster_banner'"
    ).fetchone()
    banner_on = not (brow and brow['value'] == 'off')

    label = None
    is_compatible = None
    # 災害種別が未設定・不明、避難所が未設定、またはバナー非表示なら判定を出さない
    if banner_on and shelter is not None and key in DISASTER_TYPES:
        col, label = DISASTER_TYPES[key]
        is_compatible = bool(shelter[col])

    # 避難所の詳細（左上タップで表示）
    details = None
    if shelter is not None:
        supported = [lbl for k, (col, lbl) in DISASTER_TYPES.items() if shelter[col]]
        details = {
            'address': shelter['address'] or '',
            'city': shelter['city'] or '',
            'prefecture': shelter['prefecture'] or '',
            'capacity': shelter['capacity'],
            'disasters': supported,
        }

    return {
        'shelter_name': shelter_name,
        'disaster_label': label,
        'is_compatible': is_compatible,
        'details': details,
    }
