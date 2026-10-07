# ベルク ナレーション

「ベルク、ベルクすぎる。ベルクの骨なしベルチキ。ベルクといえば、骨なしベルチキ。」を、十万石まんじゅうCMで採用した声と音で作ったもの。
スキル `cm-narration-match` の「参考CMの音で別の台本を読ませる」手順で作成（`audio/shimizu/` と同じ設定）。

- 台本：`script.txt`（3 行目の「骨なしベルチ」は「骨なしベルチキ」として作成。全角スペースは「、」として間を入れた）
- 演出メモ：`style.txt`
- 声：Algenib を 3 テイク（`tts/`）。十万石の `profile.json` で高さ・音色を合わせ、「、」0.5 秒、「。」1.0 秒の間
- 採用：`tts_Algenib_cm.wav`（ざらつきが十万石の採用版に一番近い）
  - `tts_Algenib_2_cm.wav`：声が少し澄んでいる
  - `tts_Algenib_3_cm.wav`：TTS が「ベルク、ベルクすぎる」を続けて読み、読点の間が入らなかったので不採用

## 1 本にまとめた版
`belc_cm_full.wav`（と `.mp3`、約 21 秒）：尺八（0 秒）→「風が語りかけます。」（3.6 秒）→ 鳥のさえずり（6.6 秒）→ ベルクのナレーション（10.1 秒）

```bash
python3 audio/build_cm.py --narration audio/belc/tts_Algenib_cm.wav --out audio/belc/belc_cm_full.wav
```
