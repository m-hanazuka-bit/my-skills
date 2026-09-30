# ベルク キャラクター商品紹介動画 — 共通エンジン

`belc-gu-product-video`（ぐぅ）と `belc-bellcook-product-video`（ベルクックさん）が共通で使う仕組み。
キャラごとの違い（声・口調・色・動き・BGM）は `characters/<id>/character.json` に全部入っていて、エンジンは同じ。
キャラを増やすときは `characters/` にフォルダを足し、薄い SKILL.md を 1 枚書けばよい。

## 置き方
同じ skills フォルダに次の 4 つを並べる（エンジンは `../beat-motion-video/scripts` を使う）。
```
skills/
  beat-motion-video/            ビート合成・ミックス・撮影・書き出し
  belc-product-video/           ← この共通エンジン
  belc-gu-product-video/        ぐぅ
  belc-bellcook-product-video/  ベルクックさん
```
必要なもの：Python 3（`pip install numpy "rembg[cpu]"`）、Node 18+、ffmpeg。Playwright と Web フォントは初回に自動でキャッシュ（`~/.cache/belc-product-video`）。
Gemini API キーは環境変数 `GEMINI_API_KEY` かこのフォルダの `.env`（`.env.example` をコピー）。音声モデルは `gemini-3.8-flash-tts`。

## 入力と 2 つのモード
| | モード①（おすすめ） | モード② |
|---|---|---|
| 渡すもの | 商品画像＋商品情報＋**ナレーション案** | 商品画像＋商品情報＋**作成済みの音声ファイル** |
| 声 | 台本をキャラ口調に直して 1 行ずつ Gemini TTS | 無音で行ごとに自動分割（行ごとのファイルでも可） |
| 強み | セリフ単位で画と同期、1 行だけ作り直せる、口調ルールを自動チェック | すでに気に入っている音声をそのまま使える |
| コマンド | `make_video.py --script ...` | `make_video.py --script ... --audio narration.wav` |

モード②でも script.json は書く（行ごとのシーン割り当てと字幕のため）。台本が無ければ `--transcribe` 付きで `align_audio.py` を先に回すと書き起こしで作れる。

## script.json
```json
{
 "character": "gu",
 "tagline": "くらしにベルク",
 "product": { "name": "酪農牛乳", "spec": "1000ml", "image": "product.png",
              "points": ["成分無調整", "生乳100%使用"], "price_text": "" },
 "lines": [
  { "id": "n01", "text": "おっ、ちょお待ってや！", "emotion": "tame", "scene": "hook", "scene_opts": { "text": "ぐぅの/*イチオシ*" } },
  { "id": "n02", "text": "俺が見つけてきた、*酪農牛乳*やで！", "emotion": "doya", "scene": "product" },
  ...
  { "id": "n05", "text": "1000ml、ほんまにおすすめやで！", "emotion": "shime", "scene": "closing" }
 ]
}
```
- `text`：読み上げと字幕。`*語*` は字幕で強調（読み上げでは外れる）。字幕だけ変えたいときは `caption`、読みだけ変えたいとき（「100%」を「ひゃくパーセント」など）は `read`
- `emotion`：character.json の `emotions` のキー。TTS の演技指示になり、画面のキラキラ・ホップの強さにも効く
- `scene` と `scene_opts`：

| scene | 画面 | scene_opts |
|---|---|---|
| hook | キャラが大きく登場＋ひとこと | `text`（`/` で改行、`*` で強調） |
| product | 実物パッケージが回転して登場、商品名・規格 | — |
| point | パッケージ＋推しポイントを特大で | `point`、`sub` |
| photo | シーン画像を全面に、ゆっくり寄る | `image`、`text`、`focus:[x,y]`（縦型で見せたい位置）、`cover:{x,y,w,h,rot}` |
| closing | 商品・名前・規格・ポイント・価格・タグライン | —（最後の行が closing でなければ自動で足される） |

- 画像パスは script.json からの相対パス。`price_text` を入れると締めに価格が出る（例 `"*198*円（税込）"`）
- 構成（各行の開始時刻・シーンの長さ・小節数）はセリフの長さから自動で決まる。手で秒数を書かない

## 手順
```bash
E=<skills>/belc-product-video
# 0) 商品画像を切り抜く（白背景の商品写真でも実施。高さ 1000px 以上の写真が理想）
python $E/scripts/prepare_assets.py 商品写真.jpg work/product.png
# 1) 台本チェック（キャラの口調ルール違反は ERROR）
python $E/scripts/check_lines.py --character $E/characters/gu/character.json --script script.json
# 2) 下書き（半分の解像度）。API キーが無ければ --dummy-voice で画だけ確認できる
python $E/scripts/make_video.py --character gu --script script.json --out work/milk_gu --draft
# 3) 気になる行だけ声を作り直す
python $E/scripts/make_video.py --character gu --script script.json --out work/milk_gu --retts n03 --draft
# 4) 本番（縦型は --vertical）
python $E/scripts/make_video.py --character gu --script script.json --out work/milk_gu
```
- 出力：`work/<名前>/<名前>.mp4`。途中物（voice/、beat.wav、timeline.json、frames/）も同じフォルダ
- `--stop-after plan` で構成表だけ出して確認できる。`motion.html?t=5` をブラウザで開くとその瞬間を確認できる（`?play` で簡易再生）
- 下書きは必ず 10〜12 枚のコンタクトシートにして見てから本番に進む

## 画作りのルール（必ず守る）
1. **商品は実物写真だけ**を使う。生成 AI に商品パッケージを描かせない。キャラが商品を持つ生成画像を使うときは、
   崩れたパッケージを `cover` で実物写真に置き換える（例：`examples/rakuno-milk/scene_shelf_gu_garbled.webp`）
2. **キャラの見た目を変えない**：色替え・変形・左右反転（帽子の「B」が鏡文字になる）をしない。動きは弾み・傾き・伸び縮みの範囲
3. 表示できるのは**パッケージに書いてあること・依頼で渡された情報だけ**。「日本一」「最高級」などの根拠のない最上級表現や、
   効能をうたう表現は入れない。気になるときは `shinshohin-hyoji-check` スキルで確認する
4. 価格を出すときは税込／税抜を明記し、期間限定なら期間も出す

## ファイル
- `scripts/make_video.py` 全工程をまとめて実行
- `scripts/check_lines.py` キャラ口調チェック
- `scripts/char_tts.py` 設定表どおりのプロンプトで Gemini TTS（`--print-prompt` で中身だけ確認）
- `scripts/align_audio.py` モード②の音声分割・書き起こし
- `scripts/prepare_assets.py` 背景除去（BiRefNet）
- `assets/product.html` 画面テンプレート（横 1920×1080 / 縦 1080×1920 両対応）
- `characters/gu/`、`characters/bellcook/` 設定（character.json）と切り抜き済み画像
- `examples/rakuno-milk/` 酪農牛乳 1000ml の作例（両キャラの台本、商品切り抜き、シーン画像）
