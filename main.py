
# インストールしたパッケージのインポート
from flask import Flask, render_template

# appという名前でFlaskのインスタンスを作成
# テンプレートフォルダをapp/htdocsに指定
app = Flask(__name__, template_folder='app/htdocs')


@app.route('/')
def hello_world():
    return render_template('index.html')

if __name__ == '__main__':
    # 作成したappを起動
    # ここでflaskの起動が始まる
    app.run(host='0.0.0.0', port=5000)
