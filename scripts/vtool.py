#!/usr/bin/env python3
"""video-notes 工具。用法（PY 为 setup.sh 建好的 venv 里的 python）：
  python vtool.py fetch URL OUT [--referer R]        下载媒体直链（抖音等）
  python vtool.py bili-audio BV号或链接 OUTDIR        B站下载音频（bili-cli）
  python vtool.py yt-audio URL OUTDIR [--cookies F | --browser chrome]   用 yt-dlp 下载音频（YouTube 等）
  python vtool.py transcribe AUDIO OUT.txt [--lang zh] [--prompt 术语] [--words W.json]   本地语音识别（--words 另存逐词置信度）
  python vtool.py scenes VIDEO OUTDIR [--th 0.3] [--max 24]              按画面切换抽关键帧
  python vtool.py shots VIDEO OUTDIR [--th 10]                          画面拆解：切镜头，每镜头首/中/尾三帧拼图 + shots.json
  python vtool.py sheet VIDEO OUT.jpg [--ss 0] [--to END] [--n 24]      带时间码的联系表（看转场、变装细节）
  python vtool.py beats VIDEO OUT.json [--shots shots.json]            节拍/重音/静音点，并把切点对齐到节拍（卡点）
  python vtool.py motion VIDEO OUT.json [--shots shots.json]           测运镜：推拉、上下、左右和速度曲线（需 opencv）
  python vtool.py flow VIDEO OUTDIR                                     连续运动时间线：逐帧推拉/平移/旋转/模糊/画面变化，自动找转场并出逐帧图（需 opencv）
  python vtool.py ocr IMG [IMG ...] [--out OUT.txt]                    图片文字识别（图文帖、截图）
  python vtool.py subcheck VIDEO W.json OUT.json [--all]                用画面字幕校对转写：只在数字和低置信度处截字幕 OCR（需 rapidocr）
"""
import argparse, os, subprocess, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152 Safari/537.36"

def fetch(a):
    import requests
    h = {"User-Agent": UA}
    if a.referer: h["Referer"] = a.referer
    with requests.get(a.url, headers=h, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(a.out, "wb") as f:
            for c in r.iter_content(1 << 20): f.write(c)
    print("saved", a.out, os.path.getsize(a.out))

def bili_audio(a):
    os.makedirs(a.outdir, exist_ok=True)
    code = "import sys;from bili_cli.cli import cli;sys.argv=['bili','audio',sys.argv[1],'--no-split','-o',sys.argv[2]];cli()"
    subprocess.run([PY, "-c", code, a.bv, a.outdir], check=True)
    print("\n".join(glob.glob(os.path.join(a.outdir, "*.m4a"))))

def yt_audio(a):
    os.makedirs(a.outdir, exist_ok=True)
    cmd = [PY, "-m", "yt_dlp", "-x", "--audio-format", "m4a", "-o", os.path.join(a.outdir, "%(id)s.%(ext)s")]
    import shutil
    if shutil.which("node"): cmd += ["--js-runtimes", "node"]
    if a.cookies: cmd += ["--cookies", a.cookies]
    if a.browser: cmd += ["--cookies-from-browser", a.browser]
    subprocess.run(cmd + [a.url], check=True)

def transcribe(a):
    from faster_whisper import WhisperModel
    import opencc
    wav = a.out + ".16k.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.audio, "-ar", "16000", "-ac", "1", wav], check=True)
    mdir = os.environ.get("VN_MODEL") or os.path.join(HERE, "models", "fw-small")
    m = WhisperModel(mdir, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
    import wave, numpy as np  # 自己读 wav 传数组：避开新版 PyAV 与 faster-whisper 的兼容问题
    with wave.open(wav) as w: audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    kw = dict(vad_filter=True, word_timestamps=bool(a.words))
    if a.lang != "auto": kw["language"] = a.lang
    if a.prompt: kw["initial_prompt"] = a.prompt
    segs, info = m.transcribe(audio, **kw)
    segs = list(segs)
    if not segs:  # 纯音乐/歌声常被静音检测滤掉：关掉再试一次
        kw["vad_filter"] = False
        segs, info = m.transcribe(audio, **kw); segs = list(segs)
    cc = opencc.OpenCC("t2s")
    with open(a.out, "w", encoding="utf-8") as f:
        for s in segs:
            t = s.text.strip()
            if info.language == "zh": t = cc.convert(t)
            f.write(f"[{int(s.start//60):02d}:{int(s.start%60):02d}] {t}\n")
    if a.words:
        import json
        ws = [dict(t0=round(w.start, 2), t1=round(w.end, 2), w=cc.convert(w.word) if info.language == "zh" else w.word, p=round(w.probability, 2))
              for s in segs for w in (s.words or [])]
        with open(a.words, "w", encoding="utf-8") as f: json.dump(ws, f, ensure_ascii=False)
    os.remove(wav)
    print("done", info.language, round(info.duration, 1), "s ->", a.out)

def scenes(a):
    os.makedirs(a.outdir, exist_ok=True)
    pat = os.path.join(a.outdir, "f_%03d.jpg")
    vf = f"select='gt(scene,{a.th})',scale=1280:-2,showinfo"
    p = subprocess.run(["ffmpeg", "-hide_banner", "-y", "-i", a.video, "-vf", vf, "-vsync", "vfr", "-q:v", "4", "-frames:v", str(a.max), pat], capture_output=True, text=True)
    import re
    ts = re.findall(r"pts_time:([\d.]+)", p.stderr)
    files = sorted(glob.glob(os.path.join(a.outdir, "f_*.jpg")))
    if len(files) < 3:  # 画面几乎不变：退回按固定间隔抽帧
        for f in files: os.remove(f)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.video], capture_output=True, text=True).stdout or 60)
        step = max(dur / a.max, 5)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", a.video, "-vf", f"fps=1/{step:.2f},scale=1280:-2", "-q:v", "4", "-frames:v", str(a.max), pat], check=True)
        files = sorted(glob.glob(os.path.join(a.outdir, "f_*.jpg")))
        ts = [f"{i*step:.1f}" for i in range(len(files))]
    for f, t in zip(files, ts):
        s = float(t); new = os.path.join(a.outdir, f"t{int(s//60):02d}m{int(s%60):02d}s.jpg")
        os.replace(f, new); print(new)

