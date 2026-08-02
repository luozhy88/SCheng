# 抖音合集视频批量下载脚本

## 脚本列表

| 脚本 | 功能 |
|------|------|
| `download_douyin_collection.py` | 批量下载抖音合集全部视频 → `output/video/` |
| `organize_by_chapter.py` | 按章节整理视频 → `方剂合集_按章节整理/`（顺序依据 `章节顺序.txt`） |
| `merge_chapters_to_mp3.py` | 每个章节的全部视频合并成一个 MP3 → `方剂合集_按章节整理/音频汇总/` |
| `remove_lailai_from_mp3.py` | 删除每段视频开头的「来了来了」报幕并重新生成章节 MP3 |
| `verify_clean.py` | 验证章节 MP3 中是否还有「来了来了」（语音识别检查） |
| `verify_clean2.py` | 能量法验证：检查每段视频开头是否已切到静音（配合 `--cutoffs`） |
| `verify_from_log.py` | 从重处理日志提取切点 → 自动逐章调 `verify_clean2.py` 验证 |
| `scan_tail.py` | 扫描所有视频，分析 whisper 锚点与报幕真实结束位置的偏差（诊断用） |
| `章节顺序.txt` | 18 个章节 + 方剂顺序列表（可自行修改） |

## 快速使用

```bash
# 默认下载「王点点-自学中医 中医方剂歌诀」合集 → output/video/
python3 scripts/download_douyin_collection.py

# 指定合集 ID
python3 scripts/download_douyin_collection.py 7627689248653346816

# 指定合集链接 + 输出目录
python3 scripts/download_douyin_collection.py "https://www.douyin.com/collection/7627689248653346816" output/video
```

## 首次运行

脚本会自动：
1. 创建 `scripts/.venv_dl` 虚拟环境并安装 `playwright`
2. 在 `~/Library/Caches/ms-playwright/` 中查找已有的 Chromium；找不到则会提示用 playwright 自带浏览器（需手动执行一次 `playwright install chromium`）

## 特点

- **自动翻页**：页面点击「加载更多」直到全部加载完
- **智能命名**：从标题解析「第N天《方剂名》」→ 文件名为 `第NNN天_方剂名.mp4`
- **断点续传**：已存在且有效的视频自动跳过，重复运行只会下载新增/缺失的
- **并发下载**：6 线程并行，快
- **防重名**：同一天多集时自动追加视频 ID 后缀

## 整理视频到章节文件夹

```bash
python3 scripts/organize_by_chapter.py
```

读取 `scripts/章节顺序.txt`（章节+方剂顺序），把 `output/video/` 下的视频按章节复制到
`方剂合集_按章节整理/`，文件名带章节内序号和原始天数，例如 `01_麻黄汤(第001天).mp4`。

- 列表中没收录、但下载到的视频（如大青龙汤、紫雪等 20 个）放到「其他（未在列表中）」文件夹
- 列表中有、但没有对应视频的方剂会在输出中列出（如香苏散、乌梅丸等 29 个，尚未拍到）

## 按章节合并成 MP3

```bash
python3 scripts/merge_chapters_to_mp3.py
```

把每个章节文件夹里的全部 mp4（按文件名顺序）提取音频合并为一个 mp3，
输出到 `方剂合集_按章节整理/音频汇总/`（如 `一、解表剂.mp3`）。
依赖 `scripts/.venv_dl` 中的 ffmpeg（`pip install imageio-ffmpeg`）。
单个视频先转 mp3 再拼接，坏文件自动跳过并在日志提示。

## 删除「来了来了」报幕

```bash
# 重新生成去除开头「来了来了」的章节 MP3（依赖 scripts/.venv_asr 中的 faster-whisper）
python3 scripts/remove_lailai_from_mp3.py            # 全部章节
python3 scripts/remove_lailai_from_mp3.py 01_解表剂  # 指定章节

# 验证是否删干净（语音识别检查「来了」）
python3 scripts/verify_clean.py 音频汇总/01_解表剂.mp3
```

原理：每个视频开头是「来了来了（来啰来啰）+ 今天要背的是XX + 出发 + 方歌」。
用 faster-whisper 词级时间戳定位「今天」一词，再结合波形能量分析：

1. 找每段视频报幕语音结束后的静音谷（连续 ≥0.12s 低能量）
2. 取 whisper 锚点 ±0.55s 内最后一个合格静音谷（报幕尾音衰减常形成双谷，
   取最后一个才能切净；同时用「谷前连续语音 ≥0.4s」和「谷距锚点 ≤0.55s」
   排除「今天」句内的停顿谷）
3. 切点 = max(whisper锚点, 静音谷起点 + 0.08s)，把报幕连同尾音一起裁掉，
   保留「今天要背的是XX」

whisper 词级时间戳系统性偏早约 0.1~0.3s（会把「今天」标在报幕中间），
因此不能只靠 whisper，能量分析才是主力。注意「接下来」等正常内容里的
「来」字不会被误删。

## 手动环境准备（备用）

```bash
python3 -m venv scripts/.venv_dl
scripts/.venv_dl/bin/pip install playwright
scripts/.venv_dl/bin/python -m playwright install chromium
```
