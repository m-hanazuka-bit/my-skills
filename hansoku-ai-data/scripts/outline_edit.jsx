#target illustrator
// 縁取り付き文字（同じ文字を重ねた 1 行グループ）を一括で打ち替える。
// 使い方：変える行の文字を 1 つ選択 → ファイル → スクリプト → その他のスクリプト → このファイル
(function () {
    if (!app.documents.length) { alert('編集用のデータを開いてください。'); return; }
    var sel = app.activeDocument.selection;
    if (!sel || sel.length !== 1) { alert('打ち替える行の文字を1つだけ選択してください。'); return; }
    var g = sel[0];
    if (g.typename === 'TextFrame') g = g.parent;
    if (g.typename !== 'GroupItem' || !g.textFrames.length) {
        alert('縁取り文字のグループ（1行分）を選択してください。'); return;
    }
    var frames = [];
    for (var i = 0; i < g.textFrames.length; i++) if (g.textFrames[i].parent.typename === 'GroupItem') frames.push(g.textFrames[i]);
    if (!frames.length) { alert('グループの中に文字がありません。'); return; }
    var old = frames[0].contents;
    for (i = 1; i < frames.length; i++) {
        if (frames[i].contents !== old) { alert('違う文字が混ざっているので中止しました。'); return; }
    }
    var v = prompt('新しい文字（縁取りも一緒に変わります）', old);
    if (v === null) return;
    for (i = 0; i < frames.length; i++) frames[i].contents = v;
    app.redraw();
})();
