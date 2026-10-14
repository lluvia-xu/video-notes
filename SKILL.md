---
name: video-notes
description: 把抖音、B站、YouTube 等视频链接或本地视频转成文字稿和总结（含无字幕口播、画面上的文字、歌词），也可调研某类视频。Use when the user sends a video link or says 总结这个视频, 视频转文字, 提取口播, 看看这个抖音/B站/YouTube, 调研 xx 的视频, summarize this video.
---

# 视频总结（video-notes）

把视频变成可读的素材：**口播文字稿 + 画面文字 + 总结**。原理是在本机下载音频，再用 Whisper 做本地语音识别；画面上的文字靠 ffmpeg 抽关键帧后看图读取。处理完只保留文字，音视频和截图都删掉。

## 第 0 步：确定运行环境和工具目录（每次都要做）

先判断你在哪种环境，确定 `VN_HOME`（工具目录）和 `OUT`（结果目录）：

| 环境 | 怎么判断 | VN_HOME | OUT |
|---|---|---|---|
| **本机命令行**（Claude Code、Codex、Cursor 等） | 能直接在用户电脑上执行 shell | `~/.video-notes` | 当前项目目录下的 `视频笔记/`，或用户指定的位置 |
| **Claude Cowork** | 通过 device_bash 在用户电脑的虚拟环境里执行，文件夹挂在 `$HOME/mnt/<文件夹>` | `$HOME/mnt/<连接的文件夹>/_工具` | `$HOME/mnt/<连接的文件夹>` |

Cowork 注意：没有连接文件夹就先请用户建一个（如「视频素材」），再申请访问；临时文件放 `$HOME/tmp/`（虚拟环境里，不占用户硬盘）；单次命令最多约 180 秒，长任务要拆步；虚拟环境出网可能是机房 IP（YouTube 会拦）。

**检查工具**：`PY=$VN_HOME/venv/bin/python; $PY -c "import faster_whisper,yt_dlp,bili_cli" && ls $VN_HOME/models/fw-small/model.bin`

- 不通过就运行本 skill 自带的 `scripts/setup.sh "$VN_HOME"`（先告诉用户：约 1GB、首次 3～8 分钟）。在 Cowork 里 skill 目录可能不可用：按「附录」把 setup.sh 和 vtool.py 的内容写到 `$VN_HOME` 再执行；模型下载超时就重复执行（支持续传）。
- **调用一律用 `$PY -m yt_dlp`、`$PY $VN_HOME/vtool.py ...`**，不要直接运行 `venv/bin/` 下的命令（换会话后路径可能变）。
- 需要 ffmpeg。缺失时：macOS `brew install ffmpeg`，Ubuntu `apt install ffmpeg`。

临时目录记为 `TMP`：本机用 `$(mktemp -d)`，Cowork 用 `$HOME/tmp/<任务名>`。

## 第 1 步：判断类型

用户说了类型（如"抖音、口播无字幕"）就直接用；没说就依次判断：有没有字幕 → 有没有人声 → 画面上有没有成段的字。

| 类型 | 做法 |
|---|---|
| 有字幕 | 直接取字幕 |
| 口播无字幕 | 下载音频 → 转写 |
| 画面写字（配乐、字幕卡、屏幕上的提示词/参数） | 下载视频 → 抽关键帧 → 读图 |
| 混合（常见：口播教程 + 屏幕上的提示词） | 先转写；口播提到"参考这条/看屏幕/提示词如下"等的时间点再抽帧读图 |
| 歌曲、纯音乐 | 转写得到歌词；旋律和编曲无法"听"，如实说明 |

## 第 2 步：按平台取素材

### 抖音
yt-dlp 抓抖音需要 Cookie，各类分享页解析器也常失效。按可用性选：

