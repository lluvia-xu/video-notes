# 工具说明

- `scripts/setup.sh [VN_HOME]`：建 venv（`--copies`）、安装 yt-dlp / requests / opencc-python-reimplemented / faster-whisper / bilibili-cli / opencv-python-headless（运镜）/ rapidocr_onnxruntime（字幕 OCR）、把 vtool.py 复制进 VN_HOME、下载 `Systran/faster-whisper-small`（model.bin 483,546,902 字节，可续传）到 `VN_HOME/models/fw-small`。
- `references/visual-breakdown.md`：画面拆解的分析维度、术语、提示词模板、复刻失败排查。
- `references/aesthetics-viral.md`：氛围感（美学）和爆款（传播）分析框架、平台数据收集、平台差异。
- `references/douyin-batch.md`：读取抖音「喜欢」「收藏」列表的接口、字段提取代码、三种内容类型的取素材方法、实测耗时。
- `scripts/vtool.py` 子命令：
  - `fetch URL OUT [--referer R]`：下载媒体直链（默认 referer 抖音）
  - `bili-audio BV OUTDIR`：B站完整 m4a
  - `yt-audio URL OUTDIR [--cookies F | --browser chrome]`：yt-dlp 下载音频
  - `transcribe AUDIO OUT.txt [--lang zh|en|auto] [--prompt 术语] [--words W.json]`：faster-whisper small（int8，CPU），先开静音过滤，结果为空就关掉重试（歌曲常见）；中文转简体；每行 `[mm:ss]`；`--words` 另存逐词时间和置信度；模型路径可用环境变量 `VN_MODEL` 覆盖
  - `flow VIDEO OUTDIR [--max-events 12]`：逐帧分析整条视频（不按镜头切）。每帧算缩放（推拉）、横移、升降、旋转速率（每秒）、画面变化（HSV 直方图距离，0 相同 1 全变）、清晰度（拉普拉斯方差，骤降多为运动模糊或失焦）、亮度。自动找"画面变化尖峰或持续升高、运动激增、清晰度骤降、特征点丢失"的时段，标成硬切、柔性转场、快速推进/拉远、甩镜、旋转、模糊等，并为每个事件生成一张逐帧图（`eNN_*.jpg`）。输出 `flow_timeline.png`（五条曲线的时间线，事件段标浅色底）和 `flow.json`
  - `ocr IMG [IMG ...] [--out OUT.txt]`：RapidOCR 识别图片文字，按从上到下、从左到右排序；用于图文帖和截图
  - `subcheck VIDEO W.json OUT.json [--all]`：RapidOCR 本地识别画面字幕。先在 8 帧整图里找字幕所在的横条，再只在转写可疑处截这一条识别；`--all` 按每秒 2 帧、画面有变化才识别，提取全部字幕
  - `scenes VIDEO OUTDIR [--th 0.3] [--max 24]`：按画面切换抽帧并缩到 1280 宽，不足 3 张改为固定间隔；文件名带时间（`t03m30s.jpg`）
  - `shots VIDEO OUTDIR [--th 10]`：ffmpeg scdet 切镜头；每个镜头取首/中/尾三帧拼成一张图（`s01_00m00.00s.jpg`，印时间码）；`shots.json` 记录起止、时长、平均镜头时长、每分钟刀数，以及每个镜头中间帧的亮度 luma、饱和 sat、色相 hue（0–255）和黑边裁切 crop
  - `sheet VIDEO OUT.jpg [--ss S] [--to E] [--n 24] [--cols 6] [--width 320]`：在时间段内按帧均匀取 n 帧拼图，印时间码；看转场和变装用
  - `motion VIDEO OUT.json [--shots shots.json]`：用 opencv 特征点估计每个镜头的运镜：scale<1 是后拉或拉远，dy>0 是镜头上移或上摇，dx>0 是镜头左移或左摇；speed_curve 判断缓入、缓出或匀速；profile 是每 0.1 秒的速度，可用来找变速点。无法区分"移"和"摇"、"推轨"和"变焦"，需要结合透视变化看图判断
  - `beats VIDEO OUT.json [--shots shots.json]`：只用 numpy，不需要额外安装；输出 BPM、节拍网格、重音（accents）、静音/断音段；带 `--shots` 时给出每个切点离最近节拍和重音的毫秒数，±70ms 内标「卡拍」。节拍网格可能差半拍，以重音为准

## 致谢

思路参考了两个 MIT 开源项目：[threerocks/video-subtitle-parser](https://github.com/threerocks/video-subtitle-parser)、[Panniantong/agent-reach](https://github.com/Panniantong/agent-reach)（`references/video.md`：B站用 bili-cli、YouTube 重试链）。平台规则常变，某个平台失效时可对照这两个项目的最新做法更新。
