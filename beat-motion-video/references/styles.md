# 動画スタイル・カタログ

storyboard.json の `look.style_id` に ID を書き、下の「パレット／書体／ビート／声／動き／3D」をそのまま初期値にする。
ユーザーが「〜っぽく」「〜風に」と言ったら一番近いものを選び、1〜2 項目だけ変える。
新しい作風を作ったら、ここに 1 行足していく（スタイルが増えるほどスキルが強くなる）。

表記：ビート = `make_beat.py --style` / 声 = `gemini_tts.py` のテンション（intro → build → drop → outro の順）

---

## 実例ベース（参考動画で確認した作風）

### `sport-pop` — スポーツ・イベント告知
- パレット：bg `#0d2a8a` / primary `#1f5fe0` / accent `#d7ff3a`（蛍光イエロー）/ text `#fff`
- 書体：Dela Gothic One（見出し）＋ Noto Sans JP 900（字幕）＋ JetBrains Mono（HUD）
- ビート：future 128–132 BPM
- 声：bright → narrator → build → hype → tagline
- 動き：斜めストライプ背景、残像エコー文字（「打つと、」）、擬音ポップ（「ポコッ」）、斜めステッカー（「キッチン」）、
  ピル型字幕、章ラベル（`01 PADDLE` `02 BALL`）、左上 HUD（`PICKLEBALL EVENT`）
- 3D：道具（パドル／ボール）を回転で見せる → ボールにカメラが突っ込み、穴の柄が 2D の `pattern` シーンに化ける。
  コートは真上の 2D 図 → パースの付いた 3D コートへ（seamless-2d3d.md の「上から→斜め」）
- 締め：明るい背景に押し出し風ロゴ「PICKLEBALL EVENT」＋一言

### `night-city` — コミュニティ／勉強会の告知
- パレット：bg `#0a0f14` / primary `#16c47f`（ネオングリーン）/ accent `#ffd60a` / text `#f2f5f7`
- 書体：Dela Gothic One ＋ Noto Sans JP ＋ JetBrains Mono
- ビート：house 124–132
- 声：calm → build → hype → tagline
- 動き：夜のビル群のシルエット（窓がキックで明滅）、TODO リストが 1 行ずつ取り消し線で消える、
  「ラクに」だけ黄色で特大、情報ブロック（会場・内容・形式）がラベル付きで積み上がる、路線図風タイムライン
- 3D：ビル群を Blender で作りカメラが街の上を抜ける（無理なら 2D の多層パララックス）
- 締め：「柏で会おう！」のような場所＋呼びかけ、URL をピル型で

### `wa-premium` — 和・上質（茶、酒、和菓子、旅館）
- パレット：bg `#050806` / primary `#3f7d2c` / accent `#c9f27a` / text `#f4f1e8`
- 書体：Noto Serif JP 900 の縦書き、小さな添え字（「手摘み」）
- ビート：cinematic 90–100 または lofi 84
- 声：whisper → narrator → tagline（hype は使わない）
- 動き：黒地に逆光の被写体、ゆっくりしたドリーズーム、文字はぼかしから浮かぶ、キックは光のにじみだけ
- 3D：`assets/tea_leaf.py` のような自作モデル＋水滴、リムライト強め
- 締め：短い一句（「朝摘みの、ひとしずく。」）

---

## 汎用スタイル

| id | 向いている用途 | パレット (bg / primary / accent) | ビート | 声の流れ | 動きのキーワード |
|---|---|---|---|---|---|
| `mono-type` | ブランド宣言、採用 | #ffffff / #111111 / #ff2d2d | house 120 | narrator→build→trailer | 白黒反転カット、特大 1 文字、拍ごとに反転 |
| `form` | 建築、家具、デザイン事務所 | #f3efe8 / #1c1c1c / #e4572e | lofi 88 | calm→narrator→tagline | 幾何学図形が組み上がる、グリッド、細い罫線 |
| `dance` | 音楽、フェス、エンタメ | #ff2e88 / #3a0ca3 / #ffe600 | trap 140 | bright→hype→hype | 文字が跳ねる・踊る、スケールパンチ強め、色反転 |
| `tech-launch` | AI・SaaS の新機能発表 | #0b0b1f / #5b5bff / #7cf3ff | future 128 | narrator→build→hype | 紫グラデ、数字カウントアップ、UI カードが 3D で並ぶ |
| `isometric` | サービスの仕組み説明 | #eef3ff / #3a6df0 / #ffb703 | house 118 | warm→narrator→tagline | アイソメ図の街・部屋、要素が拍で積み上がる |
| `pop-comic` | 飲食、キャンペーン | #fff1d6 / #ff3b3b / #1d3557 | future 128 | bright→hype→tagline | 集中線、吹き出し、擬音、ハーフトーン |
| `flat-illust` | 子ども・教育・行政 | #fef6e4 / #f582ae / #8bd3dd | lofi 90 | warm→bright→tagline | ぽよんと出るイラスト、丸いワイプ |
| `terminal` | 開発者向け、ハッカソン | #0c0c0c / #00ff9c / #ffffff | trap 140 | calm→build→hype | タイプライター、ASCII アート、スキャンライン |
| `glitch` | ゲーム、ティザー | #050505 / #ff0055 / #00e5ff | trap 150 | whisper→build→trailer | RGB ずれ、ブロックノイズ、インパクトで画面割れ |
| `product-dark` | ガジェット、化粧品 | #070707 / #d9d9d9 / #b08d57 | cinematic 100 | calm→narrator→tagline | 黒背景に製品 3D、スペックが細字で出る、リムライト |
| `data-counter` | 実績・料金・レポート | #fff200 / #111111 / #ff3d00 | house 124 | narrator→build→hype | 金額カウンター（¥248,300）、棒グラフが拍で伸びる |
| `doodle` | ゆるい告知、社内向け | #ffffff / #222222 / #ffcc00 | lofi 86 | warm→bright→tagline | 手描き線が描かれていく（SVG stroke-dashoffset） |
| `landscape` | 観光、不動産 | #0e1a2b / #6fa8dc / #ffd28a | cinematic 96 | whisper→narrator→tagline | 空撮風のゆっくりしたカメラ、霧、夕景グラデ |
| `neon-wave` | ナイトイベント、クラブ | #120024 / #ff00d4 / #00fff0 | future 132 | build→hype→hype | ネオン管文字、グリッド床の 3D、波形ビジュアライザ |
| `japanese-pop` | アイドル、キャラ物 | #ffe3f1 / #ff4fa3 / #6c63ff | future 140 | bright→hype→bright | キラキラ粒子、ハート、文字が回転して着地 |

## 共通の型（参考動画から抽出した「効く」ルール）
- **左上に等幅の小さな HUD**（作品名＋`NN / シーン名`）、右上に BPM とシーン数のドット。情報量が増えて"作り込まれた感"が出る
- **強調語は 1 シーン 1 語だけ** accent 色＋特大（`*ラクに*`）。全部を強調しない
- **擬音・ステッカー・章ラベル**のどれか 1 つを各シーンに置く（全部は置かない）
- 字幕はナレーションと 1 文字ずつ同期させ、強調語は字幕でも accent 色
- 最後は明るい背景（または反転色）に切り替えてロゴ＋一言で締める。暗い → 明るいの反転が「終わり」の合図になる