- **有浏览器工具时（推荐，实测可用）**：
  1. 短链转 ID：`curl -s -o /dev/null -w "%{redirect_url}" -A "Mozilla/5.0 (iPhone)" "<v.douyin.com 短链>"`，从 `/share/video/<ID>/` 取数字 ID。
  2. 浏览器打开 `https://www.douyin.com/video/<ID>`，等 3～4 秒后执行：
     ```js
     const es=performance.getEntriesByType('resource').map(e=>e.name).filter(u=>/douyinvod/.test(u));
     JSON.stringify({a:es.find(u=>u.includes('media-audio')), v:es.find(u=>u.includes('media-video')), title:document.title})
     ```
     拿不到就再等几秒或点播放后重试。`title` 就是视频文案。
  3. **立刻**下载（直链很快过期）：`$PY $VN_HOME/vtool.py fetch "<地址>" $TMP/audio.mp4`
- **本机命令行、没有浏览器工具时**：征得用户同意后读取其浏览器 Cookie：`$PY -m yt_dlp --cookies-from-browser chrome -x --audio-format m4a -o "$TMP/%(id)s.%(ext)s" "https://www.douyin.com/video/<ID>"`（要说明这会读取用户浏览器里的抖音 Cookie）。
- 都不行：在浏览器里暂停、跳到时间点截图读画面（听不到声音），或请用户把视频文件发来。

### B站
- 详情和字幕可用性：`$PY -c "import sys;from bili_cli.cli import cli;sys.argv=['bili','video','BVxxx'];cli()"`
- 下载音频：`$PY $VN_HOME/vtool.py bili-audio BVxxx $TMP`（B站经常拦截 yt-dlp，音频优先用 bili-cli）
- 需要画面：先试 `$PY -m yt_dlp -f "bv*[height<=1080]" -o $TMP/video.mp4 <链接>`，失败再用浏览器截图。

### YouTube
- **本机、家用网络**：通常直接可用：`$PY $VN_HOME/vtool.py yt-audio <链接> $TMP`；有字幕时优先 `$PY -m yt_dlp --skip-download --write-subs --write-auto-subs --sub-langs "zh-Hans,zh,en" -o "$TMP/%(id)s" <链接>`。
- **遇到"Sign in to confirm you're not a bot"**（机房 IP、Cowork 虚拟环境常见），按顺序：
  - **A（最简单）请用户复制文字记录**：视频下方「…更多」→「显示文字记录」→ 全选复制发过来。
  - **B 本机命令行**：征得同意后加 `--browser chrome`（读取浏览器 Cookie）。
  - **C Cookie 文件**（Cowork 等无法读浏览器的环境）：先看 `$VN_HOME/youtube_cookies.txt` 是否存在，存在就 `yt-audio ... --cookies $VN_HOME/youtube_cookies.txt`；不存在就把下面的步骤告诉用户：
    1. 建议用 Google **小号**、Chrome 浏览器；
    2. 安装插件「**Get cookies.txt LOCALLY**」（认准 LOCALLY，开源、本地导出）；
    3. 插件「详情」里打开「在无痕模式下启用」；
    4. 开无痕窗口，登录 youtube.com；
    5. 同一标签页打开 `https://www.youtube.com/robots.txt`；
    6. 点插件 →「Export」得到 cookies 文件；
    7. **马上关闭整个无痕窗口**（不要退出登录），Cookie 能用得更久；
    8. 文件改名 `youtube_cookies.txt` 放进 `$VN_HOME`。
    这个文件等于小号的登录凭证，不要外传、不要提交到 Git；失效了重做 4～8；仍失败就退回 A。

### 本地视频 / 其他平台
请用户把视频文件放进结果目录，直接处理；完成后询问是否删除原视频。其他 yt-dlp 支持的网站可以直接试 `$PY $VN_HOME/vtool.py yt-audio <链接> $TMP`。

## 第 3 步：转写和读画面

- **转写**：`$PY $VN_HOME/vtool.py transcribe <音频> $TMP/transcript.txt --lang zh --prompt "<标题/文案里的人名、产品名、术语>"`
  - 外语用 `--lang auto`/`en`，转完翻译成用户的语言再总结。
  - 参考速度：4 核 CPU 上 5 分半音频约 80 秒；超过 10 分钟先用 ffmpeg 切段（有时间限制的环境尤其要切）。
  - Whisper small 会有同音错字，总结时纠正，并在文末列「识别纠错」。
