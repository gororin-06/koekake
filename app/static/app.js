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
    var selectedList = [];

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
        selectedList = [];
        step1.hidden = false;
        step2.hidden = true;
        stepLabel.textContent = 'ステップ 1 / 2';
        locInput.value = loadLoc();
        freeBody.value = '';
        // 品目・数量は前回の値を持ち越さない（別の投稿に紛れ込むのを防ぐ）
        var itemEl = document.getElementById('item');
        if (itemEl) itemEl.value = '';
        var qtyEl = document.getElementById('qty');
        if (qtyEl) qtyEl.value = '';
        sheet.classList.add('open');
    }

    function closeSheet() {
        sheet.classList.remove('open');
    }

    // セットアップ画面では投稿系の要素が無いので、存在するときだけ配線する
    var btnOpen = document.getElementById('btnOpen');
    if (btnOpen) btnOpen.addEventListener('click', openSheet);

    var btnBack = document.getElementById('btnBack');
    if (btnBack) btnBack.addEventListener('click', function () {
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
            var raw = this.getAttribute('data-cat');
            var isOther = (raw === 'other');
            category = raw;  // その他は専用カテゴリ 'other' として保存（おしらせと区別）
            selectedList = [];

            presetBox.innerHTML = '';
            var list = isOther ? [] : (PRESETS[category] || []);
            for (var j = 0; j < list.length; j++) {
                var b = document.createElement('button');
                b.type = 'button';
                b.className = 'preset';
                b.textContent = list[j];
                b.addEventListener('click', function () {
                    this.classList.toggle('on');  // 複数選択（トグル）
                    var on = presetBox.querySelectorAll('.preset.on');
                    selectedList = [];
                    for (var k = 0; k < on.length; k++) selectedList.push(on[k].textContent);
                });
                presetBox.appendChild(b);
            }

            step1.hidden = true;
            step2.hidden = false;
            stepLabel.textContent = 'ステップ 2 / 2';

            // その他：定型文なし → 自由記述を開いてフォーカス
            if (isOther) {
                var det = document.querySelector('.freewrite');
                if (det) det.open = true;
                if (freeBody) freeBody.focus();
            }
        });
    }

    // 送信
    if (btnSend) btnSend.addEventListener('click', function () {
        // 選んだ定型文（複数可）＋自由記述をまとめる
        var free = freeBody.value.trim();
        var parts = selectedList.slice();
        if (free) parts.push(free);
        var body = parts.join('、');
        if (!body) {
            showToast('つたえる内容をえらんでください');
            return;
        }

        var loc = locInput.value.trim();
        var asAdmin = document.getElementById('asAdmin');
        var adminChecked = asAdmin && asAdmin.checked;
        // 場所は必須（本部として投稿のときは除く）
        if (!adminChecked && !loc) {
            showToast('いまいる場所を入力してください');
            locInput.focus();
            return;
        }

        // 品目・数量（任意）を本文に併記。両方あれば「品目: 水、数量: 3本」の形にまとめる
        var itemEl = document.getElementById('item');
        var item = itemEl ? itemEl.value.trim() : '';
        var qtyEl = document.getElementById('qty');
        var qty = qtyEl ? qtyEl.value.trim() : '';
        var extra = [];
        if (item) extra.push('品目: ' + item);
        if (qty) extra.push('数量: ' + qty);
        if (extra.length) body = body + '（' + extra.join('、') + '）';

        // 連打で二重投稿されないよう即ロック
        btnSend.disabled = true;
        btnSend.textContent = '送信中...';

        if (loc) saveLoc(loc);

        var payload = {
            category: category,
            body: body,
            location: loc,
            token: getToken()
        };

        // 管理者モードで「本部として投稿」にチェックがあれば、キーごと送る
        if (adminChecked) {
            payload.is_admin = 1;
            payload.key = urlKey();
        }

        fetch('/api/posts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        }).then(function (res) {
            if (res.status === 429) throw new Error('too_fast');
            if (!res.ok) throw new Error('failed');
            return res.json();
        }).then(function (data) {
            addMyPost(data.id);
            location.reload();
        }).catch(function (err) {
            btnSend.disabled = false;
            btnSend.textContent = '送信する';
            showToast(err && err.message === 'too_fast'
                ? '短い間に投稿しすぎです。少し待ってからお願いします'
                : '送信できませんでした。もう一度おしてください');
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

    // リアクション（助かった／確認した）。1端末1回、localStorageでトグル。その場で数だけ更新
    function loadReactions() {
        try {
            var raw = localStorage.getItem('koekake_reactions');
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            return window._tmpReactions || {};
        }
    }
    function saveReactions(obj) {
        try {
            localStorage.setItem('koekake_reactions', JSON.stringify(obj));
        } catch (e) {
            window._tmpReactions = obj;
        }
    }

    var reactBtns = document.querySelectorAll('.react-btn');
    var myReactions = loadReactions();
    for (var ri = 0; ri < reactBtns.length; ri++) {
        var rb = reactBtns[ri];
        if (myReactions[rb.getAttribute('data-id') + ':' + rb.getAttribute('data-type')]) {
            rb.classList.add('on');
        }
        rb.addEventListener('click', function () {
            var id = this.getAttribute('data-id');
            var type = this.getAttribute('data-type');
            var key = id + ':' + type;
            var op = this.classList.contains('on') ? 'remove' : 'add';
            var btn = this;
            var countEl = btn.querySelector('.react-count');
            btn.disabled = true;
            fetch('/api/posts/' + id + '/react', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: type, op: op })
            }).then(function (res) {
                if (!res.ok) throw new Error('failed');
                return res.json();
            }).then(function (data) {
                btn.disabled = false;
                if (countEl) countEl.textContent = data.count;
                var store = loadReactions();
                if (op === 'add') { btn.classList.add('on'); store[key] = true; }
                else { btn.classList.remove('on'); delete store[key]; }
                saveReactions(store);
            }).catch(function () {
                btn.disabled = false;
                showToast('うまくいきませんでした');
            });
        });
    }

    // 返信スレッドの開閉（既定は非表示）
    var replyToggles = document.querySelectorAll('.reply-toggle');
    for (var rtg = 0; rtg < replyToggles.length; rtg++) {
        replyToggles[rtg].addEventListener('click', function () {
            var id = this.getAttribute('data-id');
            var thread = document.getElementById('thread-' + id);
            if (!thread) return;
            thread.hidden = !thread.hidden;
            var n = this.getAttribute('data-count') || '';
            this.textContent = thread.hidden ? ('▼ 返信 ' + n + '件') : '▲ 返信を非表示';
        });
    }

    // 返信フォームの開閉
    var rbtns = document.querySelectorAll('.reply');
    for (var a = 0; a < rbtns.length; a++) {
        rbtns[a].addEventListener('click', function () {
            var box = document.getElementById('rf-' + this.getAttribute('data-id'));
            box.hidden = !box.hidden;
            if (!box.hidden) {
                var rl = box.querySelector('.reply-loc');
                if (rl && !rl.value) rl.value = loadLoc();  // 前回の場所を初期値に
                box.querySelector('textarea').focus();
            }
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

        // 表示中は数秒ごとに新着を確認 → 誰かが投稿したら「更新」バーが出る。
        // 画面が見えているときだけ通信し、自動リロードはしない（読んでいる途中を邪魔しない・省電力）
        setInterval(function () {
            if (document.visibilityState === 'visible') checkNew();
        }, 3000);

        // 開いた直後に一度（描画とJS初期化の隙間に届いた分を拾う）
        checkNew();
    }

    // 3分ごとに強制更新（入力中・投稿画面を開いている間はスキップ）
    setInterval(function () {
        if (sheet && sheet.classList.contains('open')) return;
        var el = document.activeElement;
        if (el && (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT')) return;
        location.reload();
    }, 300000);

    // 接続端末数（ハートビート）。30秒ごと＋復帰時に生存報告し、直近の接続数を表示。
    // 画面が見えている間だけ送る＝離れた端末は90秒で自動的に数から外れる（正確・省電力）
    var sessionEl = document.getElementById('sessionCount');
    if (sessionEl) {
        var sendHeartbeat = function () {
            fetch('/api/heartbeat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: getToken() })
            }).then(function (res) {
                return res.ok ? res.json() : null;
            }).then(function (data) {
                if (data && typeof data.sessions === 'number') sessionEl.textContent = data.sessions;
            }).catch(function () { });
        };
        sendHeartbeat();
        setInterval(function () {
            if (document.visibilityState === 'visible') sendHeartbeat();
        }, 30000);
        document.addEventListener('visibilitychange', function () {
            if (document.visibilityState === 'visible') sendHeartbeat();
        });
    }      //戻す

    // 300000

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

    // 管理者ツール パネル（管理者モードのみ）
    var debugToggle = document.getElementById('debugToggle');
    var debugPanel = document.getElementById('debugPanel');
    if (debugToggle && debugPanel) {
        debugToggle.addEventListener('click', function () {
            debugPanel.hidden = !debugPanel.hidden;
        });
    }

    var DEBUG_MSG = {
        change_shelter: '避難所の選択画面に戻ります。よろしいですか？',
        seed: 'テストデータを入れ直します（いまの投稿は置き換わります）。よろしいですか？',
        clear_posts: 'すべての投稿を削除します。元に戻せません。よろしいですか？',
        reset: '投稿もふくめて完全に初期化します（避難所・設定・投稿がすべて消えます）。元に戻せません。よろしいですか？'
    };

    var debugBtns = document.querySelectorAll('.debug-btn[data-debug]');
    for (var dbi = 0; dbi < debugBtns.length; dbi++) {
        debugBtns[dbi].addEventListener('click', function () {
            var action = this.getAttribute('data-debug');
            if (!window.confirm(DEBUG_MSG[action] || '実行しますか？')) return;
            this.disabled = true;
            fetch('/api/debug', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: urlKey(), action: action })
            }).then(function (res) {
                if (!res.ok) throw new Error('failed');
                location.reload();
            }).catch(function () {
                showToast('うまくいきませんでした');
            });
        });
    }

    // 利用者用アクセス（QR＋アドレス）。管理用の ?key= を含まない、避難者向けの入口を作る。
    // 自動検出は Docker→ホストの仮想ルータIP（例 172.19.0.2）になり不正確なため廃止。
    // 「この端末のIPを手入力 → 生成＆表示ボタン」の完全手動フローにする。
    var showAccessBtn = document.getElementById('showAccessBtn');
    var accessPanel = document.getElementById('accessPanel');
    if (showAccessBtn && accessPanel) {
        var accessClose = document.getElementById('accessClose');
        var urlEl = document.getElementById('accessUrl');
        var canvas = document.getElementById('accessQr');
        var ipInput = document.getElementById('accessIp');
        var applyBtn = document.getElementById('accessApply');
        var resultEl = document.getElementById('accessResult');
        var accessPort = location.port;  // 管理者が使っているポート＝公開ポート＝スマホも同じ

        function isLanIp(h) {
            return /^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})$/.test(h);
        }
        function buildUrl(host) {
            return location.protocol + '//' + host + (accessPort ? ':' + accessPort : '') + '/';
        }
        // 入力されたIPからQR＋アドレスを作って表示する（ボタン/Enterで押したときだけ動く）
        function generate() {
            var ip = ipInput ? ipInput.value.trim() : '';
            if (!isLanIp(ip)) {
                showToast('IPアドレスの形を確認してください（例: 192.168.137.1）');
                return;
            }
            var url = buildUrl(ip);
            if (urlEl) urlEl.textContent = url;
            if (canvas && typeof KoekakeQR !== 'undefined') {
                var ok = KoekakeQR.draw(url, canvas, 6, 4);
                if (!ok) showToast('QRを作れませんでした。アドレスを直接お伝えください');
            }
            if (resultEl) resultEl.hidden = false;  // 生成できたら結果を表示
        }

        showAccessBtn.addEventListener('click', function () {
            accessPanel.hidden = false;
            accessPanel.scrollIntoView(false);
            // 開くたびに前回の結果は隠す。自動生成・自動検出はしない（IPを入れてボタンを押すまで何も出さない）
            if (resultEl) resultEl.hidden = true;
        });

        if (applyBtn) applyBtn.addEventListener('click', generate);
        // 入力欄で Enter でも生成できる
        if (ipInput) ipInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.keyCode === 13) { e.preventDefault(); generate(); }
        });
        if (accessClose) {
            accessClose.addEventListener('click', function () {
                accessPanel.hidden = true;
            });
        }
    }

    // 自分の投稿の編集（インライン）。自分の投稿だけボタンを表示
    var editBtns = document.querySelectorAll('.act.edit');
    for (var edi = 0; edi < editBtns.length; edi++) {
        var edb = editBtns[edi];
        if (!isMine(edb.getAttribute('data-id'))) continue;
        edb.hidden = false;
        edb.addEventListener('click', function () {
            var id = this.getAttribute('data-id');
            var post = this.closest('.post');
            var bodyEl = post ? post.querySelector('.body') : null;
            if (!bodyEl || post.querySelector('.edit-box')) return;

            var current = bodyEl.textContent.trim();
            var box = document.createElement('div');
            box.className = 'edit-box';
            var ta = document.createElement('textarea');
            ta.rows = 3;
            ta.value = current;
            var actRow = document.createElement('div');
            actRow.className = 'edit-actions';
            var save = document.createElement('button');
            save.type = 'button';
            save.className = 'edit-save';
            save.textContent = '保存';
            var cancel = document.createElement('button');
            cancel.type = 'button';
            cancel.className = 'edit-cancel';
            cancel.textContent = 'やめる';
            actRow.appendChild(save);
            actRow.appendChild(cancel);
            box.appendChild(ta);
            box.appendChild(actRow);
            bodyEl.hidden = true;
            bodyEl.parentNode.insertBefore(box, bodyEl.nextSibling);
            ta.focus();

            cancel.addEventListener('click', function () {
                box.parentNode.removeChild(box);
                bodyEl.hidden = false;
            });
            save.addEventListener('click', function () {
                var text = ta.value.trim();
                if (!text) {
                    showToast('内容を入力してください');
                    return;
                }
                save.disabled = true;
                fetch('/api/posts/' + id + '/edit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: getToken(), body: text })
                }).then(function (res) {
                    if (!res.ok) throw new Error('failed');
                    return res.json();
                }).then(function () {
                    bodyEl.textContent = text;
                    box.parentNode.removeChild(box);
                    bodyEl.hidden = false;
                }).catch(function () {
                    save.disabled = false;
                    showToast('編集できませんでした');
                });
            });
        });
    }

    // 避難所情報オーバーレイ（左上タップで開く）
    var shelterInfo = document.getElementById('shelterInfo');
    var shelterInfoBtn = document.getElementById('shelterInfoBtn');
    if (shelterInfo && shelterInfoBtn) {
        shelterInfoBtn.addEventListener('click', function () {
            shelterInfo.hidden = false;
        });
        var infoClosers = shelterInfo.querySelectorAll('#shelterInfoClose, #shelterInfoClose2');
        for (var ic = 0; ic < infoClosers.length; ic++) {
            infoClosers[ic].addEventListener('click', function () {
                shelterInfo.hidden = true;
            });
        }
        shelterInfo.addEventListener('click', function (e) {
            if (e.target === shelterInfo) shelterInfo.hidden = true;  // 背景タップで閉じる
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

    // もっと見る：?show= を増やしてサーバーに追加分を描画させる。
    // 全体を読み直す＝新しい投稿のボタンも通常どおり配線される（部分描画の配線漏れを避ける）。
    // 読み込み前のスクロール位置を覚えておき、読み込み後に同じ位置へ戻す（上に飛ばさない）。
    var loadMore = document.getElementById('loadMore');
    if (loadMore) {
        loadMore.addEventListener('click', function () {
            var next = this.getAttribute('data-next');
            try { sessionStorage.setItem('koekake_scroll', String(window.pageYOffset || 0)); } catch (e) { }
            this.disabled = true;
            this.textContent = '読み込み中...';
            var key = urlKey();
            var href = location.pathname + '?show=' + encodeURIComponent(next);
            if (key) href += '&key=' + encodeURIComponent(key);
            location.assign(href);
        });
    }

    // 「もっと見る」直後だけ、元のスクロール位置に戻す（追加分は下に増えるので位置は保てる）
    try {
        var savedScroll = sessionStorage.getItem('koekake_scroll');
        if (savedScroll !== null) {
            sessionStorage.removeItem('koekake_scroll');
            window.scrollTo(0, parseInt(savedScroll, 10) || 0);
        }
    } catch (e) { }

    // 返信の送信
    var sbtns = document.querySelectorAll('.send-reply');
    for (var b2 = 0; b2 < sbtns.length; b2++) {
        sbtns[b2].addEventListener('click', function () {
            var id = this.getAttribute('data-id');
            var form = document.getElementById('rf-' + id);
            var ta = form.querySelector('textarea');
            var locEl = form.querySelector('.reply-loc');
            var text = ta.value.trim();
            var rloc = locEl ? locEl.value.trim() : '';

            if (!text) {
                showToast('返信を かいてください');
                return;
            }
            if (!rloc) {
                showToast('あなたの場所を入力してください');
                if (locEl) locEl.focus();
                return;
            }
            saveLoc(rloc);

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
                    location: rloc,
                    token: getToken()
                })
            }).then(function (res) {
                if (res.status === 429) throw new Error('too_fast');
                if (!res.ok) throw new Error('failed');
                return res.json();
            }).then(function (data) {
                addMyPost(data.id);
                location.reload();
            }).catch(function (err) {
                self.disabled = false;
                self.textContent = '送信する';
                showToast(err && err.message === 'too_fast'
                    ? '短い間に投稿しすぎです。少し待ってからお願いします'
                    : '送信できませんでした。もう一度おしてください');
            });
        });
    }

    // ===== 初回セットアップ：災害 → 市町村 → 避難所（対応順・非対応は下位） =====
    var suStep1 = document.getElementById('suStep1');
    if (suStep1) {
        var suStep2 = document.getElementById('suStep2');
        var suStep3 = document.getElementById('suStep3');
        var citySearch = document.getElementById('citySearch');
        var cityResults = document.getElementById('cityResults');
        var suResults = document.getElementById('shelterResults');
        var shelterSearch = document.getElementById('shelterSearch');
        var su3lead = document.getElementById('su3lead');
        var suBack = document.getElementById('suBack');

        var selDisaster = '';
        var selDisasterLabel = '';
        var selCity = '';

        function suShow(n) {
            suStep1.hidden = (n !== 1);
            if (suStep2) suStep2.hidden = (n !== 2);
            if (suStep3) suStep3.hidden = (n !== 3);
            if (suBack) suBack.hidden = (n === 1);
        }

        // 避難所を確定（初回セットアップ端末は管理者モードを新しいタブで開く）
        function selectShelter(id, btn) {
            if (!window.confirm('この避難所を選択しますか？')) return;
            if (btn) btn.disabled = true;
            var adminTab = window.open('', '_blank');
            fetch('/api/shelters/' + id + '/select', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            }).then(function (res) {
                if (!res.ok) throw new Error('failed');
                return res.json();
            }).then(function (data) {
                if (data && data.admin_url) {
                    if (adminTab) adminTab.location = data.admin_url;
                    showSetupDone(data.admin_url, adminTab);
                } else {
                    if (adminTab) adminTab.close();
                    location.reload();
                }
            }).catch(function () {
                if (adminTab) adminTab.close();
                if (btn) btn.disabled = false;
                showToast('避難所を選択できませんでした');
            });
        }

        // 手順1：災害種別
        var disasterBtns = document.querySelectorAll('.disaster-btn');
        for (var d = 0; d < disasterBtns.length; d++) {
            disasterBtns[d].addEventListener('click', function () {
                selDisaster = this.getAttribute('data-disaster') || '';
                selDisasterLabel = this.getAttribute('data-label') || '';
                suShow(2);
                loadCities('');
                if (citySearch) { citySearch.value = ''; citySearch.focus(); }
            });
        }

        // 手順2：市区町村
        function loadCities(q) {
            fetch('/api/cities?q=' + encodeURIComponent(q))
                .then(function (res) { return res.ok ? res.json() : { cities: [] }; })
                .then(function (data) { renderCities(data.cities || []); })
                .catch(function () { renderCities([]); });
        }
        function renderCities(cities) {
            cityResults.innerHTML = '';
            if (!cities.length) {
                cityResults.innerHTML = '<div class="empty"><strong>市区町村が見つかりません</strong></div>';
                return;
            }
            for (var i = 0; i < cities.length; i++) {
                var b = document.createElement('button');
                b.type = 'button';
                b.className = 'city-btn';
                b.textContent = cities[i];
                b.addEventListener('click', function () {
                    selCity = this.textContent;
                    if (shelterSearch) shelterSearch.value = '';
                    suShow(3);
                    loadShelters();
                });
                cityResults.appendChild(b);
            }
        }
        if (citySearch) {
            citySearch.addEventListener('input', function () {
                loadCities(this.value.trim());
            });
        }

        // 手順3：避難所（対応順・非対応は下位に）
        function loadShelters() {
            su3lead.textContent = selCity + (selDisasterLabel ? '　（' + selDisasterLabel + 'に対応する避難所を上に表示）' : '');
            suResults.innerHTML = '<div class="shelter-search-status">読み込み中...</div>';
            var q = shelterSearch ? shelterSearch.value.trim() : '';
            var url = '/api/shelters?city=' + encodeURIComponent(selCity) +
                '&disaster=' + encodeURIComponent(selDisaster) +
                '&q=' + encodeURIComponent(q);
            fetch(url).then(function (res) { return res.ok ? res.json() : { shelters: [] }; })
                .then(function (data) { renderShelters(data.shelters || []); })
                .catch(function () {
                    suResults.innerHTML = '<div class="empty"><strong>取得できませんでした</strong></div>';
                });
        }
        if (shelterSearch) {
            shelterSearch.addEventListener('input', function () {
                loadShelters();
            });
        }
        function renderShelters(list) {
            suResults.innerHTML = '';
            if (!list.length) {
                var searching = shelterSearch && shelterSearch.value.trim();
                suResults.innerHTML = searching
                    ? '<div class="empty"><strong>その名前の避難所が見つかりません</strong>入力を消すと一覧にもどります</div>'
                    : '<div class="empty"><strong>この市区町村に避難所が見つかりません</strong></div>';
                return;
            }
            var dividerShown = false;
            for (var i = 0; i < list.length; i++) {
                var s = list[i];
                var incompatible = (s.is_compatible === false);
                if (incompatible && !dividerShown) {
                    var div = document.createElement('div');
                    div.className = 'shelter-divider';
                    div.textContent = 'この災害には指定されていない避難所';
                    suResults.appendChild(div);
                    dividerShown = true;
                }
                var card = document.createElement('button');
                card.type = 'button';
                card.className = 'shelter-result' + (incompatible ? ' incompatible' : '');
                card.setAttribute('data-id', s.id);

                var name = document.createElement('div');
                name.className = 'shelter-result-name';
                name.textContent = s.name || '名称不明';
                card.appendChild(name);

                if (s.is_compatible === true) {
                    var okb = document.createElement('span');
                    okb.className = 'compat-badge ok';
                    okb.textContent = '✓ ' + (selDisasterLabel || 'この災害') + 'に対応';
                    card.appendChild(okb);
                } else if (s.is_compatible === false) {
                    var ngb = document.createElement('span');
                    ngb.className = 'compat-badge ng';
                    ngb.textContent = selDisasterLabel + 'の指定なし';
                    card.appendChild(ngb);
                }

                if (s.address) {
                    var address = document.createElement('div');
                    address.className = 'shelter-address';
                    address.textContent = s.address;
                    card.appendChild(address);
                }
                if (s.capacity) {
                    var cap = document.createElement('div');
                    cap.className = 'shelter-capacity';
                    cap.textContent = '想定収容人数：' + s.capacity + '人';
                    card.appendChild(cap);
                }
                if (s.disasters && s.disasters.length > 0) {
                    var dz = document.createElement('div');
                    dz.className = 'shelter-disasters';
                    dz.textContent = '対応：' + s.disasters.join('・');
                    card.appendChild(dz);
                }
                (function (id, btn) {
                    btn.addEventListener('click', function () { selectShelter(id, btn); });
                })(s.id, card);
                suResults.appendChild(card);
            }
        }

        // もどる
        if (suBack) {
            suBack.addEventListener('click', function () {
                if (suStep3 && !suStep3.hidden) suShow(2);
                else if (suStep2 && !suStep2.hidden) suShow(1);
            });
        }

        suShow(1);
    }

    // 初回セットアップ完了時：管理者モードは新しいタブ、この画面はメッセージ表示
    function showSetupDone(adminUrl, adminTab) {
        var search = document.querySelector('.setup-wizard');
        if (search) search.hidden = true;
        var done = document.getElementById('setupDone');
        if (!done) return;
        done.hidden = false;
        // 新しいタブが開けなかったとき用に手動リンクを出す
        if (!adminTab || adminTab.closed) {
            var link = document.getElementById('setupDoneLink');
            var fb = document.getElementById('setupDoneFallback');
            if (link) link.href = adminUrl;
            if (fb) fb.hidden = false;
        }
    }

    var setupDoneBoard = document.getElementById('setupDoneBoard');
    if (setupDoneBoard) {
        setupDoneBoard.addEventListener('click', function () {
            location.href = '/';
        });
    }
})();