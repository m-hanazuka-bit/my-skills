#target illustrator
// 編集用 SVG を開き、実寸・レイヤー・書体・長体・CMYK を整えて .ai で保存する。
// build_pop.py が MAP を埋め込んで書き出す。
(function () {
    var CONVERT_CMYK = true;   // false にすると RGB のまま保存
    var EXPORT_CHECK_PNG = true;
    var MAP = /*MAP*/{};
    var K = 72 / 25.4;

    var folder = File($.fileName).parent;
    var src = File(folder.fsName + '/' + MAP.svg);
    if (!src.exists) {
        var svgs = folder.getFiles('*.svg');
        if (!svgs.length) { alert('同じフォルダーに編集用 SVG がありません。ZIP をすべて展開してから実行してください。'); return; }
        src = svgs[0];
    }
    var doc = app.open(src);
    var report = [];

    // 1. 実寸 ---------------------------------------------------------------
    var ab = doc.artboards[0];
    var r = ab.artboardRect;
    var fullW = (MAP.trimW + 2 * MAP.bleed) * K, fullH = (MAP.trimH + 2 * MAP.bleed) * K;
    var f = fullW / (r[2] - r[0]);
    if (Math.abs(f - 1) > 0.003) {
        var ox = r[0], oy = r[1];
        for (var li = 0; li < doc.layers.length; li++) {
            var items = doc.layers[li].pageItems;
            for (var ii = 0; ii < items.length; ii++) {
                var it = items[ii];
                if (it.parent.typename !== 'Layer') continue;
                var p = it.position;
                it.resize(f * 100, f * 100, true, true, true, true, f * 100, Transformation.TOPLEFT);
                it.position = [ox + (p[0] - ox) * f, oy + (p[1] - oy) * f];
            }
        }
        report.push('読み込み倍率を補正しました（×' + f.toFixed(3) + '）');
    }
    ab.artboardRect = [r[0] + MAP.bleed * K, r[1] - MAP.bleed * K,
                       r[0] + MAP.bleed * K + MAP.trimW * K, r[1] - MAP.bleed * K - MAP.trimH * K];

    // 2. レイヤー分け -------------------------------------------------------
    var base = doc.layers[0], tops = [];
    for (var gi = 0; gi < base.groupItems.length; gi++) {
        if (base.groupItems[gi].parent.typename === 'Layer') tops.push(base.groupItems[gi]);
    }
    var byId = {};
    for (var m = 0; m < MAP.layers.length; m++) byId[MAP.layers[m].id] = MAP.layers[m].name;
    if (tops.length === MAP.layers.length) {
        // groupItems[0] が最前面。背面から順に新規レイヤーへ移す（新規レイヤーは常に最上位に作られる）
        for (var t = tops.length - 1; t >= 0; t--) {
            var nm = byId[tops[t].name] || MAP.layers[tops.length - 1 - t].name;
            var lay = doc.layers.add();
            lay.name = nm;
            tops[t].move(lay, ElementPlacement.PLACEATBEGINNING);
        }
        if (base.pageItems.length === 0) base.remove();
    } else {
        report.push('レイヤー分けは省略しました（グループ数が想定と違うため）');
    }

    // 3. 書体 ---------------------------------------------------------------
    var fontOf = {}, missing = [];
    var need = [];
    for (var key in MAP.fonts) {
        try { fontOf[key] = app.textFonts.getByName(MAP.fonts[key].ps); }
        catch (e) { need.push(key); }
    }
    if (need.length) {
        for (var fi = 0; fi < app.textFonts.length && need.length; fi++) {
            var tf0 = app.textFonts[fi], label = tf0.name + ' ' + tf0.family;
            for (var n = need.length - 1; n >= 0; n--) {
                var hints = MAP.fonts[need[n]].hints;
                for (var h = 0; h < hints.length; h++) {
                    if (label.indexOf(hints[h]) >= 0) { fontOf[need[n]] = tf0; need.splice(n, 1); break; }
                }
            }
        }
        for (var q = 0; q < need.length; q++) missing.push(MAP.fonts[need[q]].ja);
    }
    var textById = {}, textByContent = {};
    for (var ti = 0; ti < MAP.texts.length; ti++) {
        textById[MAP.texts[ti].id] = MAP.texts[ti];
        textByContent[MAP.texts[ti].text] = MAP.texts[ti];
    }
    var frames = doc.textFrames, groupsOf = {};
    for (var k = 0; k < frames.length; k++) {
        var fr = frames[k];
        var mm = /^(t\d+)/.exec(fr.name);
        var info = (mm && textById[mm[1]]) || textByContent[fr.contents];
        if (!info) continue;
        (groupsOf[info.id] = groupsOf[info.id] || []).push(fr);
        var pos = 0;
        for (var ri = 0; ri < info.runs.length; ri++) {
            var run = info.runs[ri], font = fontOf[run.font];
            if (font) {
                for (var c = pos; c < pos + run.n && c < fr.characters.length; c++) {
                    fr.characters[c].characterAttributes.textFont = font;
                }
            }
            pos += run.n;
        }
    }

    // 4. 幅に収める（長体） ---------------------------------------------------
    var fitted = [];
    for (var id in groupsOf) {
        var inf = textById[id];
        if (!inf || !inf.maxLen || inf.vertical) continue;
        var fs = groupsOf[id], w = 0;
        for (var a = 0; a < fs.length; a++) {
            var vb = fs[a].geometricBounds;
            if (/f$/.test(fs[a].name) || fs.length === 1) w = Math.max(w, vb[2] - vb[0]);
        }
        if (!w) { for (a = 0; a < fs.length; a++) { vb = fs[a].geometricBounds; w = Math.max(w, vb[2] - vb[0]); } }
        if (w > inf.maxLen) {
            var s = inf.maxLen / w;
            for (a = 0; a < fs.length; a++) {
                var ca = fs[a].textRange.characterAttributes;
                ca.horizontalScale = Math.max(50, ca.horizontalScale * s);
            }
            fitted.push(inf.text + '（' + Math.round(s * 100) + '%）');
        }
    }

    // 5. 画像の埋め込み・カラーモード ----------------------------------------
    for (var pi = doc.placedItems.length - 1; pi >= 0; pi--) { try { doc.placedItems[pi].embed(); } catch (e) {} }
    if (CONVERT_CMYK && doc.documentColorSpace !== DocumentColorSpace.CMYK) {
        try { app.executeMenuCommand('doc-color-cmyk'); report.push('CMYK に変換しました'); }
        catch (e) { report.push('CMYK 変換はできませんでした（ファイル→ドキュメントのカラーモードで手動変換してください）'); }
    }

    // 6. 保存 ---------------------------------------------------------------
    var stem = src.displayName.replace(/\.svg$/i, '');
    var dest = File(folder.fsName + '/' + stem + '.ai'), no = 2;
    while (dest.exists) { dest = File(folder.fsName + '/' + stem + '_' + no + '.ai'); no++; }
    var opt = new IllustratorSaveOptions();
    opt.pdfCompatible = true; opt.compressed = true; opt.embedLinkedFiles = true;
    doc.saveAs(dest, opt);
    if (EXPORT_CHECK_PNG) {
        try {
            var png = new ExportOptionsPNG24();
            png.artBoardClipping = true; png.transparency = false; png.horizontalScale = 150; png.verticalScale = 150;
            doc.exportFile(File(folder.fsName + '/Illustrator確認.png'), ExportType.PNG24, png);
        } catch (e) {}
    }

    var msg = '保存しました：\n' + dest.fsName;
    if (report.length) msg += '\n\n' + report.join('\n');
    if (fitted.length) msg += '\n\n幅に収めるため長体をかけた文字：\n' + fitted.join('\n');
    if (missing.length) msg += '\n\n【注意】この PC にない書体（別の書体で表示中）：\n' + missing.join('\n');
    alert(msg);
})();
