"""アプリ全体で使う定数・環境変数。ここだけ見れば設定値が分かる。"""
import os

# SQLite の実体。Docker名前付きボリュームで永続化される
DB_PATH = os.environ.get('KOEKAKE_DB', '/data/koekake.db')

# 投稿カテゴリ。API側のバリデーションに使う
# 'other'（その他）は定型文のない自由記述用。おしらせ(info)と区別して表示する
CATEGORIES = ('sos', 'health', 'child', 'info', 'other')

# 管理者キー。?key=... で照合する簡易認証。LAN内デモ用（本番運用向けではない）
ADMIN_KEY = os.environ.get('KOEKAKE_ADMIN_KEY', 'honbu')

# 連投防止：同一端末(token)の最短投稿間隔（秒）。管理者は除外
POST_COOLDOWN_SECONDS = 10

# settings.disaster_type のキー → (sheltersの列, 日本語ラベル)
DISASTER_TYPES = {
    'flood':      ('disaster_flood', '洪水'),
    'landslide':  ('disaster_landslide_etc', '崖崩れ・土石流・地滑り'),
    'stormsurge': ('disaster_stormsurge', '高潮'),
    'earthquake': ('disaster_earthquake', '地震'),
    'tsunami':    ('disaster_tsunami', '津波'),
    'fire':       ('disaster_large_scale_fire', '大規模な火事'),
    'inland':     ('disaster_inland_flooding', '内水氾濫'),
    'volcano':    ('disaster_volcanicactivity', '火山現象'),
}
