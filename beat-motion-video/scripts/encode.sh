#!/usr/bin/env bash
# フレーム連番 + mix.wav → mp4（H.264 / AAC）。縦型にしたい場合は storyboard の size を [1080,1920] にする。
# usage: bash encode.sh work/frames work/mix.wav 30 out.mp4
set -euo pipefail
FRAMES=${1:?frames dir}; AUDIO=${2:?mix.wav}; FPS=${3:-30}; OUT=${4:-out.mp4}
FIRST=$(ls "$FRAMES" | grep -E '^[0-9]+\.png$' | sort | head -1 | sed 's/\.png//')
ffmpeg -y -loglevel error -stats \
  -framerate "$FPS" -start_number "$((10#$FIRST))" -i "$FRAMES/%05d.png" \
  -i "$AUDIO" \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 256k -shortest "$OUT"
echo "→ $OUT"