- **抽关键帧**：
  - 自动（按画面切换）：`$PY $VN_HOME/vtool.py scenes <视频> <截图目录> --max 20`
  - 指定时间：`ffmpeg -ss 00:03:30 -i <视频> -frames:v 1 -vf scale=1280:-2 -q:v 4 <输出>.jpg`
  - 只看需要的几张（每张约 300～500 token）。Cowork 里截图要先放在连接文件夹的 `_临时截图/` 下，才能 device_stage_files 传到云端再看。
- **读完立刻删除截图。** Cowork 删除连接文件夹里的文件需要用户授权（每个对话一次，用 device_request_delete_permission）；用户拒绝就挪进 `_待删除/` 并告知。

## 第 4 步：输出

在 `OUT` 下建 `<简短标题>/`，只放文字：

- `总结.md`：来源（平台、链接、作者、时长）和处理方式 → 一句话总结 → 核心内容（分条）→ 操作步骤/方法（教程类）→ 画面上读到的关键信息（提示词、参数、文案原文）→ 值得借鉴之处 → 识别纠错
- `口播文字稿.txt`：带时间戳的转写或字幕原文

对话里只回复要点和文件位置，不贴全文。

## 第 5 步：清理（每次必做）

删除 `$TMP`（音频、视频、wav）和截图目录；最后只留 `<标题>/` 里的文字和 `VN_HOME` 里的工具。

## 调研模式

用户说"调研/找一些 xx 视频并总结"时：每个平台挑 3～5 条代表性内容（B站：`bili search "关键词" --type video -n 5`；抖音、小红书：有浏览器工具时在用户已登录状态下搜；YouTube：网页搜索找链接），逐条走上面的流程，最后汇总 `调研_<主题>.md`：各平台主打卖点、内容形式、文案套路、互动数据、可借鉴之处，附来源链接。

## 原则

- 仅用于个人学习、研究和素材整理。提醒用户：转写稿和总结不要用于搬运、冒充原创或未经授权的商用。
- 不绕过平台的登录墙、付费墙或访问限制；工具访问不了就如实说明并给替代方案。
- 读取浏览器 Cookie 前必须征得用户同意；不建议使用主账号的 Cookie；不替用户输入密码。
- 某一步失败时，告诉用户卡在哪、为什么，再给替代方案。

## 附录：工具说明

- `scripts/setup.sh [VN_HOME]`：建 venv（`--copies`）、安装 yt-dlp / requests / opencc-python-reimplemented / faster-whisper / bilibili-cli、把 vtool.py 复制进 VN_HOME、下载 `Systran/faster-whisper-small`（model.bin 483,546,902 字节，可续传）到 `VN_HOME/models/fw-small`。
- `scripts/vtool.py` 子命令：
  - `fetch URL OUT [--referer R]`：下载媒体直链（默认 referer 抖音）
  - `bili-audio BV OUTDIR`：B站完整 m4a
  - `yt-audio URL OUTDIR [--cookies F | --browser chrome]`：yt-dlp 下载音频
  - `transcribe AUDIO OUT.txt [--lang zh|en|auto] [--prompt 术语]`：faster-whisper small（int8，CPU），先开静音过滤，结果为空就关掉重试（歌曲常见）；中文转简体；每行 `[mm:ss]`；模型路径可用环境变量 `VN_MODEL` 覆盖
  - `scenes VIDEO OUTDIR [--th 0.3] [--max 24]`：按画面切换抽帧并缩到 1280 宽，不足 3 张改为固定间隔；文件名带时间（`t03m30s.jpg`）

## 致谢

思路参考了两个 MIT 开源项目：[threerocks/video-subtitle-parser](https://github.com/threerocks/video-subtitle-parser)、[Panniantong/agent-reach](https://github.com/Panniantong/agent-reach)（`references/video.md`：B站用 bili-cli、YouTube 重试链）。平台规则常变，某个平台失效时可对照这两个项目的最新做法更新。
