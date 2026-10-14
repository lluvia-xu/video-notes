#!/usr/bin/env python3
"""video-notes 工具。用法（PY 为 setup.sh 建好的 venv 里的 python）：
  python vtool.py fetch URL OUT [--referer R]        下载媒体直链（抖音等）
  python vtool.py bili-audio BV号或链接 OUTDIR        B站下载音频（bili-cli）
  python vtool.py yt-audio URL OUTDIR [--cookies F | --browser chrome]   用 yt-dlp 下载音频（YouTube 等）
  python vtool.py transcribe AUDIO OUT.txt [--lang zh] [--prompt 术语]   本地语音识别
  python vtool.py scenes VIDEO OUTDIR [--th 0.3] [--max 24]              按画面切换抽关键帧
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
    kw = dict(vad_filter=True)
    if a.lang != "auto": kw["language"] = a.lang
    if a.prompt: kw["initial_prompt"] = a.prompt
    segs, info = m.transcribe(wav, **kw)
    segs = list(segs)
    if not segs:  # 纯音乐/歌声常被静音检测滤掉：关掉再试一次
        kw["vad_filter"] = False
        segs, info = m.transcribe(wav, **kw); segs = list(segs)
    cc = opencc.OpenCC("t2s")
    with open(a.out, "w", encoding="utf-8") as f:
        for s in segs:
            t = s.text.strip()
            if info.language == "zh": t = cc.convert(t)
            f.write(f"[{int(s.start//60):02d}:{int(s.start%60):02d}] {t}\n")
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

ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
x = sp.add_parser("fetch"); x.add_argument("url"); x.add_argument("out"); x.add_argument("--referer", default="https://www.douyin.com/"); x.set_defaults(fn=fetch)
x = sp.add_parser("bili-audio"); x.add_argument("bv"); x.add_argument("outdir"); x.set_defaults(fn=bili_audio)
x = sp.add_parser("yt-audio"); x.add_argument("url"); x.add_argument("outdir"); x.add_argument("--cookies"); x.add_argument("--browser", help="例如 chrome，需用户同意读取浏览器 Cookie"); x.set_defaults(fn=yt_audio)
x = sp.add_parser("transcribe"); x.add_argument("audio"); x.add_argument("out"); x.add_argument("--lang", default="zh"); x.add_argument("--prompt"); x.set_defaults(fn=transcribe)
x = sp.add_parser("scenes"); x.add_argument("video"); x.add_argument("outdir"); x.add_argument("--th", type=float, default=0.3); x.add_argument("--max", type=int, default=24); x.set_defaults(fn=scenes)
a = ap.parse_args(); a.fn(a)
