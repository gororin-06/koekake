"""避難所まわりのAPI：件数・選択（初回セットアップ）・市区町村一覧・検索。"""
from flask import Blueprint, request, jsonify

from db import get_db
from config import ADMIN_KEY, DISASTER_TYPES

bp = Blueprint('shelters', __name__)


@bp.route('/sheltercount')
def sheltercount():
    db = get_db()

    row = db.execute(
        "SELECT COUNT(*) AS c FROM shelters"
    ).fetchone()

    return jsonify({
        'count': row['c']
    })


# =========================
# 避難所選択
# =========================

@bp.route('/api/shelters/<int:shelter_id>/select', methods=['POST'])
def select_shelter(shelter_id):
    db = get_db()

    # このselect前に担当避難所が無ければ「初回セットアップ」＝この端末を管理者にする
    was_setup = db.execute(
        "SELECT 1 FROM shelters WHERE is_active = 1 LIMIT 1"
    ).fetchone() is None

    row = db.execute(
        "SELECT id, name FROM shelters WHERE id = ?",
        (shelter_id,)
    ).fetchone()

    if row is None:
        return jsonify({'error': 'not found'}), 404

    # いったん全部解除
    db.execute(
        "UPDATE shelters SET is_active = 0"
    )

    # 選択した避難所だけ有効化
    db.execute(
        "UPDATE shelters SET is_active = 1 WHERE id = ?",
        (shelter_id,)
    )

    # settingsにも記録
    db.execute("""
        INSERT INTO settings (key, value)
        VALUES ('active_shelter_id', ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (str(shelter_id),))

    db.commit()

    resp = {'ok': True, 'id': row['id'], 'name': row['name']}
    if was_setup:
        # 初回セットアップした端末に管理者モードURLを渡す（新しいタブで開く用）
        resp['admin_url'] = '/?key=' + ADMIN_KEY
    return jsonify(resp)


# =========================
# 市区町村一覧
# =========================

@bp.route('/api/cities', methods=['GET'])
def list_cities():
    """避難所データに存在する市区町村の一覧。q で部分一致フィルタ。"""
    q = (request.args.get('q') or '').strip()
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT DISTINCT city FROM shelters "
            "WHERE city IS NOT NULL AND city != '' AND city LIKE ? "
            "ORDER BY city LIMIT 60",
            ('%' + q + '%',)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT DISTINCT city FROM shelters "
            "WHERE city IS NOT NULL AND city != '' ORDER BY city LIMIT 60"
        ).fetchall()
    return jsonify({'cities': [r['city'] for r in rows]})


# =========================
# 避難所検索
# =========================

@bp.route('/api/shelters', methods=['GET'])
def search_shelters():
    q = (request.args.get('q') or '').strip()
    field = request.args.get('field', 'all')

    db = get_db()

    # 災害→市町村→施設フロー：city 指定なら、その市町村の避難所を disaster 対応順で返す
    # （対応しない避難所は除外せず、優先順位を下げて含める）
    city = request.args.get('city')
    disaster = request.args.get('disaster')
    if city:
        col = DISASTER_TYPES[disaster][0] if disaster in DISASTER_TYPES else None
        order = (col + " DESC, name") if col else "name"
        where = "city = ?"
        params = [city]
        # 避難所名・住所でのテキスト絞り込み（施設が多い市区町村向け）
        if q:
            like = '%' + q + '%'
            where += " AND (name LIKE ? OR address LIKE ?)"
            params.extend([like, like])
        rows = db.execute(
            f"SELECT * FROM shelters WHERE {where} ORDER BY {order} LIMIT 50",
            params
        ).fetchall()
        out = []
        for row in rows:
            ds = [lbl for k, (c, lbl) in DISASTER_TYPES.items() if row[c]]
            item = {
                'id': row['id'], 'name': row['name'],
                'address': row['address'] or '', 'city': row['city'] or '',
                'prefecture': row['prefecture'] or '', 'capacity': row['capacity'],
                'disasters': ds, 'is_active': bool(row['is_active']),
            }
            if col:
                item['is_compatible'] = bool(row[col])
            out.append(item)
        return jsonify({'shelters': out, 'count': len(out)})

    # キーワードが無いときは全件を返さない（数千件の巨大レスポンスを防ぐ）
    if not q:
        return jsonify({'shelters': [], 'count': 0})

    params = []

    if q:
        like = '%' + q + '%'

        if field == 'name':
            where = "name LIKE ?"
            params = [like]

        elif field == 'address':
            where = "address LIKE ?"
            params = [like]

        elif field == 'city':
            where = "city LIKE ?"
            params = [like]

        else:
            where = """
                (
                    name LIKE ?
                    OR address LIKE ?
                    OR prefecture LIKE ?
                    OR city LIKE ?
                )
            """
            params = [like, like, like, like]

        sql = f"""
            SELECT
                id,
                name,
                address,
                prefecture,
                city,
                capacity,
                disaster_flood,
                disaster_landslide_etc,
                disaster_stormsurge,
                disaster_earthquake,
                disaster_tsunami,
                disaster_large_scale_fire,
                disaster_inland_flooding,
                disaster_volcanicactivity,
                is_active
            FROM shelters
            WHERE {where}
            ORDER BY name
            LIMIT 50
        """

    rows = db.execute(sql, params).fetchall()

    disaster_labels = [
        ('disaster_flood', '洪水'),
        ('disaster_landslide_etc', '崖崩れ・土石流・地滑り'),
        ('disaster_stormsurge', '高潮'),
        ('disaster_earthquake', '地震'),
        ('disaster_tsunami', '津波'),
        ('disaster_large_scale_fire', '大規模な火事'),
        ('disaster_inland_flooding', '内水氾濫'),
        ('disaster_volcanicactivity', '火山現象'),
    ]

    result = []

    for row in rows:
        disasters = []

        for column, label in disaster_labels:
            if row[column]:
                disasters.append(label)

        result.append({
            'id': row['id'],
            'name': row['name'],
            'address': row['address'] or '',
            'prefecture': row['prefecture'] or '',
            'city': row['city'] or '',
            'capacity': row['capacity'],
            'disasters': disasters,
            'is_active': bool(row['is_active'])
        })

    return jsonify({
        'shelters': result,
        'count': len(result)
    })
