#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从章节 MP3 中删除每段视频开头的「来了来了」
===========================================
步骤:
  1. 把章节内每个 mp4 转成临时 mp3（顺便得到每段精确音频时长）
  2. 拼接成章节原始 mp3
  3. 用 whisper 词级时间戳定位「今天」锚点 + 波形能量分析找报幕语音后的静音谷
  4. 每段切点 = max(whisper锚点, 静音谷起点+0.08s)，保证报幕尾音也被切干净
  5. 用 ffmpeg aselect 过滤器把各段开头的报幕静音删除，重新编码输出

用法:
  python3 remove_lailai_from_mp3.py [章节名...]   # 不传参数则处理全部章节
"""
import glob
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SRC_ROOT = os.path.join(ROOT, "output", "方剂合集_按章节整理")
AUDIO_DIR = os.path.join(SRC_ROOT, "音频汇总")
TMP_DIR = os.path.join(AUDIO_DIR, ".tmp_work")

# 定位 ffmpeg（在 .venv_dl 的 imageio-ffmpeg 里）
FFMPEG = None
for pat in [
    os.path.join(BASE, ".venv_dl", "lib", "*", "site-packages",
                 "imageio_ffmpeg", "binaries", "ffmpeg-*"),
]:
    hits = glob.glob(pat)
    if hits:
        FFMPEG = hits[0]
        break
if not FFMPEG:
    print("!! 找不到 ffmpeg")
    sys.exit(1)

FALLBACK_CUTOFF = 1.3   # 未识别到报幕边界时, 默认删除开头 1.3 秒

# 报幕锚点: 「今天要背的是」中的字
ANCHOR = set("今經经金京要背備")

# ---- 波形能量分析参数 ----
SR = 16000
WIN = 0.02          # 能量帧长 20ms
SPEECH = 0.06       # rms 高于此视为语音
LOW = 0.05          # rms 低于此视为静音
DIP_MIN_FRAMES = 6  # 静音谷最短 6 帧 = 0.12s
DIP_MARGIN = 0.08   # 静音谷起点后多切 0.08s，吃掉报幕尾音
GUARD = 0.55        # 谷起点距 whisper 锚点最大偏差
RUN_MIN = 0.4       # 谷前连续语音最短时长(容忍≤6帧短间断, 排除「今天」句内停顿谷)


def get_duration(path):
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def run_ff(args):
    return subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, text=True)


def transcribe(path):
    """返回 [(start, end, word), ...]"""
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(path, language="zh", word_timestamps=True,
                                   vad_filter=False, beam_size=1)
    words = []
    for seg in segments:
        for w in seg.words:
            words.append((w.start, w.end, w.word))
    return words


def energy_rms(path):
    """解码整个音频 → 每 20ms 一帧的 rms 能量数组。"""
    import numpy as np
    from faster_whisper.audio import decode_audio
    audio = decode_audio(path, sampling_rate=SR)
    n = int(WIN * SR)
    rms = []
    for i in range(0, len(audio) - n, n):
        seg = audio[i:i + n]
        rms.append(float(np.sqrt(np.mean(seg ** 2))))
    return rms


def find_dips(rms):
    """连续 rms < LOW 且长度 >= DIP_MIN_FRAMES 的静音谷: [(start_s, end_s), ...]"""
    dips = []
    n = len(rms)
    i = 0
    while i < n:
        if rms[i] < LOW:
            j = i
            while j < n and rms[j] < LOW:
                j += 1
            if j - i >= DIP_MIN_FRAMES:
                dips.append((i * WIN, (j - 1) * WIN))
            i = j
        else:
            i += 1
    return dips


def speech_run_before(rms, idx_end):
    """谷前连续语音跨度(秒): 从 idx_end 往回数, 容忍 <= 6 帧(0.12s)短暂低能量间断。
    这样报幕尾音衰减形成的"双谷"不会打断连续语音统计。"""
    n = 0
    gap = 0
    i = idx_end - 1
    while i >= 0:
        if rms[i] >= LOW:
            n += gap + 1
            gap = 0
        else:
            gap += 1
            if gap > 6:
                break
        i -= 1
    return n * WIN


def find_cutoffs(words, offsets, rms):
    """每段视频的报幕结束偏移。

    核心: 取「最后一个合格静音谷」作为报幕语音真正结束处:
      - 谷起点在段内窗口 [0.3, 2.5]s
      - 谷前 0.4s 内有语音 (rms>=0.07)
      - 谷前连续语音跨度 >= RUN_MIN (排除「今天」句内停顿谷)
      - 谷起点距 whisper 锚点 <= GUARD (排除开场后段的长停顿谷)
      - 必须有 whisper 锚点 (无锚点时不使用谷, 保持 FALLBACK)
    切点 = max(whisper锚点, 谷起点 + DIP_MARGIN)

    无合格谷(极少数)时直接用 whisper 锚点; 无锚点时用 FALLBACK_CUTOFF。
    """
    dips = find_dips(rms)
    cutoffs = []
    for off in offsets:
        cutoff = FALLBACK_CUTOFF
        t_abs = None
        for ws, we, ww in words:
            if off + 0.3 <= ws <= off + 6.0 and any(c in ww for c in ANCHOR):
                t_abs = ws
                break
        t_rel = (t_abs - off) if t_abs is not None else None

        if t_rel is not None and t_rel < 0.4:
            # 没有报幕、直接从「今天」开始
            cutoff = 0.0
        elif t_abs is not None:
            cands = []
            for ds, de in dips:
                if not (off + 0.3 <= ds <= off + 2.5):
                    continue
                i_ds = int(ds / WIN)
                if i_ds <= 0:
                    continue
                if max(rms[max(0, i_ds - 20):i_ds]) < 0.07:  # 谷前有语音
                    continue
                if speech_run_before(rms, i_ds) < RUN_MIN:    # 谷前连续语音够长
                    continue
                if abs(ds - t_abs) > GUARD:
                    continue
                cands.append(ds)
            if cands:
                d = max(cands)   # 取最后一个谷 (覆盖尾音衰减形成的双谷)
                cutoff = max(t_rel, (d - off) + DIP_MARGIN)
            else:
                # 无合格谷(极少数): 锚点后若存在「衰减→静音」过渡, 可多切吃掉报幕尾音
                cutoff = t_rel
                t_idx = int(t_abs / WIN)
                for i in range(t_idx, min(len(rms) - 5, t_idx + int(0.45 / WIN))):
                    if all(rms[i + k] < LOW for k in range(5)):  # >=5帧静音
                        pre = rms[max(0, i - 3):i]
                        if pre and max(pre) < 0.2:               # 过渡前是衰减弱音而非响亮语音
                            cutoff = max(cutoff, (i * WIN) + 0.06 - off)
                            break
        cutoffs.append(cutoff)
    return cutoffs


def process_chapter(ch_name):
    ch_dir = os.path.join(SRC_ROOT, ch_name)
    mp4s = sorted(glob.glob(os.path.join(ch_dir, "*.mp4")))
    out_mp3 = os.path.join(AUDIO_DIR, f"{ch_name}.mp3")
    if not mp4s:
        print(f"  (跳过, 无视频) {ch_name}")
        return
    os.makedirs(TMP_DIR, exist_ok=True)

    # 1. 每段视频 → 临时 mp3
    tmp_mp3s, offsets, skipped = [], [], []
    cur = 0.0
    for i, p in enumerate(mp4s):
        tmp = os.path.join(TMP_DIR, f"{ch_name.replace('/','_')}_{i}.mp3")
        r = run_ff(["-err_detect", "ignore_err", "-i", p,
                    "-vn", "-c:a", "libmp3lame", "-q:a", "2", tmp])
        if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 1000:
            print(f"  !! 跳过坏文件 {os.path.basename(p)}")
            if os.path.exists(tmp):
                os.remove(tmp)
            skipped.append((i, os.path.basename(p)))
            continue
        offsets.append(cur)
        cur += get_duration(tmp)
        tmp_mp3s.append(tmp)
    if not tmp_mp3s:
        print(f"  !! 无可用音频 {ch_name}")
        return

    # 2. 拼接 → 原始章节 mp3
    raw = os.path.join(TMP_DIR, f"raw_{ch_name.replace('/','_')}.mp3")
    list_file = raw + ".list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for t in tmp_mp3s:
            f.write(f"file '{t.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    r = run_ff(["-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", raw])
    if r.returncode != 0:
        print(f"  !! 拼接失败 {ch_name}: {r.stderr[-200:]}")
        return

    # 3. 识别每段「来了来了」: whisper 锚点 + 能量静音谷
    print(f"  [识别] {ch_name} ...", flush=True)
    words = transcribe(raw)
    rms = energy_rms(raw)
    cutoffs = find_cutoffs(words, offsets, rms)
    ok = sum(1 for c in cutoffs if c != FALLBACK_CUTOFF)
    print(f"    视频 {len(mp4s)} 段, 定位到报幕 {ok} 段, 默认裁剪 {len(cutoffs)-ok} 段")
    print(f"    切点: {[round(c,2) for c in cutoffs]}")

    # 4. 裁掉每段开头的「来了来了」
    ranges = [(offsets[i], offsets[i] + cutoffs[i]) for i in range(len(tmp_mp3s))]
    expr = "not(" + "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in ranges) + ")"
    final = out_mp3 + ".new.mp3"
    r = run_ff(["-i", raw, "-af",
                f"aselect='{expr}',asetpts=N/SR/TB",
                "-c:a", "libmp3lame", "-q:a", "2",
                "-metadata", f"title={ch_name}",
                final])
    if r.returncode != 0:
        print(f"  !! 过滤失败 {ch_name}: {r.stderr[-300:]}")
        return

    # 清理临时文件，替换正式文件
    for t in tmp_mp3s:
        os.remove(t)
    for extra in (raw, list_file):
        if os.path.exists(extra):
            os.remove(extra)
    os.replace(final, out_mp3)
    print(f"  [ok] {ch_name}.mp3  处理完成")


def main():
    targets = sys.argv[1:] or sorted(
        d for d in os.listdir(SRC_ROOT)
        if os.path.isdir(os.path.join(SRC_ROOT, d)) and d != "音频汇总")
    for ch in targets:
        process_chapter(ch)
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
