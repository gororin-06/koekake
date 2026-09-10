/* こえかけ QRコード生成（バイトモード・EC=M・版1〜10）
 * 外部リソースを一切読まない方針のため、自前で実装。
 * OpenCVのQRデコーダで各種URLがスキャン可能なことを検証済み（ES5相当）。
 * 使い方: KoekakeQR.draw(text, canvasEl, moduleSize)
 */
var KoekakeQR = (function () {
    'use strict';

    // レベルM・版1〜10のブロック構成 [ [ブロック数, 総符号数, データ符号数], ... ]
    var EC_BLOCKS_M = {
        1: [[1, 26, 16]], 2: [[1, 44, 28]], 3: [[1, 70, 44]],
        4: [[2, 50, 32]], 5: [[2, 67, 43]], 6: [[4, 43, 27]],
        7: [[4, 49, 31]], 8: [[2, 60, 38], [2, 61, 39]],
        9: [[3, 58, 36], [2, 59, 37]], 10: [[4, 69, 43], [1, 70, 44]]
    };
    var ALIGN = {
        1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
        6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46],
        10: [6, 28, 50]
    };

    // GF(256) 対数・逆対数テーブル（原始多項式 0x11d）
    var EXP = new Array(512);
    var LOG = new Array(256);
    (function () {
        var x = 1, i;
        for (i = 0; i < 255; i++) {
            EXP[i] = x;
            LOG[x] = i;
            x <<= 1;
            if (x & 0x100) x ^= 0x11d;
        }
        for (i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
    })();

    function gmul(a, b) {
        if (a === 0 || b === 0) return 0;
        return EXP[LOG[a] + LOG[b]];
    }

    function rsGenPoly(n) {
        var poly = [1], i, j;
        for (i = 0; i < n; i++) {
            var next = [];
            for (j = 0; j <= poly.length; j++) next[j] = 0;
            for (j = 0; j < poly.length; j++) {
                next[j] ^= poly[j];
                next[j + 1] ^= gmul(poly[j], EXP[i]);
            }
            poly = next;
        }
        return poly;
    }

    function rsEc(data, n) {
        var gen = rsGenPoly(n);
        var res = data.slice();
        var i, j;
        for (i = 0; i < n; i++) res.push(0);
        for (i = 0; i < data.length; i++) {
            var coef = res[i];
            if (coef !== 0) {
                for (j = 0; j < gen.length; j++) {
                    res[i + j] ^= gmul(gen[j], coef);
                }
            }
        }
        return res.slice(data.length);
    }

    // 文字列 → UTF-8 バイト列（URL想定だが多バイトも安全に）
    function utf8Bytes(str) {
        var out = [], i, c, c2, cp;
        for (i = 0; i < str.length; i++) {
            c = str.charCodeAt(i);
            if (c < 0x80) {
                out.push(c);
            } else if (c < 0x800) {
                out.push(0xC0 | (c >> 6), 0x80 | (c & 0x3F));
            } else if (c < 0xD800 || c >= 0xE000) {
                out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 0x3F), 0x80 | (c & 0x3F));
            } else {
                i++;
                c2 = str.charCodeAt(i);
                cp = 0x10000 + (((c & 0x3FF) << 10) | (c2 & 0x3FF));
                out.push(0xF0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3F),
                    0x80 | ((cp >> 6) & 0x3F), 0x80 | (cp & 0x3F));
            }
        }
        return out;
    }

    function totalData(version) {
        var blocks = EC_BLOCKS_M[version], t = 0, k;
        for (k = 0; k < blocks.length; k++) t += blocks[k][0] * blocks[k][2];
        return t;
    }

    function chooseVersion(bytes) {
        var v, cci, cap;
        for (v = 1; v <= 10; v++) {
            cci = v <= 9 ? 8 : 16;
            cap = Math.floor((totalData(v) * 8 - 4 - cci) / 8);
            if (bytes.length <= cap) return v;
        }
        return -1; // 長すぎ（このアプリのURLでは起きない）
    }

    function encodeData(bytes, version) {
        var td = totalData(version);
        var bits = [];
        function put(val, len) {
            var k;
            for (k = len - 1; k >= 0; k--) bits.push((val >> k) & 1);
        }
        put(0x4, 4); // バイトモード
        var cci = version <= 9 ? 8 : 16;
        put(bytes.length, cci);
        var i;
        for (i = 0; i < bytes.length; i++) put(bytes[i], 8);
        // 終端子
        var cap = td * 8;
        var term = Math.min(4, cap - bits.length);
        put(0, term);
        // バイト境界までパディング（標準どおり 0 埋め）
        while (bits.length % 8 !== 0) bits.push(0);
        var codewords = [];
        for (i = 0; i < bits.length; i += 8) {
            var v = 0, k;
            for (k = 0; k < 8; k++) v = (v << 1) | bits[i + k];
            codewords.push(v);
        }
        // 埋め草符号（0xEC / 0x11 を交互に）
        var pad = [0xEC, 0x11], pi = 0;
        while (codewords.length < td) {
            codewords.push(pad[pi % 2]);
            pi++;
        }
        return codewords;
    }

    function structureCodewords(codewords, version) {
        var blocks = EC_BLOCKS_M[version];
        var dataBlocks = [], ecBlocks = [];
        var idx = 0, gi, b, i;
        for (gi = 0; gi < blocks.length; gi++) {
            var cnt = blocks[gi][0], tot = blocks[gi][1], dt = blocks[gi][2];
            for (b = 0; b < cnt; b++) {
                var db = codewords.slice(idx, idx + dt);
                idx += dt;
                dataBlocks.push(db);
                ecBlocks.push(rsEc(db, tot - dt));
            }
        }
        var result = [];
        var maxd = 0, maxe = 0;
        for (i = 0; i < dataBlocks.length; i++) if (dataBlocks[i].length > maxd) maxd = dataBlocks[i].length;
        for (i = 0; i < ecBlocks.length; i++) if (ecBlocks[i].length > maxe) maxe = ecBlocks[i].length;
        for (i = 0; i < maxd; i++) {
            for (b = 0; b < dataBlocks.length; b++) {
                if (i < dataBlocks[b].length) result.push(dataBlocks[b][i]);
            }
        }
        for (i = 0; i < maxe; i++) {
            for (b = 0; b < ecBlocks.length; b++) {
                if (i < ecBlocks[b].length) result.push(ecBlocks[b][i]);
            }
        }
        return result;
    }

    function makeMatrix(version) {
        var size = version * 4 + 17;
        var m = [], i, j;
        for (i = 0; i < size; i++) {
            m[i] = [];
            for (j = 0; j < size; j++) m[i][j] = null;
        }
        return { m: m, size: size };
    }

    function placeFinder(m, r, c) {
        var size = m.length, i, j;
        for (i = -1; i <= 7; i++) {
            for (j = -1; j <= 7; j++) {
                var rr = r + i, cc = c + j;
                if (rr < 0 || rr >= size || cc < 0 || cc >= size) continue;
                if (i >= 0 && i <= 6 && j >= 0 && j <= 6) {
                    var dark = (i === 0 || i === 6 || j === 0 || j === 6 ||
                        (i >= 2 && i <= 4 && j >= 2 && j <= 4));
                    m[rr][cc] = dark ? 1 : 0;
                } else {
                    m[rr][cc] = 0; // 分離パターン
                }
            }
        }
    }

    function placeAlignment(m, version) {
        var pos = ALIGN[version], a, b, i, j;
        for (a = 0; a < pos.length; a++) {
            for (b = 0; b < pos.length; b++) {
                var r = pos[a], c = pos[b];
                if (m[r][c] !== null) continue; // ファインダと重なる位置は除外
                for (i = -2; i <= 2; i++) {
                    for (j = -2; j <= 2; j++) {
                        var dark = (i === -2 || i === 2 || j === -2 || j === 2 || (i === 0 && j === 0));
                        m[r + i][c + j] = dark ? 1 : 0;
                    }
                }
            }
        }
    }

    function placeTiming(m) {
        var size = m.length, i;
        for (i = 8; i < size - 8; i++) {
            var v = (i % 2 === 0) ? 1 : 0;
            if (m[6][i] === null) m[6][i] = v;
            if (m[i][6] === null) m[i][6] = v;
        }
    }

    function reserveFormat(m, version) {
        var size = m.length, i;
        m[4 * version + 9][8] = 1; // ダークモジュール
        for (i = 0; i < 9; i++) {
            if (m[8][i] === null) m[8][i] = 2;
            if (m[i][8] === null) m[i][8] = 2;
        }
        for (i = 0; i < 8; i++) {
            if (m[8][size - 1 - i] === null) m[8][size - 1 - i] = 2;
            if (m[size - 1 - i][8] === null) m[size - 1 - i][8] = 2;
        }
    }

    function reserveVersion(m, version) {
        if (version < 7) return;
        var size = m.length, i, j;
        for (i = 0; i < 6; i++) {
            for (j = 0; j < 3; j++) {
                m[i][size - 11 + j] = 2;
                m[size - 11 + j][i] = 2;
            }
        }
    }

    function placeData(m, data) {
        var size = m.length;
        var bits = [], i, k;
        for (i = 0; i < data.length; i++) {
            for (k = 7; k >= 0; k--) bits.push((data[i] >> k) & 1);
        }
        var idx = 0, col = size - 1, upward = true;
        while (col > 0) {
            if (col === 6) col -= 1;
            var row;
            if (upward) {
                for (row = size - 1; row >= 0; row--) placePair(row);
            } else {
                for (row = 0; row < size; row++) placePair(row);
            }
            upward = !upward;
            col -= 2;
        }
        function placePair(row) {
            var cc, c;
            for (cc = 0; cc < 2; cc++) {
                c = col - cc;
                if (m[row][c] === null) {
                    m[row][c] = (idx < bits.length) ? bits[idx] : 0;
                    idx++;
                }
            }
        }
    }

    function maskFn(mask, i, j) {
        switch (mask) {
            case 0: return ((i + j) % 2) === 0;
            case 1: return (i % 2) === 0;
            case 2: return (j % 3) === 0;
            case 3: return ((i + j) % 3) === 0;
            case 4: return ((Math.floor(i / 2) + Math.floor(j / 3)) % 2) === 0;
            case 5: return (((i * j) % 2) + ((i * j) % 3)) === 0;
            case 6: return ((((i * j) % 2) + ((i * j) % 3)) % 2) === 0;
            case 7: return ((((i + j) % 2) + ((i * j) % 3)) % 2) === 0;
        }
        return false;
    }

    function applyMask(m, reserved, mask) {
        var size = m.length, i, j;
        var out = [];
        for (i = 0; i < size; i++) out[i] = m[i].slice();
        for (i = 0; i < size; i++) {
            for (j = 0; j < size; j++) {
                if (!reserved[i][j] && maskFn(mask, i, j)) out[i][j] ^= 1;
            }
        }
        return out;
    }

    function getbit(x, i) { return (x >> i) & 1; }

    function formatBits(mask) {
        var data = (0 << 3) | mask; // レベルM = 0
        var rem = data, k;
        for (k = 0; k < 10; k++) rem = (rem << 1) ^ ((rem >> 9) * 0x537);
        return ((data << 10) | rem) ^ 0x5412;
    }

    function placeFormat(m, mask) {
        var size = m.length;
        var fi = formatBits(mask);
        var voffset = 0, hoffset = 0, i;
        for (i = 0; i < 8; i++) {
            var vbit = getbit(fi, i);
            var hbit = getbit(fi, 14 - i);
            if (i === 6) { voffset += 1; hoffset = 1; }
            m[i + voffset][8] = vbit;      // 縦・左上
            m[8][i + hoffset] = hbit;      // 横・左上
            m[8][size - 1 - i] = vbit;     // 横・右上
            m[size - 1 - i][8] = hbit;     // 縦・左下
        }
        m[size - 8][8] = 1; // 常に暗
    }

    function versionBits(version) {
        var rem = version, k;
        for (k = 0; k < 12; k++) rem = (rem << 1) ^ ((rem >> 11) * 0x1F25);
        return (version << 12) | rem;
    }

    function placeVersion(m, version) {
        if (version < 7) return;
        var size = m.length;
        var bits = versionBits(version), i;
        for (i = 0; i < 18; i++) {
            var bit = getbit(bits, i);
            var a = size - 11 + (i % 3);
            var b = Math.floor(i / 3);
            m[a][b] = bit;
            m[b][a] = bit;
        }
    }

    function penalty(m) {
        var size = m.length, score = 0, i, j, k;
        // 規則1: 連続
        for (i = 0; i < size; i++) {
            var lines = [m[i], []];
            for (k = 0; k < size; k++) lines[1].push(m[k][i]);
            var li;
            for (li = 0; li < 2; li++) {
                var arr = lines[li], run = 1;
                for (k = 1; k < size; k++) {
                    if (arr[k] === arr[k - 1]) run++;
                    else { if (run >= 5) score += 3 + (run - 5); run = 1; }
                }
                if (run >= 5) score += 3 + (run - 5);
            }
        }
        // 規則2: 2x2
        for (i = 0; i < size - 1; i++) {
            for (j = 0; j < size - 1; j++) {
                if (m[i][j] === m[i][j + 1] && m[i][j] === m[i + 1][j] && m[i][j] === m[i + 1][j + 1]) score += 3;
            }
        }
        // 規則3: ファインダ類似
        var p1 = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0];
        var p2 = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1];
        function eq(a, off, row, isRow) {
            var t;
            for (t = 0; t < 11; t++) {
                var v = isRow ? m[a][off + t] : m[off + t][a];
                if (v !== row[t]) return false;
            }
            return true;
        }
        for (i = 0; i < size; i++) {
            for (j = 0; j < size - 10; j++) {
                if (eq(i, j, p1, true) || eq(i, j, p2, true)) score += 40;
                if (eq(i, j, p1, false) || eq(i, j, p2, false)) score += 40;
            }
        }
        // 規則4: 暗率
        var dark = 0;
        for (i = 0; i < size; i++) for (j = 0; j < size; j++) if (m[i][j] === 1) dark++;
        var ratio = Math.floor(dark * 100 / (size * size));
        var prev = Math.floor(ratio / 5) * 5;
        var nxt = prev + 5;
        score += Math.floor(Math.min(Math.abs(prev - 50), Math.abs(nxt - 50)) / 5) * 10;
        return score;
    }

    function build(text) {
        var bytes = utf8Bytes(text);
        var version = chooseVersion(bytes);
        if (version < 0) return null;
        var mk = makeMatrix(version);
        var m = mk.m, size = mk.size;
        placeFinder(m, 0, 0);
        placeFinder(m, 0, size - 7);
        placeFinder(m, size - 7, 0);
        placeAlignment(m, version);
        placeTiming(m);
        reserveFormat(m, version);
        reserveVersion(m, version);
        var reserved = [], i, j;
        for (i = 0; i < size; i++) {
            reserved[i] = [];
            for (j = 0; j < size; j++) reserved[i][j] = (m[i][j] !== null);
        }
        for (i = 0; i < size; i++) for (j = 0; j < size; j++) if (m[i][j] === 2) m[i][j] = 0;
        var codewords = encodeData(bytes, version);
        var final = structureCodewords(codewords, version);
        placeData(m, final);
        var best = null, bestM = null, bestMask = 0, mask;
        for (mask = 0; mask < 8; mask++) {
            var cand = applyMask(m, reserved, mask);
            placeFormat(cand, mask);
            placeVersion(cand, version);
            var p = penalty(cand);
            if (best === null || p < best) { best = p; bestM = cand; bestMask = mask; }
        }
        return { modules: bestM, size: size, version: version, mask: bestMask };
    }

    // canvas に描画。moduleSize=1モジュールの画素、quiet=余白モジュール数
    function draw(text, canvas, moduleSize, quiet) {
        moduleSize = moduleSize || 6;
        quiet = (quiet == null) ? 4 : quiet;
        var qr = build(text);
        if (!qr) return false;
        var full = qr.size + quiet * 2;
        var px = full * moduleSize;
        canvas.width = px;
        canvas.height = px;
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, px, px);
        ctx.fillStyle = '#000000';
        var i, j;
        for (i = 0; i < qr.size; i++) {
            for (j = 0; j < qr.size; j++) {
                if (qr.modules[i][j] === 1) {
                    ctx.fillRect((j + quiet) * moduleSize, (i + quiet) * moduleSize, moduleSize, moduleSize);
                }
            }
        }
        return true;
    }

    return { build: build, draw: draw };
})();
