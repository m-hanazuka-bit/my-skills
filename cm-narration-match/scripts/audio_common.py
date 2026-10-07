"""cm-narration-match の共通処理（音声の読み書き・声の区間検出・スペクトル・声質の測定・Gemini 呼び出し）。

キーは環境変数 GEMINI_API_KEY（または GOOGLE_API_KEY）か .env（作業ディレクトリ → このスキル直下）。
"""
import base64, io, json, os, subprocess, sys, time, urllib.error, urllib.request, wave
from pathlib import Path

import numpy as np

SR = 24000  # Gemini TTS の出力と同じ。全処理をこのレートで行う
SKILL_DIR = Path(__file__).resolve().parent.parent
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
TEXT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")  # 書き起こし用

# 1/6 オクターブ帯の中心周波数（スペクトル比較と EQ カーブの評価点）
CENTERS = 50 * 2 ** (np.arange(0, 48) / 6)
CENTERS = CENTERS[CENTERS < SR / 2 * 0.95]


# ---------- 入出力 ----------

def load(path):
    """任意の音声/動画を 24kHz mono float で読む（ffmpeg）。"""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(float) / 32768


def wav_bytes(x, peak=0.89):
    x = x / (np.max(np.abs(x)) + 1e-12) * peak
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return buf.getvalue()


def save(path, x):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(wav_bytes(x))


# ---------- Gemini ----------

def api_key():
    k = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    for p in (Path(".env"), SKILL_DIR / ".env"):
        if k: break
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip().startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                    k = line.split("=", 1)[1].strip().strip("\"'"); break
    if not k:
        sys.exit("GEMINI_API_KEY が未設定です（環境変数か cm-narration-match/.env に書く）")
    return k


def gemini(model, parts, generation_config=None, timeout=180, retries=3):
    body = {"contents": [{"parts": parts}]}
    if generation_config: body["generationConfig"] = generation_config
    for i in range(retries):
        req = urllib.request.Request(API.format(model=model), json.dumps(body).encode(),
                                     {"Content-Type": "application/json", "x-goog-api-key": api_key()})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and i < retries - 1:
                time.sleep(5 * (i + 1)); continue
            sys.exit(f"Gemini API エラー {e.code}: {e.read().decode()[:500]}")


def first_part(res):
    return res["candidates"][0]["content"]["parts"][0]


def transcribe(x, timestamps=False):
    """Gemini で書き起こす。timestamps=True なら [{text,start,end}] を返す（音楽・効果音は [..] 表記）。"""
    audio = {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(wav_bytes(x)).decode()}}
    if not timestamps:
        prompt = "この音声を一字一句そのまま日本語で書き起こしてください。書き起こしのみを出力。"
        return first_part(gemini(TEXT_MODEL, [audio, {"text": prompt}]))["text"].strip()
    prompt = ("この音声のナレーション（人の声）の各フレーズについて、開始秒と終了秒を小数第2位まで "
              "JSON 配列 [{\"text\":..,\"start\":..,\"end\":..}] で出力。読点や息継ぎで区切れる単位をフレーズとする。"
              "音楽や効果音の区間もあれば {\"text\":\"[音楽や効果音の名前]\",...} として含める。JSON のみ出力。")
    res = gemini(TEXT_MODEL, [audio, {"text": prompt}], {"responseMimeType": "application/json"})
    return json.loads(first_part(res)["text"])


# ---------- 声の区間 ----------

def bandpass(x, lo=100, hi=4000):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))


def segments(x, floor_db=25, join_gap=0.15, min_len=0.15):
    """声の区間 [[開始秒, 終了秒], ...] を返す。
    100–4000Hz の 10ms エネルギーが最大から floor_db 以内の所を声とみなし、
    join_gap 秒未満の隙間はつなぎ、min_len 秒未満の区間（息・クリック）は捨てる。"""
    y = bandpass(x); h = SR // 100
    e = np.array([20 * np.log10(np.sqrt((y[i:i + h] ** 2).mean()) + 1e-9) for i in range(0, len(y) - h, h)])
    on = e > e.max() - floor_db
    segs, st = [], None
    for i, v in enumerate(on):
        if v and st is None: st = i
        if not v and st is not None: segs.append([st, i]); st = None
    if st is not None: segs.append([st, len(on)])
    m = []
    for a, b in segs:
        if m and a - m[-1][1] < join_gap * 100: m[-1][1] = b
        else: m.append([a, b])
    return [[a / 100, b / 100] for a, b in m if b - a >= min_len * 100]


def seg_f0(x, seg):
    import parselmouth
    a, b = int(seg[0] * SR), int(seg[1] * SR)
    f0 = parselmouth.Sound(x[a:b], SR).to_pitch_ac(time_step=0.01, pitch_floor=50, pitch_ceiling=600).selected_array["frequency"]
    f0 = f0[f0 > 0]
    return float(np.median(f0)) if len(f0) else None


def drop_music_edges(x, segs, octaves=0.8):
    """区間の端にある、声と音程がかけ離れた区間（尺八・チャイムなどの楽器）を落とす。
    内側の区間の声の高さの中央値から octaves オクターブ以上離れていれば楽器とみなす。"""
    segs = list(segs); dropped = []
    while len(segs) >= 3:
        f0s = [seg_f0(x, s) for s in segs]
        inner = [f for f in f0s[1:-1] if f]
        if not inner: break
        ref = np.median(inner)
        far = lambda f: f is None or abs(np.log2(f / ref)) > octaves
        if far(f0s[0]): dropped.append(segs.pop(0))
        elif far(f0s[-1]): dropped.append(segs.pop())
        else: break
    return segs, dropped


