---
name: video-notes
description: 把抖音、B站、YouTube 等视频链接或本地视频转成文字稿和总结（含无字幕口播、画面上的文字、歌词）；也能拆解纯画面视频的分镜、构图、运镜、穿搭、卡点和氛围感，分析爆款为什么火，并写出复刻用的 AI 生成视频提示词；还可调研某类视频，或批量读取用户自己抖音账号里「喜欢」「收藏」的视频做速览、转写和总结。Use when the user sends a video link or says 出收藏日报, 整理我最近的收藏, 读我喜欢/收藏的前 N 条, 读我 xx 收藏夹, 批量转我的收藏, 总结这个视频, 视频转文字, 提取口播, 看看这个抖音/B站/YouTube, 拆解画面, 分析分镜/运镜/构图, 这个视频怎么拍的, 卡点, 复刻这个视频, 生成视频提示词, 调研 xx 的视频, summarize this video.
---

# 视频总结（video-notes）

把视频变成可读的素材：口播文字稿、画面文字、总结。本机下载音频，用 Whisper 本地识别；画面上的字靠截图 OCR 或看图。处理完只留文字。

## 先选模式：只读用得到的文件

本文件是所有模式共用的基础流程（环境 → 取素材 → 转写 → 输出）。其他模式的说明放在 `references/` 里，**判断出模式后再读对应文件，用不到的不要读**。

| 用户想要 | 模式 | 开始前读 |
|---|---|---|
| 一条或几条视频的文字稿、总结（口播、教程、讲解） | 基础流程 | 只用本文件 |
| 学"这个视频怎么拍、怎么剪、为什么火"，分析转场和运镜，或想复刻、要生成视频提示词 | 画面拆解 | `references/mode-visual.md` |
| 找某类视频、调研题材或爆款规律、竞品账号 | 调研 | `references/mode-research.md` |
| 读自己抖音「喜欢」「收藏」或某个收藏夹的前 N 条 | 批量 | `references/mode-batch.md` |
| 出收藏日报、把最近的新收藏整理进知识库（日报 + 知识卡片） | 收藏日报 | `references/mode-digest.md`（取素材部分再读 `douyin-batch.md`） |

按需再读的参考文件：

- `references/creator-research.md`：自媒体起号的用户匹配、对标、证据与 30 天实验，适用于任意领域。
- `references/platforms.md`：各平台取素材的完整做法、YouTube 被拦、豆包等工具的实测对比
- `references/transcription.md`：转写参数和速度、字幕校对规则、抽关键帧
- `references/tools.md`：setup.sh 和 vtool.py 全部子命令说明

## yt-dlp 轻量采集与证据索引

按需使用 `scripts/collect.py`，不必先下载 Whisper 模型：`python scripts/collect.py URL --out 结果目录 --subtitles --limit 1`。需要已安装 `yt-dlp` 的 Python；缺失时先安装该依赖。`--limit` 为每个输入的上限（1–100），单视频默认不展开播放列表；支持多个 URL 和 `ytsearchN:关键词`。`--languages zh.*,en.*` 控制字幕语言；`--audio --format bestaudio/best` 可另存音频，下载支持当前运行内的续传与跨运行下载归档；因每次使用独立目录，不支持跨运行续传未完成的分片；只读字幕时不会建立音频下载归档。manifest 标注元数据、章节、字幕与音频分别的状态和文件；每次运行目录隔离旧文件，重复的提取器和视频 ID 会去重；失败时检查 manifest 的 error，不能把无字幕的成功退出视为转写成功。搜索结果或 metadata 只能证明公开页面信息，不代表看过视频；总结应基于实际字幕、转写或画面并标时间。自动字幕注明机器生成及错误风险。适配随平台变化，无法保证所有站点或登录资源可用。此脚本忽略 yt-dlp 配置，不读取 Cookie；原有授权访问流程另见相应参考。

在 ChatGPT、Codex 或其他环境中，先确认可访问技能文件、Python 和网络；无法执行 shell 或访问外网时如实说明，不声称安装成功。研究起号时区分讲师主张与证据，记录来源链接、时间点、样本范围、失败和未覆盖内容，收益或平台规则须独立核验。

## 第 0 步：环境（按需检查）

| 环境 | 怎么判断 | VN_HOME（工具目录） | OUT（结果目录） |
|---|---|---|---|
| 本机命令行（Claude Code、Codex、Cursor 等） | 能直接在用户电脑执行 shell | `~/.video-notes` | 当前项目下的 `视频笔记/`，或用户指定的位置 |
| Claude Cowork | 用 device_bash，文件夹挂在 `$HOME/mnt/<文件夹>` | `$HOME/mnt/<连接的文件夹>/_工具` | `$HOME/mnt/<连接的文件夹>` |

