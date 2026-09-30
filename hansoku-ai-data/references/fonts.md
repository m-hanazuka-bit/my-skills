# 書体の対応表

`font` に書くキー → Illustrator で使う書体（PostScript 名）→ プレビューで代わりに使う無料書体。
表の元データは `scripts/fonts.json`。書体を増やすときは fonts.json に 1 項目足す（`hints` は Illustrator でフォント名を探すときの手がかりの文字列）。

| キー | Illustrator の書体 | PostScript 名 | プレビュー | 向いている所 |
|---|---|---|---|---|
| `pop` | HGP創英角ﾎﾟｯﾌﾟ体 | HGPSoeiKakupoptai | Mochiy Pop P One | 煽り文句・キャッチ（甘さ増し増し！） |
| `kakugo-ub` | HGP創英角ｺﾞｼｯｸUB | HGPSoeiKakugothicUB | Noto Sans JP 900 | 大見出し・商品名・リボン・下帯（既定） |
| `gothic-e` | HGPｺﾞｼｯｸE | HGPGothicE | Noto Sans JP 900 | 価格・数字 |
| `maru` | HG丸ｺﾞｼｯｸM-PRO | HGMaruGothicMPRO | Zen Maru Gothic 700 | やさしい説明文・子ども向け |
| `presence` | HGP創英ﾌﾟﾚｾﾞﾝｽEB | HGPSoeiPresenceEB | Shippori Mincho B1 800 | 和・高級感の見出し |
| `mincho-e` | HGP明朝E | HGPMinchoE | Shippori Mincho B1 800 | 上品な見出し・贈答 |
| `gyosho` | HGP行書体 | HGPGyoshotai | Yuji Syuku | 筆文字風（新米・鍋・年末） |
| `meiryo-b` | メイリオ ボールド | Meiryo-Bold | Noto Sans JP 700 | 本文・注意書き |

## デザイン案の文字から書体を選ぶ目安
- 丸みがあって太く、はねが跳ねている → `pop`
- 角ばって極太、字面が大きい → `kakugo-ub`
- 本文の太めゴシック → `meiryo-b`
- 筆で書いたような文字 → `gyosho`（筆のかすれは再現できない。必要ならデザイナーに差し替えを依頼）
- 明朝体の太字 → `presence`（見出し）／`mincho-e`

## 注意
- HGP 書体は Windows の Office に付いてくる。Mac の Illustrator に入っていないと別の書体で表示されるので、jsx が最後に「この PC にない書体」として一覧を出す
- 代替フォントと HG フォントでは文字幅が違う（HGP創英角ﾎﾟｯﾌﾟ体の方が少し広い）。`maxWidth` を付けておけば jsx が本物の書体の幅で長体をかける
