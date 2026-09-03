import csv
import os
import sqlite3

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')
CSV_PATH = 'hinan-list.csv'

# CSVの列名 → DBのカラム名
DISASTERS = {
    '災害種別_洪水': 'disaster_flood',
    '災害種別_崖崩れ、土石流及び地滑り': 'disaster_landslide_etc',
    '災害種別_高潮': 'disaster_stormsurge',
    '災害種別_地震': 'disaster_earthquake',
    '災害種別_津波': 'disaster_tsunami',
    '災害種別_大規模な火事': 'disaster_large_scale_fire',
    '災害種別_内水氾濫': 'disaster_inland_flooding',
    '災害種別_火山現象': 'disaster_volcanicactivity',
}


def to_flag(v):
    """CSVの表記ゆれを 1/0 に寄せる"""
    return 1 if str(v).strip() in ('1', '○', '〇', '◯', 'TRUE', 'True') else 0


def to_int(v):
    try:
        return int(str(v).replace(',', '').strip())
    except (ValueError, AttributeError):
        return None


def load_csv():
    for enc in ('utf-8-sig', 'cp932'):
        try:
            with open(CSV_PATH, encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError('CSVの文字コードを判別できませんでした')


def main():
    rows = load_csv()
    conn = sqlite3.connect(DB_PATH)

    # 何度実行しても同じ結果になるよう、一度空にする
    conn.execute('DELETE FROM shelters')

    cols = ['name', 'address', 'prefecture', 'city', 'capacity'] + list(DISASTERS.values())
    sql = 'INSERT INTO shelters ({}) VALUES ({})'.format(
        ', '.join(cols), ', '.join('?' * len(cols))
    )

    n = 0
    for r in rows:
        values = [
            r.get('名称'),
            r.get('住所'),
            r.get('都道府県名'),
            r.get('市区町村名'),
            to_int(r.get('想定収容人数')),
        ] + [to_flag(r.get(k)) for k in DISASTERS]
        conn.execute(sql, values)
        n += 1

    conn.commit()
    print(f'{n} 件を取り込みました')

    # 市区町村ごとの件数を確認
    for city, cnt in conn.execute(
        'SELECT city, COUNT(*) FROM shelters GROUP BY city ORDER BY COUNT(*) DESC LIMIT 10'
    ):
        print(f'  {city}: {cnt}')

    conn.close()


if __name__ == '__main__':
    main()