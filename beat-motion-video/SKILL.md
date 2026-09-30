---
name: beat-motion-video
description: ビートに同期した15〜30秒のダイナミックなモーショングラフィック動画（CM・告知・ティザー）を、ビート合成→Gemini TTSナレーション→Blenderの3D→HTMLの2D→合成→mp4 まで一気通貫で作る。2Dと3Dをシームレスにつなぎ、ナレーションの感情の起伏（声のテンション）を設計する。ユーザーが「モーショングラフィック」「モーショングラフィックス」「CM動画」「告知動画」「イベント告知」「商品紹介動画」「ティザー」「15秒動画」「ショート動画」「ビートに合わせた動画」「Blenderで3D」「Gemini TTS」「ナレーション付き動画」「縦型動画」と言ったときや、動画スタイル（sport-pop、night-city、和風、glitch など）を指定したときは必ずこのスキルを使う。参考動画や参考画像を渡されて「こんな感じの動画を作って」と言われたときも使う。静止画ポスターやスライド資料には使わない。
---

# ビート同期モーショングラフィック動画

**音（ビート）が設計図**。先に曲を作って拍の時刻を JSON にし、3D も 2D もナレーションも全部その時刻に合わせて動かす。
だから何度作っても「音にハマった」動画になる。

```
storyboard.json ─┬─ make_beat.py ──→ beat.wav + beat.json（拍・キック・スネア・ドロップ）
                 ├─ gemini_tts.py ─→ voice/*.wav（行ごとにテンション）
                 └─ mix_audio.py ──→ mix.wav + timeline.json  ← 以降はこれ 1 つを見る
                                        ├─ blender_scene.py → 3d/00123.png（透過・ビート同期）
                                        └─ template.html + render_frames.mjs → frames/*.png（2D＋3D 合成）
                                                                   └─ encode.sh → out.mp4
```

## 0. 準備（初回だけ）
- Python 3 + `pip install numpy` / Node 18+ / ffmpeg / Blender 4.x–5.x（`blender` が PATH に無ければフルパスで）
- 作業フォルダを作り、スクリプトとテンプレートをコピーして Playwright を入れる：
  ```bash
  mkdir -p work && cd work
  cp <skill>/scripts/* . && cp <skill>/assets/template.html motion.html
  npm init -y >/dev/null && npm i playwright && npx playwright install chromium
  ```
- Gemini API キー：`export GEMINI_API_KEY=...` かスキル直下の `.env`（`.env.example` をコピー）。**キーをファイルに書いてコミットしない**

## 1. ヒアリング（足りない分だけ、1 回でまとめて聞く）
目的と見せたいもの（商品・イベント名・日時・場所・URL）／尺（既定 15 秒）／横 16:9 か縦 9:16／作風／ナレーションの有無。
参考動画や画像があれば、パレット・書体・動きのキーワードを読み取って `references/styles.md` の近いスタイルに寄せる。

## 2. storyboard.json を書く
`assets/storyboard.example.json`（和・上質、3D は自作の茶葉）と `assets/storyboard.event.json`（スポーツ告知、HUD・残像・擬音・柄シーン入り）を土台にする。

- `beat`：`references/styles.md` のスタイルから style / bpm を決める
- `palette`：bg / primary / accent / light / text の 5 色だけ。Blender と HTML の両方がこれを使う
- `look`：`style_id`、`hud_label`（左上 HUD）、`caption`（pill / plain / none）、`pattern_word`
- `scenes`：**小節単位**（`start_bar` / `end_bar` は整数）。type は title / 3d / pattern / tagline / outro。
  使えるキー（text の `*強調*` と `\n`、echo、sticker、onomatopoeia、label、vertical、serif、transition）は template.html 冒頭のコメント参照
- `narration`：`text`、`tension`、`at_bar`（小数可）。テンションの山は `references/audio.md`
- `scene3d`：3D を出す小節と主役・カメラ。主役の作り分けは下の 4

構成の定石（15 秒 ≒ 6〜8 小節）：
| 小節 | セクション | 絵 | 声 |
|---|---|---|---|
| 0–2 | intro | フック（問い・特大タイトル） | Lv1–3 |
| 2–3 | build | 説明・寄り、ライザーで溜める | Lv4 |
| ドロップ | drop | **3D の主役 or メインコピー**（一番見せたい絵） | Lv5 |
| 最後の 1 小節 | outro | 明るい背景にロゴ＋一言＋情報 | Lv3 きっぱり |

## 3. 音を作る
```bash
python make_beat.py --style future --bpm 132 --duration 15 --out beat   # --list で種類一覧
python gemini_tts.py --plan storyboard.json --out voice                   # --list-tensions でテンション一覧
python mix_audio.py --plan storyboard.json --beat beat --voice voice --out .
```
- `mix_audio.py` がはみ出し警告を出したら、文を短くするか `at_bar` を前へ動かして TTS からやり直す
- キーが無い／ナレーション無しなら `gemini_tts.py` を飛ばしてよい（mix は声なしで動く）

## 4. 3D を作る（Blender）
```bash
blender -b -P blender_scene.py -- --plan storyboard.json --timeline timeline.json --out 3d --preview   # 下書き
blender -b -P blender_scene.py -- --plan storyboard.json --timeline timeline.json --out 3d             # 本番
```
- 主役 `scene3d.subject.type`：`primitive`（torus/sphere/cube/ico/monkey/cylinder）、`text`（**和文は font に .ttf/.otf を必ず指定**）、
  `import`（.glb/.fbx/.obj）、`custom`（自作 bpy スクリプト。例 `assets/tea_leaf.py`：変数 `hero` と任意の `glow_nodes` を返す）
