# 抖音「喜欢 / 收藏」批量读取：实现细节

2026-10 实测可用（「喜欢」20 条全流程跑通）。抖音改版后接口或字段可能变化，失效时按"兜底"做，并更新本文件。

## 1. 打开列表页

| 列表 | 页面 |
|---|---|
| 喜欢 | `https://www.douyin.com/user/self?showTab=like` |
| 收藏 | `https://www.douyin.com/user/self?showTab=favorite_collection` |

打开后等 3～5 秒。页面上能看到"喜欢 🔒""收藏 🔒"标签和视频封面，就说明已登录。

## 2. 在页面里直接请求列表接口（推荐）

在页面里用 XHR 请求同源接口，抖音页面自带的安全 SDK 会自动给请求签名，不需要自己处理 a_bogus 等参数。从外部用 curl 请求不行。

**喜欢列表**（实测可用，单次最多约 20 条，`has_more` 为 1 时用返回的 `max_cursor` 翻页）：

```js
const html = document.documentElement.innerHTML;
const cands = [...new Set(html.match(/MS4wLjABAAAA[\w-]{20,}/g) || [])];   // 页面里出现的 sec_uid，第一个通常是自己
const domIds = [...new Set([...document.querySelectorAll('a[href*="/video/"]')].map(a => a.href.match(/video\/(\d+)/)?.[1]).filter(Boolean))];
async function fav(sec, cursor = 0, count = 20) {
  return new Promise(res => { const x = new XMLHttpRequest();
    x.open('GET', '/aweme/v1/web/aweme/favorite/?device_platform=webapp&aid=6383&channel=channel_pc_web&sec_user_id=' + encodeURIComponent(sec) +
      '&max_cursor=' + cursor + '&min_cursor=0&count=' + count + '&publish_video_strategy_type=2&pc_client_type=1&version_code=170400&version_name=17.4.0&cookie_enabled=true&platform=PC');
    x.onload = () => res(JSON.parse(x.responseText)); x.send(); });
}
let j, sec;
for (sec of cands) { j = await fav(sec); if ((j.aweme_list || []).some(a => domIds.includes(a.aweme_id))) break; }  // 用页面上已显示的视频 ID 校验是不是自己的列表
```

**校验很重要**：页面里可能出现别人的 sec_uid。返回的 `aweme_id` 必须和页面上已显示的视频 ID 对得上，才说明读的是用户自己的列表。

**指定收藏夹**（2026-10 实测可用，用户常说"我的『学习』收藏夹"）：两个 GET 接口，同样在页面里用 XHR 请求。

```js
const get = u => new Promise(res => { const x = new XMLHttpRequest(); x.open('GET', u); x.onload = () => res(JSON.parse(x.responseText)); x.send(); });
const base = 'device_platform=webapp&aid=6383&channel=channel_pc_web&pc_client_type=1&version_code=170400&version_name=17.4.0&cookie_enabled=true&platform=PC';
const L = await get('/aweme/v1/web/collects/list/?' + base + '&cursor=0&count=30');          // 所有收藏夹
const folders = (L.collects_list || []).map(c => ({ id: c.collects_id_str || String(c.collects_id), name: c.collects_name, n: c.total_number }));
const f = folders.find(c => c.name === '学习');                                               // 按用户说的名字找；找不到就把 folders 列给用户选
const V = await get('/aweme/v1/web/collects/video/list/?' + base + '&collects_id=' + f.id + '&cursor=0&count=' + N);  // 每页最多约 10～20 条，翻页用返回的 cursor
// V.aweme_list 的结构和喜欢列表相同，按第 3 节提取字段
```

收藏夹本身就是用户自己的，不需要 sec_uid 校验。

**收藏列表（全部收藏，不分收藏夹）**（2026-10 实测可用）：`POST /aweme/v1/web/aweme/listcollection/`，在页面里用 XHR 发，表单体 `count=10&cursor=0`，按收藏时间倒序返回；翻页用返回的 `cursor`（是微秒时间戳，约等于本页最后一条的收藏时间）。单条视频没有单独的收藏时间字段，要"接着上次读"就用已处理 ID 判断。

```js
const base = 'device_platform=webapp&aid=6383&channel=channel_pc_web&pc_client_type=1&version_code=170400&version_name=17.4.0&cookie_enabled=true&platform=PC&publish_video_strategy_type=2';
const post = (u, body) => new Promise(res => { const x = new XMLHttpRequest(); x.open('POST', u);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded'); x.onload = () => res(JSON.parse(x.responseText)); x.send(body); });
const j = await post('/aweme/v1/web/aweme/listcollection/?' + base, 'count=10&cursor=0');   // 下一页：cursor=<j.cursor>
```

## 3. 提取字段（在页面里做，只返回精简结果，别把整个响应读进对话）

整个响应有 1MB 以上，必须在页面里提取：

```js
const rows = (j.aweme_list || []).slice(0, N).map(a => ({
  id: a.aweme_id,
  title: (a.item_title || a.preview_title || a.desc || '').slice(0, 60),
  desc: (a.desc || '').slice(0, 300),
  author: a.author?.nickname,
  dur: Math.round((a.video?.duration || 0) / 1000),          // 秒；图文、文章为 0
  isImages: !!(a.images && a.images.length),                  // 图文帖
  created: a.create_time,
  like: a.statistics?.digg_count, collect: a.statistics?.collect_count,
  comment: a.statistics?.comment_count, share: a.statistics?.share_count,
  tags: (a.video_tag || []).map(v => v.tag_name).filter(Boolean).join('/'),   // 平台分类，如"个人管理/职场技能/办公效率"
  music: a.music?.title,                                      // "@xx创作的原声" 说明是作者自己的声音
}));
JSON.stringify(rows)
```

接口里没有作者粉丝数（`follower_count` 为空），需要时到作者主页看。

## 4. 兜底：从页面 DOM 取视频 ID

接口不行时：在列表页滚动几次，让更多封面加载出来，再取所有 `a[href*="/video/"]` 里的 ID，按页面顺序取前 N 个。再逐个打开 `https://www.douyin.com/video/<ID>`，从 `document.title` 读标题。这样拿不到互动数据。

## 5. 三种内容类型，取素材的方法不同

| 类型 | 怎么识别 | 怎么取内容 |
|---|---|---|
| 普通视频 | `dur > 0` 且不是图文 | 打开 `/video/<ID>`，等 5 秒，在 performance 资源列表里找 `douyinvod` 地址：**有 `media-audio` 的取它**（音视频分开存放）；**没有的，取 `<video>` 的 `currentSrc`**（单个 mp4，含音轨），然后下载、转写 |
| 文章 | 打开 `/video/<ID>` 后地址跳成 `/article/<ID>` | `get_page_text` 读正文，不用转写。文章可能带朗读音频，内容和正文一致 |
| 图文帖 | `isImages` 为真 | 文案在 `desc` 里，通常很完整；图片地址在 `a.images[].url_list`（取最后一个），下载后用 `vtool.py ocr` 识别图中文字 |

直链很快过期，取到就立刻下载。逐条打开页面时，每条之间间隔几秒，不要并发。

## 6. 实测耗时（2 核云端，2026-10）

| 环节 | 用时 |
|---|---|
| 读 20 条列表 | 一次请求，几秒 |
| 逐条打开页面、抓地址并下载 | 每条约 15～20 秒 |
| 转写 | 约等于视频时长（10 分钟视频约 9.5 分钟；5 条共 23 分钟音频用了 22 分钟） |
| 图片 OCR | 每张约 1～2 秒 |

用户本机通常更快（未实测）。转写前先报预计用时。