- Cowork：没连接文件夹就请用户建一个（如「视频素材」）再申请访问；临时文件放 `$HOME/tmp/`（不占用户硬盘）；单次命令最多约 180 秒，长任务拆步；出网可能是机房 IP（YouTube 会拦）。
- **本地转写和画面分析检查工具**：`PY=$VN_HOME/venv/bin/python; $PY -c "import faster_whisper,yt_dlp,bili_cli,cv2,rapidocr_onnxruntime" && ls $VN_HOME/models/fw-small/model.bin`。需要本地转写或画面工具且检查不通过时，再运行 `scripts/setup.sh "$VN_HOME"`（先告诉用户：约 1GB，首次 3～8 分钟；旧版缺依赖时重跑即可补装）。Cowork 里 skill 目录可能读不到：把 `scripts/setup.sh` 和 `scripts/vtool.py` 的内容写到 `$VN_HOME` 再执行；模型下载超时就重复执行（支持续传）。
- 调用一律用 `$PY -m yt_dlp`、`$PY $VN_HOME/vtool.py ...`，不要直接运行 `venv/bin/` 下的命令（换会话后路径可能变）。需要 ffmpeg（macOS `brew install ffmpeg`，Ubuntu `apt install ffmpeg`）。
- 若 ffmpeg 安装在 `$VN_HOME/bin`，先执行 `export PATH="$VN_HOME/bin:$PATH"`，否则使用系统 ffmpeg。
- 临时目录 `TMP`：本机 `$(mktemp -d)`，Cowork `$HOME/tmp/<任务名>`。

## 第 1 步：判断类型

用户说了就直接用；没说就依次判断：有没有平台字幕文件 → 有没有人声 → 画面里有没有字。

"字幕"分两种：**平台字幕文件**（B站、YouTube 可单独开关的 CC 字幕）可以直接下载；**烧录字幕**（压进画面的字，抖音、小红书最常见）只能截图 OCR。

| 类型 | 做法 |
|---|---|
| 有平台字幕文件（B站、YouTube 的 CC 字幕） | 直接取字幕 |
| 口播，画面无字幕 | 下载音频 → 转写 |
| 口播，画面有烧录字幕（抖音口播最常见） | 下载音频和视频 → 转写（带 `--words`）→ 字幕校对 |
| 画面写字（字幕卡、屏幕上的提示词、参数） | 下载视频 → 抽关键帧 → 读图 |
| 混合（口播教程 + 屏幕上的提示词） | 先转写；口播提到"看屏幕/提示词如下"的时间点再抽帧读图 |
| 歌曲、纯音乐 | 转写得到歌词；旋律和编曲听不了，如实说明 |
| 纯画面（变装、卡点、氛围、MV） | 转画面拆解模式 |

## 第 2 步：取素材

**抖音（有浏览器工具时，实测可用）**：

1. 短链转 ID：`curl -s -o /dev/null -w "%{redirect_url}" -A "Mozilla/5.0 (iPhone)" "<短链>"`，从 `/share/video/<ID>/` 取数字。
2. 浏览器打开 `https://www.douyin.com/video/<ID>`，等 4～5 秒后执行：
   ```js
   const es=performance.getEntriesByType('resource').map(e=>e.name).filter(u=>/douyinvod/.test(u));
   JSON.stringify({a:es.find(u=>u.includes('media-audio')), v:es.find(u=>u.includes('media-video')), m:document.querySelector('video')?.currentSrc, title:document.title, path:location.pathname})
   ```
   - 有 `a`：音频单独存放，下载它。没有 `a`：用 `m`（单个 mp4，含音轨）。
   - 地址跳成 `/article/`：是文章，用 get_page_text 读正文。
3. **立刻下载**（直链很快过期）：`$PY $VN_HOME/vtool.py fetch "<地址>" $TMP/audio.mp4`；要校对字幕或拆画面时，把视频也下载下来。

**B站**：`$PY $VN_HOME/vtool.py bili-audio BVxxx $TMP`。**YouTube**：`$PY $VN_HOME/vtool.py yt-audio <链接> $TMP`。**本地视频**：请用户放进结果目录。

以上走不通，或遇到没有浏览器、YouTube 要求验证、其他平台时，读 `references/platforms.md`。

## 第 3 步：转写

`$PY $VN_HOME/vtool.py transcribe <音频> $TMP/transcript.txt --lang zh --prompt "<标题里的人名、产品名、术语>"`

- 外语用 `--lang auto` 或 `en`，转完再翻译总结。用时约等于音频时长（2 核机器）；超过 10 分钟先切段。
- 同音错字在总结里纠正，文末列「识别纠错」。
- 画面有烧录字幕、且用户要引用原话时，加 `--words $TMP/words.json`，再做字幕校对：`$PY $VN_HOME/vtool.py subcheck $TMP/video.mp4 $TMP/words.json $TMP/subcheck.json`。校对规则和抽关键帧见 `references/transcription.md`。

## 第 4 步：输出和清理

在 `OUT/<简短标题>/` 下只放文字：

- `总结.md`：来源（平台、链接、作者、时长）和处理方式 → 一句话总结 → 核心内容 → 操作步骤（教程类）→ 画面上读到的关键信息 → 值得借鉴 → 识别纠错（标时间点方便回听）
- `口播文字稿.txt`：带时间戳的原文

对话里只回复要点和文件位置，不贴全文。**最后删除 `$TMP`（音视频、wav）和截图**，只留文字和 `VN_HOME` 里的工具。Cowork 删除连接文件夹里的文件要先用 device_request_delete_permission 申请；用户拒绝就挪进 `_待删除/` 并告知。

## 原则

- 仅用于个人学习、研究和素材整理。转写稿和总结不要用于搬运、冒充原创或未经授权的商用；复刻时换成用户自己的人物和场景。
- 不绕过平台的登录墙、付费墙或访问限制；访问不了就如实说明并给替代方案。
- 读取浏览器 Cookie 前必须征得同意；不建议用主账号的 Cookie；不替用户输入密码。读用户账号数据时只读，不点赞、不改收藏。
- 对内容里的说法保持判断：数字没有出处、标题和内容不符、夸大收益的，写进"存疑"。
- 某一步失败时，告诉用户卡在哪、为什么，再给替代方案。
