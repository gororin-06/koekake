"""避難所オープンデータ（CSV）の取り込み。起動時に1回だけ走らせる。

CSVは千葉県の指定緊急避難場所。表記ゆれ（想定収容人数・災害種別フラグ）を
_cap_to_int / _to_flag で正規化してから shelters テーブルへ入れる。
"""
import os
import csv

from db import get_db


def _cap_to_int(v):
    """想定収容人数の表記ゆれを整数に。'8,889人（敷地面積…）'→8889、空/不明→0"""
    if not v:
        return 0
    digits = ''
    for ch in str(v):
        if ch.isdigit():
            digits += ch
        elif ch == ',':
            continue
        else:
            break  # 先頭の数値だけ採用
    return int(digits) if digits else 0


def _to_flag(v):
    """災害種別列の表記ゆれを 1/0 に。'1'/'○'/'〇' 等→1、'※1'・空など→0"""
    return 1 if str(v).strip() in ('1', '○', '〇', '◯', 'TRUE', 'True') else 0


def import_shelters():
    csv_path = os.environ.get(
        'KOEKAKE_SHELTER_CSV',
        '/app/hinan-list.csv'
    )

    if not os.path.exists(csv_path):
        print(f'避難所CSVがありません: {csv_path}')
        return

    db = get_db()

    # すでにデータがあるなら二重登録しない
    count = db.execute(
        "SELECT COUNT(*) AS c FROM shelters"
    ).fetchone()['c']

    if count > 0:
        print(f'避難所データは既に {count} 件あります')
        return

    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)

        imported = 0

        for row in reader:
            db.execute("""
                INSERT INTO shelters (
                    id,
                    name,
                    address,
                    prefecture,
                    city,
                    disaster_flood,
                    disaster_landslide_etc,
                    disaster_stormsurge,
                    disaster_earthquake,
                    disaster_tsunami,
                    disaster_large_scale_fire,
                    disaster_inland_flooding,
                    disaster_volcanicactivity,
                    is_active,
                    capacity
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['NO']),
                row['名称'],
                row['住所'],
                row['都道府県名'],
                row['市区町村名'],
                _to_flag(row['災害種別_洪水']),
                _to_flag(row['災害種別_崖崩れ、土石流及び地滑り']),
                _to_flag(row['災害種別_高潮']),
                _to_flag(row['災害種別_地震']),
                _to_flag(row['災害種別_津波']),
                _to_flag(row['災害種別_大規模な火事']),
                _to_flag(row['災害種別_内水氾濫']),
                _to_flag(row['災害種別_火山現象']),
                0,  # is_active は管理者が選択する運用状態。CSVの重複フラグは使わない
                _cap_to_int(row['想定収容人数']),
            ))

            imported += 1

    db.commit()

    print(f'避難所データを {imported} 件登録しました')