- 主役は自動で中心に置かれ最大寸法 `fit`（既定 2.6m）にそろうので、カメラ設定は使い回せる
- カメラ `camera.move`：orbit / push_in / static、`handoff_in` / `handoff_out`（2D とのつなぎ、既定 ON）
- GPU の無いサーバーでは `--engine cycles --samples 16`（EEVEE は OpenGL が要る）。下書きは `--percent 50`
- 下書きの PNG を数枚並べて見て、主役が画面外・下寄り・向きが逆、になっていないか確かめてから本番へ
- **Blender が無い／形がうまく作れない**ときは three.js で代替（`references/seamless-2d3d.md` 末尾）
- **Higgsfield（Brender MCP）が繋がっているとき**は下の「Brender / Higgsfield ルート」も使える

## 5. 2D を作って合成する
`motion.html` を編集して作風を作る。**動きは必ず `seek(t)` の中で時刻から計算する**（CSS アニメや requestAnimationFrame は撮影でズレる）。
部品：キネティックタイポ（8 分音符で 1 文字ずつ）、残像エコー、擬音、ステッカー、章ラベル、ピル型字幕、HUD、柄シーン、丸ワイプ、2D⇄3D の受け渡し丸。

```bash
python fetch_fonts.py --out fonts "Dela Gothic One" "Noto Sans JP:wght@400;700;900" "Noto Serif JP:wght@500;900" "JetBrains Mono:wght@500"
node render_frames.mjs --html motion.html --timeline timeline.json --frames3d 3d --out frames --step 6 --scale 0.5   # 下書き
node render_frames.mjs --html motion.html --timeline timeline.json --frames3d 3d --out frames                        # 本番
bash encode.sh frames mix.wav 30 out.mp4
```
- `[warn] 読み込めていないフォント` が出たら fetch_fonts.py を実行（ローカルの fonts/fonts.css が優先して読まれる）
- ブラウザで `motion.html?t=4.2` を開くとその瞬間、`?play` で簡易再生（TIMELINE を注入しないのでダミーデータで動く）

## 6. 仕上げチェック（下書きの段階で必ず見る）
下書きフレームを 4×3 などのコンタクトシートにして目で確認する。
- [ ] ドロップの頭に一番見せたい絵があるか。キックで何かが必ず動いているか
- [ ] 2D⇄3D のつなぎ目の前後 ±3 フレームで、形・色・位置が飛んでいないか
- [ ] 文字が画面からはみ出していない／重なっていない（縦書き・長いコピー）
- [ ] 強調語は 1 シーン 1 語。字幕とナレーションが合っている
- [ ] 最後の 1 小節でロゴ・日時・場所・URL が読める長さ（最低 1.5 秒）表示されている
- [ ] 声が埋もれていない（`mix_audio.py --duck` で調整）

直すときは、どのファイルのどこを直すかを決めて部分的にやり直す（音 → mix → 3D → frames → encode の順で下流だけ再実行）。

## Brender / Higgsfield ルート（任意）
Higgsfield の Brender MCP（`mcp__Brender__bl_*`）がユーザーの PC の Blender に繋がっていると、CLI の代わりに対話的に 3D を作れる。
`mcp__Brender__get_host_status` で `blr: true` を確認してから使う。
- 使う前に `bl_get_skill('blender-scene')` を読み、その手順に従う（Brender 側の必須ルール）
- `blender_scene.py` の中身は `bl_execute` にそのまま渡せる（argparse 部分を辞書に置き換える）。`bl_screenshot` で途中確認できるのが利点
- **複雑な主役（商品・キャラクター・道具）を手で bpy モデリングするのが難しいとき**に一番効く：
  `bl_generate_3d`（テキスト→3D）や `bl_image_to_3d`（商品写真→3D）で GLB を作り、`subject.type: "import"` で読み込む。
  生成は Higgsfield のクレジットを消費するので、実行前に見積もりをユーザーに伝える
- レンダリングは最後に `blender_scene.py` と同じ出力（透過 PNG・動画全体のフレーム番号）にそろえれば、以降の手順は同じ

## ファイル
- `scripts/make_beat.py` ビート 5 種の合成＋拍 JSON
- `scripts/gemini_tts.py` Gemini TTS、テンション 9 種、`.env` 対応
- `scripts/mix_audio.py` ダッキング付きミックス、timeline.json 生成
- `scripts/blender_scene.py` 3D 主役・ライト・カメラ・ビート反応・2D 受け渡し、透過 PNG 連番
- `scripts/render_frames.mjs` HTML＋3D を 1 フレームずつ撮影（Playwright）
- `scripts/fetch_fonts.py` Google Fonts のローカル保存
- `scripts/encode.sh` mp4 書き出し
- `assets/template.html` 2D 部品集テンプレート
- `assets/storyboard.example.json` / `assets/storyboard.event.json` / `assets/tea_leaf.py` 作例
- `references/styles.md` 動画スタイル・カタログ（増やしていく）
- `references/seamless-2d3d.md` 2D⇄3D のつなぎ方 5 パターン、three.js 代替
- `references/audio.md` ビートの使い分け、声のテンション設計、ミックス調整
