(function () {
    var PRESETS = {
        sos: ['水がほしい', '食べ物がほしい', '毛布がほしい', '日用品がほしい'],
        health: ['体調がわるい', 'くすりがほしい', 'ケガをした', '熱がある'],
        child: ['粉ミルクがほしい', 'おむつがほしい', '離乳食がほしい', '子どもが泣きやまない'],
        info: ['ゆずれるものがあります', 'お手伝いできます', 'おしらせがあります']
    };

    var sheet = document.getElementById('sheet');
    var step1 = document.getElementById('step1');
    var step2 = document.getElementById('step2');
    var stepLabel = document.getElementById('stepLabel');
    var presetBox = document.getElementById('presets');
    var freeBody = document.getElementById('freeBody');
    var locInput = document.getElementById('loc');
    var btnSend = document.getElementById('btnSend');
    var toast = document.getElementById('toast');

    var category = null;
    var selected = null;

    // 端末を識別するトークン。認証の代わり
    function getToken() {
        try {
            var t = localStorage.getItem('koekake_token');
            if (!t) {
                t = 'tk-' + Date.now() + '-' + Math.random().toString(36).slice(2);
                localStorage.setItem('koekake_token', t);
            }
            return t;
        } catch (e) {
            // プライベートブラウズ等。セッション内だけの一時トークン
            if (!window._tmpToken) {
                window._tmpToken = 'tmp-' + Math.random().toString(36).slice(2);
            }
            return window._tmpToken;
        }
    }

    // 自分が投稿したIDを覚えておく。本人判定に使う（トークンはHTMLに出さない）
    function loadMyPosts() {
        try {
            var raw = localStorage.getItem('koekake_posts');
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return window._tmpPosts || [];
        }
    }
    function addMyPost(id) {
        if (!id) return;
        var arr = loadMyPosts();
        if (arr.indexOf(id) === -1) arr.push(id);
        try {
            localStorage.setItem('koekake_posts', JSON.stringify(arr));
        } catch (e) {
            window._tmpPosts = arr;
        }
    }
    function isMine(id) {
        return loadMyPosts().indexOf(parseInt(id, 10)) !== -1;
    }

    function saveLoc(v) {
        try { localStorage.setItem('koekake_loc', v); } catch (e) { }
    }
    function loadLoc() {
        try { return localStorage.getItem('koekake_loc') || ''; } catch (e) { return ''; }
    }

    function showToast(msg) {
        toast.textContent = msg;
        toast.hidden = false;
        setTimeout(function () { toast.hidden = true; }, 4000);
    }

    function openSheet() {
        category = null;
        selected = null;
        step1.hidden = false;
        step2.hidden = true;
        stepLabel.textContent = 'ステップ 1 / 2';
        locInput.value = loadLoc();
        freeBody.value = '';
        sheet.classList.add('open');
    }

    function closeSheet() {
        sheet.classList.remove('open');
    }

    document.getElementById('btnOpen').addEventListener('click', openSheet);

    document.getElementById('btnBack').addEventListener('click', function () {
        if (step2.hidden) {
            closeSheet();
        } else {
            step1.hidden = false;
            step2.hidden = true;
            stepLabel.textContent = 'ステップ 1 / 2';
        }
    });

    // ステップ1 → ステップ2
    var cats = document.querySelectorAll('.cat');
    for (var i = 0; i < cats.length; i++) {
        cats[i].addEventListener('click', function () {
            category = this.getAttribute('data-cat');
            selected = null;

            presetBox.innerHTML = '';
            var list = PRESETS[category];
            for (var j = 0; j < list.length; j++) {
                var b = document.createElement('button');
                b.type = 'button';
                b.className = 'preset';
                b.textContent = list[j];
                b.addEventListener('click', function () {
                    var all = presetBox.querySelectorAll('.preset');
                    for (var k = 0; k < all.length; k++) all[k].classList.remove('on');
                    this.classList.add('on');
                    selected = this.textContent;
                    freeBody.value = '';
                });
                presetBox.appendChild(b);
            }

            step1.hidden = true;
            step2.hidden = false;
            stepLabel.textContent = 'ステップ 2 / 2';
        });
    }

    // 送信
    btnSend.addEventListener('click', function () {
        var body = freeBody.value.trim() || selected;
        if (!body) {
            showToast('つたえる内容をえらんでください');
            return;
        }

        // 連打で二重投稿されないよう即ロック
        btnSend.disabled = true;
        btnSend.textContent = '送信中...';

        var loc = locInput.value.trim();
        if (loc) saveLoc(loc);

        var payload = {
            category: category,
            body: body,
            location: loc,
            token: getToken()
        };

        // 管理者モードで「本部として投稿」にチェックがあれば、キーごと送る
        var asAdmin = document.getElementById('asAdmin');
        if (asAdmin && asAdmin.checked) {
            payload.is_admin = 1;
            payload.key = urlKey();
        }

        fetch('/api/posts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (res) {
            if (!res.ok) throw new Error('failed');
            return res.json();
        }).then(function (data) {
            addMyPost(data.id);
            location.reload();
        }).catch(function () {
            btnSend.disabled = false;
            btnSend.textContent = '送信する';
            showToast('送信できませんでした。もう一度おしてください');
        });
    });

    // 解決トグル
    var acts = document.querySelectorAll('.resolve');
    for (var n = 0; n < acts.length; n++) {
        var btn = acts[n];

        // 自分の投稿でなければ押せない
        if (!isMine(btn.getAttribute('data-id'))) {
            btn.disabled = true;
            continue;
        }

        btn.addEventListener('click', function () {
            var id = this.getAttribute('data-id');
            this.disabled = true;

            fetch('/api/posts/' + id + '/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: getToken() })
            }).then(function (res) {
                if (!res.ok) throw new Error('failed');
                location.reload();
            }).catch(function () {
                showToast('うまくいきませんでした');
            });
        });
    }

    // 返信フォームの開閉
    var rbtns = document.querySelectorAll('.reply');
    for (var a = 0; a < rbtns.length; a++) {
        rbtns[a].addEventListener('click', function () {
            var box = document.getElementById('rf-' + this.getAttribute('data-id'));
            box.hidden = !box.hidden;
            if (!box.hidden) box.querySelector('textarea').focus();
        });
    }

    // 新着チェック（差分検知のみ・描画はリロードに任せる）
    // タイマーは持たず、画面に戻ってきた時だけ確認する＝端末の電力を極力使わない
    var newbar = document.getElementById('newbar');
    var newbarBtn = document.getElementById('newbarBtn');
    var newCount = document.getElementById('newCount');
    var sinceId = parseInt(document.body.getAttribute('data-since'), 10) || 0;

    if (newbar && newbarBtn) {
        var checking = false;

        function checkNew() {
            if (checking) return;
            checking = true;
            fetch('/api/posts?since=' + sinceId).then(function (res) {
                if (!res.ok) throw new Error('failed');
                return res.json();
            }).then(function (data) {
                checking = false;
                if (data.count > 0) {
                    newCount.textContent = data.count;
                    newbar.hidden = false;
                }
            }).catch(function () {
                checking = false;
                // オフライン等は黙って次の機会を待つ（エラー表示はしない）
            });
        }

        newbarBtn.addEventListener('click', function () {
            location.reload();
        });

        // アプリに戻ってきた／画面が点いた瞬間に一度だけ確認
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'visible') checkNew();
        });

        // 開いた直後に一度（描画とJS初期化の隙間に届いた分を拾う）
        checkNew();
    }

    // 管理者操作（?key=... で開いたときだけボタンがDOMに存在する）
    // キーは管理者のURLにあるので、そこから読む（通常ユーザーのDOMには出さない）
    function urlKey() {
        try {
            var m = location.search.match(/[?&]key=([^&]+)/);
            return m ? decodeURIComponent(m[1]) : '';
        } catch (e) {
            return '';
        }
    }

    function adminAction(btn, path, confirmMsg) {
        if (confirmMsg && !window.confirm(confirmMsg)) return;
        var id = btn.getAttribute('data-id');
        btn.disabled = true;
        fetch('/api/posts/' + id + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: urlKey() })
        }).then(function (res) {
            if (!res.ok) throw new Error('failed');
            location.reload();
        }).catch(function () {
            btn.disabled = false;
            showToast('うまくいきませんでした');
        });
    }

    var pinBtns = document.querySelectorAll('.adm-btn.pin');
    for (var pi = 0; pi < pinBtns.length; pi++) {
        pinBtns[pi].addEventListener('click', function () {
            adminAction(this, '/pin', null);
        });
    }

    var delBtns = document.querySelectorAll('.adm-btn.del');
    for (var di = 0; di < delBtns.length; di++) {
        delBtns[di].addEventListener('click', function () {
            adminAction(this, '/delete', 'この投稿を削除します。よろしいですか？');
        });
    }

    // カテゴリタブのフィルタ（表示中の投稿を種類でしぼる。サーバー往復なし）
    var tabs = document.querySelectorAll('.tab');
    var timelinePosts = document.querySelectorAll('.post');
    var filterEmpty = document.getElementById('filterEmpty');

    function applyFilter(f) {
        var shown = 0;
        for (var i = 0; i < timelinePosts.length; i++) {
            var match = (f === 'all') || (timelinePosts[i].getAttribute('data-cat') === f);
            timelinePosts[i].hidden = !match;
            if (match) shown++;
        }
        // 「すべて」以外で1件も無いときだけ空表示を出す
        if (filterEmpty) filterEmpty.hidden = (f === 'all' || shown > 0);
    }

    for (var tb = 0; tb < tabs.length; tb++) {
        tabs[tb].addEventListener('click', function () {
            for (var m = 0; m < tabs.length; m++) tabs[m].classList.remove('on');
            this.classList.add('on');
            applyFilter(this.getAttribute('data-filter'));
        });
    }

    // 返信の送信
    var sbtns = document.querySelectorAll('.send-reply');
    for (var b2 = 0; b2 < sbtns.length; b2++) {
        sbtns[b2].addEventListener('click', function () {
            var id = this.getAttribute('data-id');
            var ta = document.getElementById('rf-' + id).querySelector('textarea');
            var text = ta.value.trim();

            if (!text) {
                showToast('こたえを かいてください');
                return;
            }

            this.disabled = true;
            this.textContent = '送信中...';
            var self = this;

            fetch('/api/posts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    parent_id: parseInt(id, 10),
                    category: 'info',
                    body: text,
                    location: loadLoc(),
                    token: getToken()
                })
            }).then(function (res) {
                if (!res.ok) throw new Error('failed');
                return res.json();
            }).then(function (data) {
                addMyPost(data.id);
                location.reload();
            }).catch(function () {
                self.disabled = false;
                self.textContent = '送信する';
                showToast('送信できませんでした。もう一度おしてください');
            });
        });
    }
})();