# layout.json 仕様

単位はすべて **mm**。原点は仕上がり（トリム）の左上、x は右、y は下向き。塗り足しがあっても座標は仕上がり基準で書く。

```json
{
  "name": "シャインマスカット_B5横",          // ファイル名に使う
  "size": "B5横",                             // "B5横" "A3縦" "300x864横" "300x864縦" か {"w":mm,"h":mm}
  "bleed": 0,                                 // 塗り足し mm。仕上がり線に接する rect / cover 画像は自動で外へ延長
  "background": "#FFF8D8",                    // 省略可。最背面に全面の四角を敷く
  "meta": {"展開場所": "ぶどう売場", "期間": "〜10/15", "枚数": "各店2枚"},   // 紙面外の運用情報
  "notes": ["生産者写真は依頼書の画像を使用"],                                  // お読みください.txt に追記
  "layers": [ {"name": "背景", "items": [ ... ]}, {"name": "文字", "items": [ ... ]} ]   // 先頭が最背面
}
```

## 共通プロパティ
| キー | 意味 |
|---|---|
| `fill` | 色（`"#RRGGBB"`、`"#RRGGBBAA"`、`"none"`）かグラデーション（下記） |
| `stroke` / `strokeWidth` | 線の色と太さ（mm） |
| `dash` | 破線 `[線, 間隔]`（mm） |
| `opacity` | 0〜1 |
| `rotate` | 回転角（度、時計回り）。図形の中心で回る |

グラデーション：
```json
{"type": "linear", "angle": 90, "stops": [[0, "#FFFBE0"], [1, "#FFF3B8"]]}   // angle 0=左→右, 90=上→下
{"type": "radial", "stops": [[0, "#FFFFFF", 0.9], [1, "#FFFFFF", 0]]}       // 3 番目は不透明度
```

## 図形
| type | 必須キー | 用途・メモ |
|---|---|---|
| `rect` | x, y, w, h（r=角丸） | 帯、パネル、背景 |
| `ellipse` / `circle` | cx, cy, rx, ry（circle は r） | 吹き出し、丸バッジ |
| `polygon` | points `[[x,y],…]` | 強調マーク、筆帯、斜めの帯 |
| `path` | d（SVG パス、座標は mm） | 雲形の吹き出し、曲線パネル。M L H V C S Q T A Z に対応 |
| `star` | cx, cy, r（inner=内径比 0.8、n=山の数 16、ry=縦半径） | 爆発バッジ、ギザギザ枠 |
| `rays` | cx, cy, r2（r1、n=24、spread=1 本の角度幅 5°、clip=true） | 集中線・放射背景。clip で紙面内に切る |
| `ribbon` | x, y, w, h（tail, notch, drop, tailFill, foldFill） | 冠リボン（「長野県高山村産」など）。本体の上に文字を置く |
| `dots` | x, y, w, h（step=4, r=1, fade=left/right/up/down） | 網点。fade の向きへ小さくなる |
| `group` | items | まとめて opacity をかけるとき |

## 画像 `image`
```json
{"type": "image", "src": "images/grape.png", "x": 0, "y": 0, "w": 81, "h": 182,
 "fit": "contain", "crop": [0, 0, 470, 1055], "alignX": "center", "alignY": "bottom", "r": 4}
```
- `src`：layout.json からの相対パス。PNG/JPEG 推奨（webp などは自動で PNG に変換）
- `fit`：`contain`（枠内に全体、既定）／`cover`（枠を埋めて切り抜き、クリップグループになる）／`stretch`
- `crop`：元画像の px 範囲 `[x, y, w, h]`。デザイン案から文字のない範囲だけ使うとき
- `alignX` / `alignY`：contain で余白が出たときの寄せ（商品写真は `"bottom"` で下揃えが多い）
- `r`：角丸でクリップ

## 文字 `text`
```json
{"type": "text", "text": "甘さ増し増し！", "font": "pop", "size": 21,
 "x": 136, "y": 92, "align": "center", "color": "#E0141E",
 "outlines": [{"color": "#FFFFFF", "width": 1.3}, {"color": "#FFD83A", "width": 0.9}],
 "shadow": {"dx": 0.8, "dy": 1.0, "color": "#7A4A00"},
 "maxWidth": 118, "rotate": -3, "tracking": 0, "scaleX": 100}
```
| キー | 意味 |
|---|---|
| `text` | 文字。`\n` で改行。1 行が 1 つの Illustrator グループになる |
| `lines` | `text` の代わり。行ごとに文字列か**ラン配列** `[{"t":"松本","size":9},{"t":"さん","size":6,"color":"#333","font":"maru"}]` |
| `font` | 書体キー（`references/fonts.md`）。既定 `kakugo-ub` |
| `size` | 文字サイズ（mm、全角 1 文字の大きさ）。pt にするには × 2.835 |
| `x`, `y` | 横組み：x は align の基準点、y は **1 行目の上端**。縦組み：x は 1 列目の中心線、y は上端 |
| `align` | `left` / `center`（既定） / `right`。縦組みは `top` / `center` / `bottom` |
| `lineHeight` | 行送り（文字サイズに対する倍率、既定 1.2） |
| `color` | 文字色かグラデーション |
| `outlines` | 縁取り。**内側から外側の順**に `{color, width(mm)}`。同じ文字を太い線付きで後ろに重ねて作る |
| `shadow` | 縁取りの外形ごとずらした影 `{dx, dy, color}` |
| `maxWidth` | 行の最大長（mm）。越えたら jsx とプレビューが長体で収める（下限 50%） |
| `scaleX` | 最初からかける長体・平体（%） |
| `tracking` | 字間（1/1000 em、Illustrator のトラッキングと同じ） |
| `rotate` | 回転（度）。(x, y) を中心に回る |
| `vertical` | true で縦組み（長尺縦の大見出しなど）。maxWidth による自動長体は横組みだけ |
| `name` | 任意のメモ（jsx の報告に出る） |

### 縁取りの目安
- 白フチ：文字サイズの 6〜8%（21mm の見出しなら 1.3mm 前後）
- 二重フチ（白＋色）：内側の白を 5〜6%、外側の色を 4〜5%
- 暗い背景の上の白文字は縁取りなし、または濃い色の細いフチ（3%）

### Illustrator での構造
```
レイヤー「04 文字」
  └ グループ t012        ← 1 行
       ├ t012s  影
       ├ t012o2 外側の縁取り（太い線付き）
       ├ t012o1 内側の縁取り
       └ t012f  本体
```
`縁取り文字変更.jsx` はこのグループの中の文字を一括で打ち替える。
