# video-notes · 视频转文字 & 总结 skill

把**抖音、B站、YouTube** 的视频链接（或本地视频）变成：

- 📝 **口播文字稿**：没有字幕的口播也能转，本地语音识别，免费、音频不上传
- 🖼️ **画面文字**：自动抽关键帧，读出屏幕上的提示词、参数、字幕卡
- 📥 **批量读我的喜欢 / 收藏**（新）：读取你抖音账号里「喜欢」或「收藏」的前 N 条，先出速览表，你挑出想看的再逐条转写、总结
- 🗂️ **收藏日报**（新）：说一句「出收藏日报」，自动接着上次读新收藏，每条写「讲什么 / 钩子 / 值不值」，有方法的视频再写四格知识卡片（讲了什么 / 钩子在第几秒 / 能抄什么 / 要不要跟进），存进 `抖音知识库/`（Obsidian 可直接打开）。只在你开口时运行，不定时
- ✅ **字幕校对**（新）：抖音等视频画面里有字幕时，只在语音识别没把握的地方截字幕做 OCR，纠正数字和同音字
- 📌 **总结**：要点、操作步骤、可借鉴之处

- 🎬 **画面拆解**（新）：纯画面视频（变装、卡点、氛围片、MV）自动切镜头、测运镜和节拍，逐镜头分析景别、运镜、构图、穿搭、光色、转场和卡点；分析氛围感从哪来、为什么能火；并写出复刻用的 AI 生成视频提示词

处理完自动删除下载的音视频和截图，只留文字（画面拆解会保留几张镜头缩略图）。也支持"调研某类视频"：先确认是找教程、研究爆款还是竞品调研，按对应标准选样（爆款研究会加普通视频做对照），汇总成带选样说明的调研报告。

## 适用的 AI 工具

需要能**在你电脑上执行命令**的 AI：

| 工具 | 是否可用 |
|---|---|
| Claude Code、Codex、Cursor、Windsurf 等 | ✅ |
| Claude 桌面版 Cowork（连接一个本地文件夹） | ✅ |
| ChatGPT / Grok / Claude 网页聊天 | ❌ 不能运行本地程序 |

## 安装

**方法一：让 AI 帮你装**（Claude Code / Codex 等）

```
帮我安装这个 skill：https://github.com/lluvia-xu/video-notes
```

或：`npx skills add lluvia-xu/video-notes`

**方法二：Claude 桌面版 / Cowork**

1. 下载本仓库的 zip，在 Claude「设置 → Skills」里上传（或把 `SKILL.md` 内容新建为 skill）。
2. 在电脑上新建一个文件夹（例如「视频素材」），在 Cowork 里连接它。
3. 第一次用时 AI 会自动把工具装进 `视频素材/_工具/`（约 1GB，3～8 分钟），以后打开即用。

**手动安装工具**（可选）

```bash
bash scripts/setup.sh            # 默认装到 ~/.video-notes
```

需要 Python 3.9+ 和 ffmpeg（macOS：`brew install ffmpeg`）。

## 使用

直接对 AI 说：

```
总结这个视频 https://v.douyin.com/xxxx/
这个 B 站视频讲了什么 BV1xxxx（口播无字幕）
调研一下 XX 在抖音和 B 站上的宣传视频
拆解一下这个视频的分镜和卡点，我想复刻（附视频文件或链接）
读我抖音收藏的前 30 条，出个速览表
```

说明平台和类型（口播 / 画面文字 / 有字幕）能更快，不说也会自动判断。

## 各平台情况（2026-10 实测）

| 平台 | 方法 | 备注 |
|---|---|---|
| 抖音 | 浏览器拿到音频直链 → 本地转写；或 yt-dlp 读取浏览器 Cookie | 分享页解析器已普遍失效 |
| B站 | bili-cli 下载音频 → 本地转写 | yt-dlp 常被 B 站拦截 |
| YouTube | 家用网络下 yt-dlp 直接可用 | 机房 IP 会被要求验证：可手动复制「文字记录」，或用小号 Cookie（步骤见 SKILL.md） |

## 隐私与版权

- 语音识别在本地完成，音视频不会上传到第三方。
- 读取浏览器 Cookie 前 AI 会先征得你的同意；Cookie 文件（如 `youtube_cookies.txt`）请勿提交到 Git、勿分享，建议用小号。
- **仅供个人学习、研究和素材整理。** 请尊重原作者，不要把转写稿、总结用于搬运、冒充原创或未经授权的商用。

## 文件结构

```
video-notes/
├── SKILL.md          # 基础流程 + 模式目录（每次都读，约 90 行）
├── scripts/
│   ├── setup.sh      # 一次性安装（venv + 依赖 + Whisper small 模型）
│   └── vtool.py      # 下载 / 转写 / 抽关键帧 / 切镜头 / 运镜 / 节拍卡点
├── references/
│   ├── mode-*.md            # 画面拆解 / 调研 / 批量 / 收藏日报四个模式的步骤（按需读取）
│   ├── platforms.md、transcription.md、tools.md  # 取素材、转写、工具的详细说明
│   ├── visual-breakdown.md  # 画面拆解框架和提示词模板
│   ├── aesthetics-viral.md  # 氛围感与爆款分析框架
│   └── douyin-batch.md      # 抖音喜欢/收藏批量读取的实现细节
├── README.md
└── LICENSE
```

## 致谢

画面拆解框架参考了 [0xsline/openchatcut](https://github.com/0xsline/openchatcut) 的 storyboard-shot-breakdown、machina-exm/film-studio-skills 的 film-breakdown、hexiaochun/seedance2-api 的分镜提示词公式。参考了 [threerocks/video-subtitle-parser](https://github.com/threerocks/video-subtitle-parser) 和 [Panniantong/agent-reach](https://github.com/Panniantong/agent-reach)（均为 MIT 协议）。使用了 [yt-dlp](https://github.com/yt-dlp/yt-dlp)、[bilibili-cli](https://pypi.org/project/bilibili-cli/)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[FFmpeg](https://ffmpeg.org/)。
