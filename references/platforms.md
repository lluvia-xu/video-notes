# 各平台取素材（详细版）

SKILL.md 第 2 步的展开。抖音最常用的做法已写在 SKILL.md，这里是完整版、其他平台和排错。

## 抖音
yt-dlp 抓抖音需要 Cookie，各类分享页解析器也常失效。按可用性选：

- **有浏览器工具时（推荐，实测可用）**：
  1. 短链转 ID：`curl -s -o /dev/null -w "%{redirect_url}" -A "Mozilla/5.0 (iPhone)" "<v.douyin.com 短链>"`，从 `/share/video/<ID>/` 取数字 ID。
  2. 浏览器打开 `https://www.douyin.com/video/<ID>`，等 3～4 秒后执行：
     ```js
     const es=performance.getEntriesByType('resource').map(e=>e.name).filter(u=>/douyinvod/.test(u));
     JSON.stringify({a:es.find(u=>u.includes('media-audio')), v:es.find(u=>u.includes('media-video')), title:document.title})
     ```
     拿不到就再等几秒或点播放后重试。`title` 就是视频文案。
  3. **立刻**下载（直链很快过期）：`$PY $VN_HOME/vtool.py fetch "<地址>" $TMP/audio.mp4`；要校对字幕或拆画面时，把 `v` 也下载为 `$TMP/video.mp4`（2 分钟视频约 4MB，HEVC 编码，ffmpeg 可直接处理）。
  4. 页面已打开时，顺手用 get_page_text 看有没有抖音自带的 AI 摘要或章节要点，有就记下，可用于快速筛选（尚未逐条验证覆盖率和准确度，不能代替转写）。
  - 实测（2026-10）：取直链约 10 秒，下载音频 3～4 秒；直链在云端和本机都能下载。
- **本机命令行、没有浏览器工具时**：征得用户同意后读取其浏览器 Cookie：`$PY -m yt_dlp --cookies-from-browser chrome -x --audio-format m4a -o "$TMP/%(id)s.%(ext)s" "https://www.douyin.com/video/<ID>"`（要说明这会读取用户浏览器里的抖音 Cookie）。
- 都不行：在浏览器里暂停、跳到时间点截图读画面（听不到声音），或请用户把视频文件发来。
- **其他工具的实测对比**（2026-10，用户想图省事时可以告诉他）：
  - 豆包**手机 App** 普通对话：发抖音链接说"转文字"，几秒出结果，和真实口播基本一致。单条只要原话时最省事，但无法批量、无法被 skill 调用。
  - 豆包**网页版**普通对话：不读音频，而是用标题和链接去搜索再拼答案；逐字稿会被拒绝，"列出原话"时后半段会编造。**不能当文字稿用。**
  - 豆包网页版**工作模式**：流程和本 skill 相同（yt-dlp 被拦 → 浏览器抓直链 → 上传飞书妙记转写），转写准确，但单条约 3 分半，不比本 skill 快。

## B站
- 详情和字幕可用性：`$PY -c "import sys;from bili_cli.cli import cli;sys.argv=['bili','video','BVxxx'];cli()"`
- 下载音频：`$PY $VN_HOME/vtool.py bili-audio BVxxx $TMP`（B站经常拦截 yt-dlp，音频优先用 bili-cli）
- 需要画面：先试 `$PY -m yt_dlp -f "bv*[height<=1080]" -o $TMP/video.mp4 <链接>`，失败再用浏览器截图。

## YouTube
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

## 本地视频 / 其他平台
请用户把视频文件放进结果目录，直接处理；完成后询问是否删除原视频。其他 yt-dlp 支持的网站可以直接试 `$PY $VN_HOME/vtool.py yt-audio <链接> $TMP`。