# ---------- 画面拆解 ----------
def _probe(v):
    import json
    o = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", v], capture_output=True, text=True).stdout)
    vs = next(s for s in o["streams"] if s["codec_type"] == "video")
    n, d = vs.get("r_frame_rate", "30/1").split("/")
    return dict(dur=float(o["format"]["duration"]), w=vs["width"], h=vs["height"], fps=round(float(n) / float(d or 1), 2),
                audio=any(s["codec_type"] == "audio" for s in o["streams"]))

def _tc(t): return f"{int(t//60):02d}:{t%60:05.2f}"

def _tile(video, out, ss, to, n, cols, width, fps=30.0):
    """在 [ss,to] 内按帧号均匀取 n 帧（含首尾）拼成一张图，左上角印时间码；ffmpeg 没有 drawtext 时退回不印字。"""
    span = max(to - ss, 0.05); last = max(int(span * fps) - 1, 0); rows = -(-n // cols)
    idx = sorted({round(k * last / (n - 1)) if n > 1 else 0 for k in range(n)})
    base = "select='" + "+".join(f"eq(n\\,{i})" for i in idx) + f"',scale={width}:-2"
    txt = f",drawtext=text='%{{pts\\:hms\\:{ss:.3f}}}':x=4:y=4:fontsize={max(width//16,12)}:fontcolor=yellow:box=1:boxcolor=black@0.6"
    for vf in (base + txt, base):
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{ss:.3f}", "-t", f"{span + 0.2:.3f}", "-i", video,
                            "-vf", vf + f",tile={cols}x{-(-len(idx) // cols)}:padding=2", "-vsync", "vfr", "-frames:v", "1", "-q:v", "4", out], capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(out): return
    raise SystemExit(r.stderr[-500:])

def _cuts(video, th):
    import re
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vf", f"scdet=threshold={th},metadata=print", "-an", "-f", "null", "-"], capture_output=True, text=True)
    return [float(t) for t in re.findall(r"lavfi\.scd\.time=([\d.]+)", p.stderr)]

def _frame_stats(video, t):
    """单帧的亮度/饱和度/色相均值（0-255）和黑边裁切，用来描述色调、判断宽银幕遮幅。"""
    import re
    p = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", "signalstats,metadata=print,cropdetect=24:2:0", "-f", "null", "-"], capture_output=True, text=True)
    g = lambda k: (re.findall(rf"lavfi\.signalstats\.{k}=([\d.]+)", p.stderr) or [None])[0]
    crop = (re.findall(r"crop=(\d+:\d+:\d+:\d+)", p.stderr) or [None])[-1]
    return dict(luma=g("YAVG") and round(float(g("YAVG"))), sat=g("SATAVG") and round(float(g("SATAVG"))), hue=g("HUEAVG") and round(float(g("HUEAVG"))), crop=crop)

