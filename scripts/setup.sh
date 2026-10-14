#!/usr/bin/env bash
# video-notes 一次性安装：建 Python 环境、装依赖、下载语音识别模型（共约 1GB）
# 用法：bash setup.sh [安装目录]
#   安装目录默认 ~/.video-notes；Cowork 用户请传入连接文件夹里的 _工具 目录
# 可分多次运行：已完成的步骤会跳过，模型下载支持断点续传。
set -euo pipefail
VN_HOME="${1:-${VN_HOME:-$HOME/.video-notes}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$VN_HOME/models/fw-small"
echo "安装目录: $VN_HOME"

command -v python3 >/dev/null || { echo "缺少 python3（3.9+），请先安装"; exit 1; }
command -v ffmpeg  >/dev/null || echo "⚠️ 缺少 ffmpeg：macOS 用 'brew install ffmpeg'，Ubuntu 用 'sudo apt install ffmpeg'"

if [ ! -x "$VN_HOME/venv/bin/python" ]; then
  # --copies：目录被挂载进虚拟机、或换了会话路径时也能用
  python3 -m venv --copies "$VN_HOME/venv"
fi
PY="$VN_HOME/venv/bin/python"
if ! "$PY" -c "import faster_whisper, yt_dlp, bili_cli, opencc, requests" 2>/dev/null; then
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q yt-dlp requests opencc-python-reimplemented faster-whisper bilibili-cli
fi

cp "$HERE/vtool.py" "$VN_HOME/vtool.py"

cd "$VN_HOME/models/fw-small"
BASE=https://huggingface.co/Systran/faster-whisper-small/resolve/main
for f in config.json tokenizer.json vocabulary.txt; do [ -s "$f" ] || curl -sL -o "$f" "$BASE/$f"; done
EXPECT=483546902
SIZE=$(stat -c%s model.bin 2>/dev/null || stat -f%z model.bin 2>/dev/null || echo 0)
if [ "$SIZE" != "$EXPECT" ]; then
  echo "下载语音识别模型（约 480MB，可续传）..."
  curl -L -C - -o model.bin "$BASE/model.bin" || true
  SIZE=$(stat -c%s model.bin 2>/dev/null || stat -f%z model.bin 2>/dev/null || echo 0)
  [ "$SIZE" = "$EXPECT" ] || { echo "模型还没下完（$SIZE / $EXPECT 字节），请再运行一次 setup.sh 续传"; exit 2; }
fi

"$PY" -c "import faster_whisper, yt_dlp; print('✅ video-notes 安装完成')"
echo "以后调用：$PY $VN_HOME/vtool.py <子命令> ..."
