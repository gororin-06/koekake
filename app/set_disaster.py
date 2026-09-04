"""今回の災害種別を設定する

  python set_disaster.py tsunami
  python set_disaster.py          ← 一覧と現在値を表示

  python set_disaster.py --hide   ← 適合バナーを画面から隠す
  python set_disaster.py --show   ← 適合バナーを表示に戻す（既定）

災害種別の記録は残したまま、バナーの表示だけを管理者が切り替えられる。
非指定の避難所を意図的に開設していて、避難者を不安にさせたくない場合に使う。
"""
import os
import sqlite3
import sys

DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')

TYPES = {
    'flood':      ('disaster_flood', '洪水'),
    'landslide':  ('disaster_landslide_etc', '崖崩れ・土石流・地滑り'),
    'stormsurge': ('disaster_stormsurge', '高潮'),
    'earthquake': ('disaster_earthquake', '地震'),
    'tsunami':    ('disaster_tsunami', '津波'),
    'fire':       ('disaster_large_scale_fire', '大規模な火事'),
    'inland':     ('disaster_inland_flooding', '内水氾濫'),
    'volcano':    ('disaster_volcanicactivity', '火山現象'),
}


def main():
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=5000')

    arg = sys.argv[1] if len(sys.argv) >= 2 else None

    if arg is None:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = 'disaster_type'"
        ).fetchone()
        cur = row['value'] if row else '(未設定)'
        brow = conn.execute(
            "SELECT value FROM settings WHERE key = 'disaster_banner'"
        ).fetchone()
        banner = '非表示' if brow and brow['value'] == 'off' else '表示'
        print(f'現在: {cur}')
        print(f'バナー: {banner}\n')
        print('指定できる種別:')
        for k, (_, label) in TYPES.items():
            print(f'  {k:<11} {label}')
        conn.close()
        return

    if arg in ('--hide', '--show'):
        value = 'off' if arg == '--hide' else 'on'
        conn.execute(
            "INSERT INTO settings (key, value) VALUES ('disaster_banner', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (value,)
        )
        conn.commit()
        msg = '隠しました（画面には出ません）' if value == 'off' else '表示に戻しました'
        print(f'適合バナーを{msg}')
        conn.close()
        return

    key = arg
    if key not in TYPES:
        print(f'「{key}」は無効です。引数なしで実行すると一覧が出ます')
        conn.close()
        return

    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('disaster_type', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key,)
    )
    conn.commit()

    col, label = TYPES[key]
    print(f'災害種別を「{label}」に設定しました')

    row = conn.execute('SELECT name, ' + col + ' AS ok FROM shelters WHERE is_active = 1').fetchone()
    if row is None:
        print('  ※ アクティブな避難所が未設定です（set_shelter.py で指定してください）')
    elif row['ok']:
        print(f'  {row["name"]} は {label} に対応しています（緑の確認表示）')
    else:
        print(f'  {row["name"]} は {label} に対応していません（赤の警告が出ます）')

    brow = conn.execute(
        "SELECT value FROM settings WHERE key = 'disaster_banner'"
    ).fetchone()
    if brow and brow['value'] == 'off':
        print('  ※ 現在バナーは非表示です（--show で表示に戻せます）')

    conn.close()


if __name__ == '__main__':
    main()