def shots(a):
    import json
    os.makedirs(a.outdir, exist_ok=True)
    info = _probe(a.video)
    cuts = [c for c in _cuts(a.video, a.th) if 0.15 < c < info["dur"] - 0.1]
    edges = [0.0] + cuts + [info["dur"]]
    res = []
    for i in range(len(edges) - 1):
        s, e = edges[i], edges[i + 1]
        img = os.path.join(a.outdir, f"s{i+1:02d}_{int(s//60):02d}m{s%60:05.2f}s.jpg")
        pad = min(0.05, (e - s) / 4)
        _tile(a.video, img, s + pad, e - pad, 3, 3, 480, info["fps"])
        st = _frame_stats(a.video, (s + e) / 2)
        res.append(dict(shot=i + 1, start=round(s, 2), end=round(e, 2), dur=round(e - s, 2), image=os.path.basename(img), **st))
    d = [r["dur"] for r in res]
    meta = dict(video=os.path.basename(a.video), **info, shots=len(res), avg_shot=round(sum(d) / len(d), 2), cuts_per_min=round(len(cuts) / info["dur"] * 60, 1), threshold=a.th, list=res)
    with open(os.path.join(a.outdir, "shots.json"), "w", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"{info['w']}x{info['h']} {info['fps']}fps {info['dur']:.2f}s  镜头 {len(res)} 个，平均 {meta['avg_shot']}s，每分钟 {meta['cuts_per_min']} 刀")
    for r in res: print(f"S{r['shot']:02d} {_tc(r['start'])}-{_tc(r['end'])} ({r['dur']}s) 亮度{r['luma']} 饱和{r['sat']} 裁切{r['crop']}  {r['image']}")
    if len(res) == 1: print("只切出 1 个镜头：可能是一镜到底或柔性转场，试试 --th 5，或用 sheet 看细节")

def sheet(a):
    info = _probe(a.video)
    to = a.to if a.to else info["dur"]
    _tile(a.video, a.out, a.ss, to, a.n, a.cols, a.width, info["fps"])
    print(a.out, f"{_tc(a.ss)}-{_tc(to)} 共 {a.n} 格，每格 {(to-a.ss)/a.n:.3f}s")

