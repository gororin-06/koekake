"""アプリのエントリポイント（gunicorn は python.main:app を読む）。

このファイルは app/python/ パッケージ内にある。実行時のcwdは /app のままなので、
schema.sql / hinan-list.csv などの相対パスは従来どおり app/ 直下を指す。
ローカルで直接動かすときは app/ で `python -m python.main`（相対importのため）。


役割はここに集約：
  1. Flask アプリを生成
  2. DB接続のteardownを登録
  3. 各Blueprint（画面・避難所・投稿・管理者・システム）をまとめる
  4. 起動時にスキーマ適用＋避難所CSV取り込み

個々の処理は config / db / importer / services / views_*.py に分けてある。
どのファイルに何があるかは README / 部品対応表を参照。
"""
from flask import Flask

from .db import init_db, close_db
from .importer import import_shelters
from .views_pages import bp as pages_bp
from .views_shelters import bp as shelters_bp
from .views_posts import bp as posts_bp
from .views_admin import bp as admin_bp
from .views_system import bp as system_bp

# このパッケージ(python/)はappの1階層下なので、templates/static は親(app/)を指す
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# リクエスト終了ごとにDB接続を閉じる
app.teardown_appcontext(close_db)

# ルートをまとめて登録
app.register_blueprint(pages_bp)
app.register_blueprint(shelters_bp)
app.register_blueprint(posts_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(system_bp)

# 起動時：スキーマ適用 → 避難所CSV取り込み（既存データがあればスキップ）
init_db()
with app.app_context():
    import_shelters()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
