# 清水ナレーション

「清水です。うまい、うますぎる。きよいみずとかいて、しみず」を、十万石まんじゅうCMで採用した声と音で作ったもの。
スキル `cm-narration-match` の「参考CMの音で別の台本を読ませる」手順で作成。

- 台本：`script.txt`（TTS には「清水」をかなで渡す。漢字だと「きよみず」「せいすい」と読まれるおそれがある）
- 演出メモ：`style.txt`
- 声：Algenib を 3 テイク（`tts/`）
- 後処理：十万石の `profile.json` で高さ・音色を合わせ、句読点で間を入れる（「、」0.5 秒、「。」1.0 秒）、`--drive 3`、かすれなし

```bash
S=cm-narration-match/scripts
python $S/match_ref.py --profile cm-narration-match/examples/juumangoku/profile.json audio/shimizu/tts/*.wav \
    --script audio/shimizu/script.txt --gaps "、=0.5,。=1.0" --out-dir audio/shimizu --suffix _cm
```

| ファイル | 長さ | 備考 |
|---|---|---|
| `tts_Algenib_3_cm.wav` | 7.4 秒 | 十万石の採用版に一番近いざらつき（おすすめ） |
| `tts_Algenib_cm.wav` | 8.8 秒 | 声が澄んでいて、ゆったりめ |
| `tts_Algenib_2_cm.wav` | 7.9 秒 | 声が澄んでいる |

## 1 本にまとめた版
`shimizu_cm_full.wav`（と `.mp3`、約 18 秒）：尺八 →「風が語りかけます。」→ 鳥のさえずり → 清水ナレーション

| 時刻 | 内容 | 素材 |
|---|---|---|
| 0.0 秒〜 | 尺八 | `audio/juumangoku/shakuhachi.wav` |
| 3.6 秒〜 | 風が語りかけます。 | `audio/juumangoku/narration_Algenib_cm.wav` の 0.54〜2.84 秒 |
| 6.6 秒〜 | 鳥のさえずり | `audio/juumangoku/birds.wav` |
| 10.1 秒〜 | 清水です。うまい、うますぎる。きよいみずとかいて、しみず。 | `tts_Algenib_3_cm.wav` |

```bash
python3 audio/shimizu/build_cm.py                                         # 作り直す
python3 audio/shimizu/build_cm.py --shimizu audio/shimizu/tts_Algenib_cm.wav  # 清水を別テイクにする
```
時刻と音量は `build_cm.py` の `parts` と音量の行で変えられる。