def beats(a):
    """纯 numpy：频谱通量求重音 → 自相关估 BPM → 拟合节拍网格；另找静音/断音点。切点对齐用 --shots。"""
    import json, numpy as np
    sr, hop, nfft = 22050, 512, 2048
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", a.video, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
    y = np.frombuffer(raw, dtype=np.float32)
    if y.size < sr: raise SystemExit("没有音轨或音频太短")
    fr = np.lib.stride_tricks.sliding_window_view(np.pad(y, (nfft // 2, nfft // 2)), nfft)[::hop] * np.hanning(nfft)
    S = np.log1p(10 * np.abs(np.fft.rfft(fr, axis=1)))
    flux = np.r_[0, np.maximum(S[1:] - S[:-1], 0).sum(1)]
    env = (flux - flux.mean()) / (flux.std() + 1e-9)
    t = np.arange(len(env)) * hop / sr
    rms = np.sqrt((fr ** 2).mean(1)); rms = rms / (rms.max() + 1e-9)
    # 重音：局部最大且高于均值+1σ，间隔 ≥ 0.1s
    w = int(0.1 * sr / hop); on = []
    for i in range(1, len(env) - 1):
        if env[i] > 1 and env[i] == env[max(0, i - w):i + w + 1].max(): on.append(i)
    # BPM：自相关在 60-200 BPM 里找峰
    ac = np.correlate(env, env, "full")[len(env) - 1:]
    lags = np.arange(int(60 / 200 * sr / hop), int(60 / 60 * sr / hop) + 1)
    lag = lags[np.argmax(ac[lags] * np.exp(-0.5 * (np.log2(60 * sr / hop / lags / 120)) ** 2))]  # 偏好 120 附近，避免倍频
    bpm = 60 * sr / hop / lag
    emx = np.array([env[max(0, i - 2):i + 3].max() for i in range(len(env))]) * (rms > 0.08)  # 容忍 ±2 帧，静音处不算拍
    phase = max(range(lag), key=lambda p: emx[p::lag].sum())
    grid = t[phase::lag]
    # 静音/断音：音量 < 8% 持续 ≥ 60ms
    quiet, i = [], 0
    while i < len(rms):
        if rms[i] < 0.08:
            j = i
            while j < len(rms) and rms[j] < 0.08: j += 1
            if (j - i) * hop / sr >= 0.06: quiet.append([round(float(t[i]), 2), round(float(t[min(j, len(t) - 1)]), 2)])
            i = j
        else: i += 1
    out = dict(bpm=round(float(bpm), 1), beat_interval=round(60 / bpm, 3), beats=[round(float(x), 2) for x in grid],
               accents=[dict(t=round(float(t[i]), 2), strength=round(float(env[i]), 1)) for i in on], silences=quiet)
    if a.shots:
        sh = json.load(open(a.shots, encoding="utf-8")); al = []
        for r in sh["list"][1:]:
            c = r["start"]; nb = min(grid, key=lambda b: abs(b - c)) if len(grid) else None
            na = min(out["accents"], key=lambda x: abs(x["t"] - c)) if out["accents"] else None
            ns = next((q for q in quiet if q[0] - 0.08 <= c <= q[1] + 0.08), None)
            al.append(dict(cut=c, to_shot=r["shot"], nearest_beat=round(float(nb), 2), beat_offset_ms=int((c - nb) * 1000),
                           nearest_accent=na and na["t"], accent_offset_ms=na and int((c - na["t"]) * 1000), in_silence=ns))
        out["cut_alignment"] = al
    with open(a.out, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"BPM≈{out['bpm']}（一拍 {out['beat_interval']}s），重音 {len(on)} 个，静音/断音 {quiet}")
    print("最强重音:", sorted(out["accents"], key=lambda x: -x["strength"])[:6])
    for x in out.get("cut_alignment", []):
        tag = "卡拍" if abs(x["beat_offset_ms"]) <= 70 or (x["accent_offset_ms"] is not None and abs(x["accent_offset_ms"]) <= 70) else "不在拍上"
        print(f"切点 {x['cut']}s → S{x['to_shot']:02d}: 离节拍 {x['beat_offset_ms']}ms，离重音 {x['accent_offset_ms']}ms，静音段 {x['in_silence']} [{tag}]")

def motion(a):
    """用特征点估计相邻帧的相似变换：画面整体缩小=镜头后拉（或变焦拉远），内容下移=镜头上移/上摇。
    手持且主体大面积运动时估计会失真，按 confidence 判断可信度。"""
    import json
    try:
        import cv2, numpy as np
    except ImportError:
        raise SystemExit("缺少 opencv：$PY -m pip install opencv-python-headless")
    cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS) or 30; frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY); h, w = g.shape
        frames.append(cv2.resize(g, (640, int(640 * h / w))) if w > 640 else g)
    H, W = frames[0].shape
    shots = json.load(open(a.shots, encoding="utf-8"))["list"] if a.shots else [dict(shot=1, start=0, end=len(frames) / fps)]
    orb = cv2.ORB_create(1500); bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    step = max(1, round(fps / 10))  # 每秒约 10 次估计
    out = []
    for sh in shots:
        i0, i1 = int(sh["start"] * fps) + 1, int(sh["end"] * fps) - 1
        S, X, Y, ok_n, tot, prof = 1.0, 0.0, 0.0, 0, 0, []
        for i in range(i0, i1 - step, step):
            tot += 1
            k1, d1 = orb.detectAndCompute(frames[i], None); k2, d2 = orb.detectAndCompute(frames[i + step], None)
            if d1 is None or d2 is None: continue
            m = bf.match(d1, d2)
            if len(m) < 30: continue
            p1 = np.float32([k1[x.queryIdx].pt for x in m]); p2 = np.float32([k2[x.trainIdx].pt for x in m])
            M, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=3)
            if M is None or inl.sum() < 25: continue
            sc = float(np.hypot(M[0, 0], M[1, 0]))
            if not 0.85 < sc < 1.18: continue  # 跳变多半是主体运动或模糊，丢掉
            # 以画面中心为基准的平移（去掉缩放带来的中心偏移），换算成画面宽/高的百分比
            cx, cy = W / 2, H / 2
            tx = M[0, 0] * cx + M[0, 1] * cy + M[0, 2] - cx; ty = M[1, 0] * cx + M[1, 1] * cy + M[1, 2] - cy
            S *= sc; X += tx / W * 100; Y += ty / H * 100; ok_n += 1
            prof.append(dict(t=round(i / fps, 2), zoom=round((sc - 1) * 100 * fps / step, 1), x=round(tx / W * 100 * fps / step, 1), y=round(ty / H * 100 * fps / step, 1)))
        conf = round(ok_n / tot, 2) if tot else 0
        words = []
        if S < 0.95: words.append(f"后拉/拉远（画面缩到 {S:.2f} 倍）")
        elif S > 1.05: words.append(f"前推/推近（画面放大到 {S:.2f} 倍）")
        if Y > 5: words.append(f"镜头上移/上摇（内容下移 {Y:.0f}% 画高）")
        elif Y < -5: words.append(f"镜头下移/下摇（内容上移 {-Y:.0f}% 画高）")
        if X > 5: words.append(f"镜头左移/左摇（内容右移 {X:.0f}% 画宽）")
        elif X < -5: words.append(f"镜头右移/右摇（内容左移 {-X:.0f}% 画宽）")
        if not words: words.append("基本固定")
        # 速度曲线：前 1/3 和后 1/3 的运动量对比
        mag = [abs(p["zoom"]) + abs(p["x"]) + abs(p["y"]) for p in prof]
        curve = ""
        if len(mag) >= 6 and sum(mag) > 0:
            n3 = len(mag) // 3; a_, c_ = sum(mag[:n3]) / n3, sum(mag[-n3:]) / n3
            curve = "先快后慢（缓出）" if a_ > 2 * c_ else "先慢后快（缓入）" if c_ > 2 * a_ else "匀速"
        r = dict(shot=sh["shot"], start=sh["start"], end=sh["end"], scale=round(S, 3), dx_pct=round(X, 1), dy_pct=round(Y, 1),
                 move="，".join(words), speed_curve=curve, confidence=conf, profile=prof)
        out.append(r)
        warn = "（可信度低：手持或主体大面积运动，请结合看图判断）" if conf < 0.5 else ""
        print(f"S{sh['shot']:02d} {sh['start']}-{sh['end']}s: {r['move']}；{curve}；可信度 {conf}{warn}")
    with open(a.out, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=1)

