#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证章节 MP3 去报幕效果: 每段视频开头处必须是低能量静音(报幕已切干净)。

偏移量用 mp4→mp3 转码后的精确时长累计(与 remove_lailai_from_mp3.py 一致)。

用法:
  python3 verify_clean2.py            # 检查全部章节
  python3 verify_clean2.py 01_解表剂  # 指定章节
"""
import argparse
import glob
import os
import re
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SRC_ROOT = os.path.join(ROOT, "output", "方剂合集_按章节整理")
AUDIO_DIR = os.path.join(SRC_ROOT, "音频汇总")
TMP_DIR = os.path.join(AUDIO_DIR, ".tmp_verify")

FFMPEG = None
for pat in [
    os.path.join(BASE, ".venv_dl", "lib", "*", "site-packages",
                 "imageio_ffmpeg", "binaries", "ffmpeg-*"),
]:
    hits = glob.glob(pat)
    if hits:
        FFMPEG = hits[0]
        break

SR = 16000
WIN = 0.02
CHECK_WIN = 0.35   # 每段开头检查 0.35s
SPEECH_HI = 0.10   # rms 高于此视为"有语音"


def get_duration(path):
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def conv_mp3(path, out):
    r = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-err_detect", "ignore_err", "-i", path,
         "-vn", "-c:a", "libmp3lame", "-q:a", "2", out],
        capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000


def rms_profile(path):
    import numpy as np
    from faster_whisper.audio import decode_audio
    audio = decode_audio(path, sampling_rate=SR)
    n = int(WIN * SR)
    rms = []
    for i in range(0, len(audio) - n, n):
        seg = audio[i:i + n]
        rms.append(float(np.sqrt(np.mean(seg ** 2))))
    return rms, len(audio) / SR


def check_chapter(ch_name, cutoffs=None):
    ch_dir = os.path.join(SRC_ROOT, ch_name)
    mp4s = sorted(glob.glob(os.path.join(ch_dir, "*.mp4")))
    mp3 = os.path.join(AUDIO_DIR, f"{ch_name}.mp3")
    if not os.path.exists(mp3):
        print(f"[缺文件] {ch_name}.mp3 不存在")
        return
    if not mp4s:
        print(f"[空章节] {ch_name}")
        return
    os.makedirs(TMP_DIR, exist_ok=True)

    # 与 remove 脚本同法: 每段 mp3 时长 (精确偏移)
    durs = []
    for i, p in enumerate(mp4s):
        tmp = os.path.join(TMP_DIR, f"{ch_name.replace('/','_')}_{i}.mp3")
        if not (os.path.exists(tmp) and os.path.getsize(tmp) > 1000):
            if not conv_mp3(p, tmp):
                print(f"  !! 转换失败 {os.path.basename(p)}")
                durs.append(None)
                continue
        durs.append(get_duration(tmp))
    total_orig = sum(d for d in durs if d)

    # 处理后偏移 = 前面各段(时长 - 切点) 之和
    if cutoffs is None:
        cutoffs = [0.0] * len(mp4s)
    offs_proc, cur = [], 0.0
    for i, d in enumerate(durs):
        if d is None:
            continue
        offs_proc.append(cur)
        co = cutoffs[i] if i < len(cutoffs) else 0.0
        cur += d - co

    rms, dur = rms_profile(mp3)
    problems = []
    for i, off in enumerate(offs_proc):
        if off >= dur - 0.05:
            continue
        i0 = int(off / WIN)
        # 打印段开头前 6 帧(0.12s)能量, 供核对
        frames = [round(v, 3) for v in rms[i0:i0 + 6]]
        # 干净判定: 前 2 帧(0.04s)均 < 0.06 => 段开头是静音
        first2 = rms[i0:i0 + 2]
        ok_start = len(first2) == 2 and max(first2) < 0.06
        if not ok_start:
            problems.append((os.path.basename(mp4s[i]), frames, round(max(first2), 3) if first2 else 0.0))

    if problems:
        print(f"[有疑点] {ch_name}.mp3 (原总长 {total_orig:.1f}s, 现长 {dur:.1f}s)")
        for name, frames, mx in problems:
            print(f"    {name}: 段开头0.12s能量={frames} (首帧{len(frames) and frames[0]})")
    else:
        print(f"[干净] {ch_name}.mp3 (原总长 {total_orig:.1f}s, 现长 {dur:.1f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chapters", nargs="*",
                    help="章节名, 默认全部")
    ap.add_argument("--cutoffs", default=None,
                    help="每段切点(秒, 逗号分隔), 与章节一一对应; 未传则用 0")
    args = ap.parse_args()
    cutoffs = [float(x) for x in args.cutoffs.split(",")] if args.cutoffs else None
    targets = args.chapters or sorted(
        d for d in os.listdir(SRC_ROOT)
        if os.path.isdir(os.path.join(SRC_ROOT, d)) and d != "音频汇总")
    for ch in targets:
        check_chapter(ch, cutoffs)


if __name__ == "__main__":
    main()
