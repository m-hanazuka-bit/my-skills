# my-skills

Claude のエージェントスキル集。

| スキル | 内容 |
|---|---|
| [beat-motion-video](beat-motion-video/SKILL.md) | ビート合成 → Gemini TTS ナレーション → Blender 3D → HTML 2D → mp4。ビートに同期した 15〜30 秒のモーショングラフィック動画を作る |
| [belc-gu-product-video](belc-gu-product-video/SKILL.md) | ぐぅ（ベルクのペンギン）が関西弁で自慢げに商品を紹介する動画 |
| [belc-bellcook-product-video](belc-bellcook-product-video/SKILL.md) | ベルクックさんが丁寧にやさしく商品を紹介する動画 |
| [belc-product-video](belc-product-video/WORKFLOW.md) | 上の 2 つが使う共通エンジン（キャラ設定・台本チェック・Gemini TTS・音声分割・画面テンプレート） |
| [joretsu-papa](joretsu-papa/SKILL.md) | YouTube「家庭内序列5位パパ」（仮）の台本づくり。実話の「お父さんの悲哀」を毎回同じ型・決め台詞でショート／長尺の台本にする |

ベルクのキャラクタースキルを使うときは `beat-motion-video` / `belc-product-video` / キャラのスキルを同じ skills フォルダに並べる。