def align(segs, ref_phrases, max_group=3, merge_cost=0.02):
    """TTS の区間と元CMの句を対応づけ、(TTS側のまとまり [開始, 終了], 元CM側の開始秒) のリストを返す。
    TTS は読点で句を割ったり（「風が、｜語りかけます」）、元CMで分かれている句をつなげて読んだりするので、
    両側とも隣り合う区間を max_group 個までまとめてよいことにして、
    まとまりどうしの長さの差の二乗和が一番小さくなる対応を動的計画法で探す。"""
    n, k = len(segs), len(ref_phrases)
    span = lambda ss, i, j: ss[j - 1][1] - ss[i][0]
    INF = float("inf")
    cost = [[INF] * (k + 1) for _ in range(n + 1)]; back = [[None] * (k + 1) for _ in range(n + 1)]
    cost[0][0] = 0
    for i in range(n + 1):
        for j in range(k + 1):
            if cost[i][j] == INF: continue
            for p in range(1, max_group + 1):
                for q in range(1, max_group + 1):
                    if i + p > n or j + q > k: continue
                    c = cost[i][j] + (span(segs, i, i + p) - span(ref_phrases, j, j + q)) ** 2 \
                        + merge_cost * (p + q - 2)  # 迷ったら 1 対 1 を選ぶ
                    if c < cost[i + p][j + q]:
                        cost[i + p][j + q], back[i + p][j + q] = c, (i, j)
    if cost[n][k] == INF:
        raise SystemExit(f"句を対応づけられない（TTS {n} 区間 / 元CM {k} 句）。台本が元CMと同じか確かめる")
    out, i, j = [], n, k
    while i or j:
        pi, pj = back[i][j]
        out.append(([segs[pi][0], segs[i - 1][1]], ref_phrases[pj][0])); i, j = pi, pj
    return out[::-1]


# ---------- 音色・声質 ----------

def ltas(x):
    """有声部の長時間平均スペクトルを 1/6 オクターブ帯で返す（dB、最大 0）。"""
    n = 2048; win = np.hanning(n)
    fr = [x[i:i + n] * win for i in range(0, len(x) - n, n // 2)]
    rms = np.array([np.sqrt((v * v).mean()) for v in fr])
    P = np.mean([np.abs(np.fft.rfft(v)) ** 2 for v, r in zip(fr, rms) if r > rms.max() * 0.1], 0)
    f = np.fft.rfftfreq(n, 1 / SR)
    e = np.array([P[(f >= c / 2 ** (1 / 12)) & (f < c * 2 ** (1 / 12))].sum() for c in CENTERS])
    e = 10 * np.log10(e + 1e-12)
    return e - e.max()


def ltas_distance(a_db, b_db, lo=90, hi=7000):
    """2 つのスペクトルの差（lo〜hi Hz の RMS、dB）。小さいほど音色が近い。"""
    m = (CENTERS >= lo) & (CENTERS <= hi)
    d = np.asarray(a_db)[m] - np.asarray(b_db)[m]
    return float(np.sqrt(((d - d.mean()) ** 2).mean()))


def voice_only(x, segs=None, pad=0.03):
    """声の区間だけをつないだ音を返す。句の間に残る BGM や楽器の余韻を測定に混ぜないため。"""
    segs = segments(x) if segs is None else segs
    return np.concatenate([x[max(0, int((a - pad) * SR)):int((b + pad) * SR)] for a, b in segs])


def voice_metrics(x):
    """声の高さ・声質・明るさを Praat（parselmouth）で測る。x には voice_only() を通した音を渡す。"""
    import parselmouth
    from parselmouth.praat import call
    s = parselmouth.Sound(x, SR)
    f0 = s.to_pitch_ac(time_step=0.01, pitch_floor=50, pitch_ceiling=300).selected_array["frequency"]; f0 = f0[f0 > 0]
    pp = call(s, "To PointProcess (periodic, cc)", 50, 300)
    return {
        "f0_median_hz": round(float(np.median(f0)), 1),
        "f0_p10_hz": round(float(np.percentile(f0, 10)), 1),
        "f0_p90_hz": round(float(np.percentile(f0, 90)), 1),
        "jitter_pct": round(call(pp, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3) * 100, 2),
        "shimmer_pct": round(call([s, pp], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6) * 100, 2),
        "hnr_db": round(call(s.to_harmonicity_cc(0.01, 50, 0.1, 1.0), "Get mean", 0, 0), 2),
        "centroid_hz": round(call(s.to_spectrum(), "Get centre of gravity", 2), 0),
    }


def snr_db(x, segs, edge=0.05, min_gap=0.2):
    """句の中と句の間の音量差（dB）。元CMは声の下に音楽が鳴っていることが多く、
    これが小さい（30dB 未満）と、元CM側の HNR・shimmer は実際より濁った値に出る。"""
    rms = lambda a, b: np.sqrt((x[int(a * SR):int(b * SR)] ** 2).mean())
    voice = np.mean([rms(a, b) for a, b in segs])
    gaps = [rms(segs[i][1] + edge, segs[i + 1][0] - edge) for i in range(len(segs) - 1)
            if segs[i + 1][0] - segs[i][1] >= min_gap]
    return round(20 * np.log10(voice / (np.mean(gaps) + 1e-12)), 1) if gaps else None