def flow(a):
    """逐帧分析整条视频（不按镜头切）：相邻帧的缩放、平移、旋转、清晰度、亮度、画面变化。
    用来看连续运镜和柔性转场（形状匹配、遮挡、甩镜、穿越推进、溶解），这些 shots 往往切不出来。"""
    import json
    try:
        import cv2, numpy as np
    except ImportError:
        raise SystemExit("缺少 opencv：$PY -m pip install opencv-python-headless")
    os.makedirs(a.outdir, exist_ok=True)
    cap = cv2.VideoCapture(a.video); fps = cap.get(cv2.CAP_PROP_FPS) or 30; frames = []
    while True:
        ok, f = cap.read()
        if not ok: break
        h, w = f.shape[:2]; f = cv2.resize(f, (360, int(360 * h / w)))
        frames.append(f)
    if len(frames) < 3: raise SystemExit("视频太短")
    H, W = frames[0].shape[:2]
    orb = cv2.ORB_create(1000); bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    def hist(f):
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hh = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256]); return cv2.normalize(hh, hh).flatten()
    rows = []; prev = frames[0]; pg = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY); ph = hist(prev)
    for i in range(1, len(frames)):
        f = frames[i]; g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY); hh = hist(f)
        r = dict(t=round(i / fps, 3), zoom=None, x=None, y=None, rot=None, ok=0)
        k1, d1 = orb.detectAndCompute(pg, None); k2, d2 = orb.detectAndCompute(g, None)
        if d1 is not None and d2 is not None:
            m = bf.match(d1, d2)
            if len(m) >= 20:
                p1 = np.float32([k1[x.queryIdx].pt for x in m]); p2 = np.float32([k2[x.trainIdx].pt for x in m])
                M, inl = cv2.estimateAffinePartial2D(p1, p2, method=cv2.RANSAC, ransacReprojThreshold=3)
                if M is not None and inl.sum() >= 15:
                    sc = float(np.hypot(M[0, 0], M[1, 0])); ang = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
                    cx, cy = W / 2, H / 2
                    tx = M[0, 0] * cx + M[0, 1] * cy + M[0, 2] - cx; ty = M[1, 0] * cx + M[1, 1] * cy + M[1, 2] - cy
                    # 每秒速率：缩放%/s、平移 画宽%/s、旋转 度/s
                    r.update(zoom=round((sc - 1) * 100 * fps, 1), x=round(tx / W * 100 * fps, 1), y=round(ty / H * 100 * fps, 1),
                             rot=round(ang * fps, 1), ok=int(inl.sum()))
        r["change"] = round(float(cv2.compareHist(ph, hh, cv2.HISTCMP_BHATTACHARYYA)), 3)   # 0 相同，1 完全不同
        r["sharp"] = round(float(cv2.Laplacian(g, cv2.CV_64F).var()), 1)
        r["luma"] = round(float(g.mean()), 1)
        rows.append(r); pg, ph = g, hh
    # ---- 找事件：画面变化尖峰/持续升高、大幅运动、明显模糊 ----
    ch = np.array([r["change"] for r in rows]); sh = np.array([r["sharp"] for r in rows])
    mag = np.array([abs(r["zoom"] or 0) + abs(r["x"] or 0) + abs(r["y"] or 0) + abs(r["rot"] or 0) * 2 for r in rows])
    lost = np.array([r["ok"] == 0 for r in rows])
    base_ch = np.median(ch) + 1e-6; base_sh = np.median(sh) + 1e-6; base_mag = np.median(mag) + 1e-6
    flag = (ch > max(0.25, base_ch * 4)) | (mag > max(60, base_mag * 4)) | (sh < base_sh * 0.35) | lost
    events = []; i = 0
    while i < len(rows):
        if flag[i]:
            j = i
            while j + 1 < len(rows) and (flag[j + 1] or (j + 2 < len(rows) and flag[j + 2])): j += 1
            seg = rows[i:j + 1]; c = ch[i:j + 1]; mg = mag[i:j + 1]
            kinds = []
            if c.max() > 0.5 and (j - i) <= 1: kinds.append("硬切")
            elif c.max() > 0.25: kinds.append("柔性转场（溶解/形状匹配/遮挡，需看逐帧图）")
            zs = [r["zoom"] for r in seg if r["zoom"] is not None]; xs = [r["x"] for r in seg if r["x"] is not None]
            ys = [r["y"] for r in seg if r["y"] is not None]; rs = [r["rot"] for r in seg if r["rot"] is not None]
            if zs and abs(np.mean(zs)) > 15: kinds.append("快速推进" if np.mean(zs) > 0 else "快速拉远")
            if xs and abs(np.mean(xs)) > 40: kinds.append("快速横移/甩镜")
            if ys and abs(np.mean(ys)) > 40: kinds.append("快速升降/上下甩")
            if rs and abs(np.mean(rs)) > 20: kinds.append("旋转")
            if (sh[i:j + 1] < base_sh * 0.35).any(): kinds.append("运动模糊或失焦")
            if lost[i:j + 1].mean() > 0.5: kinds.append("特征点丢失（大幅变化、遮挡或全新画面）")
            t0, t1 = rows[i]["t"], rows[j]["t"]
            events.append(dict(start=round(max(0, t0 - 1 / fps), 2), end=round(t1, 2), kinds=kinds or ["画面变化"],
                               peak_change=round(float(c.max()), 2), peak_motion=round(float(mg.max()), 1)))
            i = j + 1
        else: i += 1
    # ---- 时间线图：变化、缩放、平移、旋转、清晰度五条曲线 ----
    Wc, Hc, pad = 1200, 600, 40; img = np.full((Hc, Wc, 3), 255, np.uint8); T = rows[-1]["t"]
    tx_ = lambda t: int(pad + (Wc - 2 * pad) * t / T)
    lanes = [("画面变化 change", [r["change"] for r in rows], (0, 0, 200), 1.0, False),
             ("缩放 zoom %/s (+推 -拉)", [r["zoom"] for r in rows], (200, 100, 0), None, True),
             ("横移 x %/s", [r["x"] for r in rows], (0, 150, 0), None, True),
             ("升降 y %/s", [r["y"] for r in rows], (150, 0, 150), None, True),
             ("清晰度 sharp", [r["sharp"] for r in rows], (100, 100, 100), None, False)]
    lh = (Hc - 2 * pad) / len(lanes)
    for e in events: cv2.rectangle(img, (tx_(e["start"]), pad), (tx_(e["end"]) + 2, Hc - pad), (220, 235, 255), -1)
    for k, (name, vals, col, vmax, signed) in enumerate(lanes):
        y0 = int(pad + k * lh); y1 = int(y0 + lh - 8)
        v = np.array([np.nan if x is None else x for x in vals], float)
        vm = vmax or (np.nanpercentile(np.abs(v), 98) if np.isfinite(v).any() else 1) or 1
        mid = (y0 + y1) // 2 if signed else y1
        cv2.line(img, (pad, mid), (Wc - pad, mid), (210, 210, 210), 1)
        pts = []
        for r, x in zip(rows, v):
            if np.isnan(x): pts.append(None); continue
            yy = mid - (x / vm) * ((y1 - y0) / 2 if signed else (y1 - y0)); pts.append((tx_(r["t"]), int(np.clip(yy, y0, y1))))
        for p, q in zip(pts, pts[1:]):
            if p and q: cv2.line(img, p, q, col, 2)
        cv2.putText(img, name.encode("ascii", "ignore").decode().strip() or name, (pad + 4, y0 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
    for s_ in range(int(T) + 1): cv2.putText(img, f"{s_}s", (tx_(s_) - 6, Hc - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.imwrite(os.path.join(a.outdir, "flow_timeline.png"), img)
    # ---- 每个事件自动出一张逐帧图 ----
    for n, e in enumerate(events[:a.max_events], 1):
        ss = max(0, e["start"] - 0.15); to = min(T, e["end"] + 0.15)
        out = os.path.join(a.outdir, f"e{n:02d}_{ss:05.2f}s.jpg"); e["sheet"] = os.path.basename(out)
        try: _tile(a.video, out, ss, to, min(12, max(6, int((to - ss) * fps))), 4, 300, fps)
        except SystemExit: pass
    with open(os.path.join(a.outdir, "flow.json"), "w", encoding="utf-8") as f:
        json.dump(dict(fps=fps, events=events, frames=rows), f, ensure_ascii=False)
    print(f"{len(rows)+1} 帧，找到 {len(events)} 个运动/转场事件 → {a.outdir}/flow_timeline.png")
    for n, e in enumerate(events, 1):
        print(f"E{n:02d} {e['start']:.2f}-{e['end']:.2f}s  {' + '.join(e['kinds'])}  (变化峰值 {e['peak_change']}, 运动峰值 {e['peak_motion']})  {e.get('sheet','')}")

def ocr_images(a):
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        raise SystemExit("缺少 OCR：$PY -m pip install rapidocr_onnxruntime")
    import numpy as np
    o = RapidOCR(); lines = []
    for f in a.images:
        r, _ = o(f)
        r = sorted([x for x in (r or []) if float(x[2]) > 0.6], key=lambda x: (round(np.array(x[0])[:, 1].mean() / 20), np.array(x[0])[:, 0].min()))
        lines.append(f"--- {os.path.basename(f)}\n" + "\n".join(x[1] for x in r))
    txt = "\n".join(lines)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh: fh.write(txt)
    print(txt)

def subcheck(a):
    """用画面里烧录的字幕校对语音转写。默认只在"可疑处"截字幕：含数字且置信度<0.9 的词、或置信度<0.4 的词；
    相距 1 秒内的合并成一次截图。--all 则逐句 OCR 全部字幕（慢，约每张 1 秒）。"""
    import json, re, numpy as np
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        raise SystemExit("缺少 OCR：$PY -m pip install rapidocr_onnxruntime")
    if not a.all and not a.words: raise SystemExit("缺少 words.json：先 transcribe ... --words W.json，或用 --all 提取全部字幕")
    ocr = RapidOCR()
    info = _probe(a.video); dur = info["dur"]
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", a.video], capture_output=True, text=True).stdout)
    vs = next(s for s in pr["streams"] if s["codec_type"] == "video"); W, H = vs["width"], vs["height"]
    def grab(t, crop=None):
        vf = ["-vf", f"crop={W}:{crop[1]}:0:{crop[0]}"] if crop else []
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", a.video, "-frames:v", "1", *vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(crop[1] if crop else H, W, 3)
    def read(img):
        r, _ = ocr(img, use_cls=False)
        r = [x for x in (r or []) if float(x[2]) > 0.6]
        return "".join(x[1] for x in sorted(r, key=lambda x: (round(np.array(x[0])[:, 1].mean() / 40), np.array(x[0])[:, 0].min())))
    # 1) 找字幕带：均匀取 8 帧整图，统计画面下 60% 里文字框的位置
    ys, hs = [], []
    for k in range(8):
        r, _ = ocr(grab(dur * (k + 0.5) / 8), use_cls=False)
        for box, txt, sc in (r or []):
            b = np.array(box); yc = b[:, 1].mean()
            if yc > H * 0.4 and len(txt) >= 2 and float(sc) > 0.6: ys.append(yc); hs.append(b[:, 1].max() - b[:, 1].min())
    if not ys: raise SystemExit("画面里没找到字幕，跳过字幕校对")
    yc, h = float(np.median(ys)), float(np.median(hs))
    y0 = max(0, int(yc - 1.6 * h)) // 2 * 2; bh = min(H - y0, int(3.2 * h)) // 2 * 2
    out = dict(band=[y0, y0 + bh], items=[])
    if a.all:
        fps = 2; raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", a.video, "-vf", f"fps={fps},crop={W}:{bh}:0:{y0}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        frames = np.frombuffer(raw, np.uint8).reshape(-1, bh, W, 3); last = None
        for i, f in enumerate(frames):
            g = f.mean(2)
            if last is not None and np.abs(g - last).mean() < 6: continue
            last = g; txt = read(f)
            if txt and (not out["items"] or out["items"][-1]["sub"] != txt): out["items"].append(dict(t=round(i / fps, 1), sub=txt))
    else:
        ws = json.load(open(a.words, encoding="utf-8"))
        num = re.compile(r"[0-9一二两三四五六七八九十百千万几半]")
        sus = [w for w in ws if (num.search(w["w"]) and w["p"] < 0.9) or w["p"] < 0.4]
        groups = []
        for w in sus:
            t = (w["t0"] + w["t1"]) / 2
            if groups and t - groups[-1]["t"] <= 1.0: groups[-1]["asr"].append(w)
            else: groups.append(dict(t=t, asr=[w]))
        for g in groups:
            txt = read(grab(g["t"], (y0, bh)))
            ctx = "".join(w["w"] for w in ws if g["t"] - 1.5 <= (w["t0"] + w["t1"]) / 2 <= g["t"] + 1.5)
            out["items"].append(dict(t=round(g["t"], 1), asr_context=ctx, doubtful=[f'{w["w"]}({w["p"]})' for w in g["asr"]], sub=txt))
    with open(a.out, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"字幕带 y={y0}-{y0+bh}，截图识别 {len(out['items'])} 处 -> {a.out}")
    for it in out["items"][:80]:
        print(f"{int(it['t']//60):02d}:{it['t']%60:04.1f}  " + (f"语音:{it['asr_context']}  存疑:{' '.join(it['doubtful'])}  字幕:{it['sub']}" if "asr_context" in it else it["sub"]))

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
x = sp.add_parser("fetch"); x.add_argument("url"); x.add_argument("out"); x.add_argument("--referer", default="https://www.douyin.com/"); x.set_defaults(fn=fetch)
x = sp.add_parser("bili-audio"); x.add_argument("bv"); x.add_argument("outdir"); x.set_defaults(fn=bili_audio)
x = sp.add_parser("yt-audio"); x.add_argument("url"); x.add_argument("outdir"); x.add_argument("--cookies"); x.add_argument("--browser", help="例如 chrome，需用户同意读取浏览器 Cookie"); x.set_defaults(fn=yt_audio)
x = sp.add_parser("transcribe"); x.add_argument("audio"); x.add_argument("out"); x.add_argument("--lang", default="zh"); x.add_argument("--prompt"); x.add_argument("--words", help="另存逐词时间和置信度（给 subcheck 用）"); x.set_defaults(fn=transcribe)
x = sp.add_parser("scenes"); x.add_argument("video"); x.add_argument("outdir"); x.add_argument("--th", type=float, default=0.3); x.add_argument("--max", type=int, default=24); x.set_defaults(fn=scenes)
x = sp.add_parser("shots"); x.add_argument("video"); x.add_argument("outdir"); x.add_argument("--th", type=float, default=10, help="scdet 阈值，越小切得越碎"); x.set_defaults(fn=shots)
x = sp.add_parser("sheet"); x.add_argument("video"); x.add_argument("out"); x.add_argument("--ss", type=float, default=0); x.add_argument("--to", type=float); x.add_argument("--n", type=int, default=24); x.add_argument("--cols", type=int, default=6); x.add_argument("--width", type=int, default=320); x.set_defaults(fn=sheet)
x = sp.add_parser("beats"); x.add_argument("video"); x.add_argument("out"); x.add_argument("--shots"); x.set_defaults(fn=beats)
x = sp.add_parser("flow"); x.add_argument("video"); x.add_argument("outdir"); x.add_argument("--max-events", dest="max_events", type=int, default=12); x.set_defaults(fn=flow)
x = sp.add_parser("ocr"); x.add_argument("images", nargs="+"); x.add_argument("--out"); x.set_defaults(fn=ocr_images)
x = sp.add_parser("subcheck"); x.add_argument("video"); x.add_argument("words", nargs="?"); x.add_argument("out"); x.add_argument("--all", action="store_true", help="逐句 OCR 全部字幕（慢）"); x.set_defaults(fn=subcheck)
x = sp.add_parser("motion"); x.add_argument("video"); x.add_argument("out"); x.add_argument("--shots"); x.set_defaults(fn=motion)
a = ap.parse_args(); a.fn(a)
