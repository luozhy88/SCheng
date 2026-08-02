#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按章节把视频合并成单个 MP3
==========================
读取「方剂合集_按章节整理/」下每个章节文件夹，将其中所有 mp4 按文件名顺序
提取音频并合并为一个 mp3，输出到「方剂合集_按章节整理/音频汇总/」。

用法：
  python3 merge_chapters_to_mp3.py
"""
import glob
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SRC_ROOT = os.path.join(ROOT, "output", "方剂合集_按章节整理")
OUT_DIR = os.path.join(SRC_ROOT, "音频汇总")

VENV_PY = os.path.join(BASE, ".venv_dl", "bin", "python")
if not os.path.exists(VENV_PY):
    print("!! 缺少虚拟环境 scripts/.venv_dl，请先运行 download_douyin_collection.py 初始化")
    sys.exit(1)

FFMPEG = subprocess.run(
    [VENV_PY, "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
    capture_output=True, text=True).stdout.strip()
if not os.path.exists(FFMPEG):
    print("!! 缺少 ffmpeg，请安装: scripts/.venv_dl/bin/pip install imageio-ffmpeg")
    sys.exit(1)


def chapter_mp3(ch_dir, out_mp3):
    mp4s = sorted(glob.glob(os.path.join(ch_dir, "*.mp4")))
    if not mp4s:
        print(f"  (跳过, 无视频) {os.path.basename(ch_dir)}")
        return False
    # 第一步: 每个视频单独转成临时 mp3，隔离坏文件
    tmp_mp3s = []
    for p in mp4s:
        tmp = out_mp3 + f".part{len(tmp_mp3s)}.mp3"
        r = subprocess.run(
            [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-err_detect", "ignore_err", "-i", p,
             "-vn", "-c:a", "libmp3lame", "-q:a", "2", tmp],
            capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 1000:
            print(f"  !! 跳过坏文件: {os.path.basename(p)}: {r.stderr[-200:]}")
            if os.path.exists(tmp):
                os.remove(tmp)
            continue
        tmp_mp3s.append(tmp)
    if not tmp_mp3s:
        print(f"  !! 无可用音频 {os.path.basename(ch_dir)}")
        return False
    # 第二步: 拼接所有临时 mp3（同格式, 直接复制）
    list_file = out_mp3 + ".list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for t in tmp_mp3s:
            f.write(f"file '{t.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    r = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", list_file,
         "-c", "copy",
         "-metadata", f"title={os.path.basename(ch_dir)}",
         out_mp3],
        capture_output=True, text=True)
    os.remove(list_file)
    for t in tmp_mp3s:
        os.remove(t)
    if r.returncode != 0:
        print(f"  !! 拼接失败 {os.path.basename(ch_dir)}: {r.stderr[-300:]}")
        return False
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"输出目录: {OUT_DIR}\n")
    ok = 0
    for entry in sorted(os.listdir(SRC_ROOT)):
        ch_dir = os.path.join(SRC_ROOT, entry)
        if not os.path.isdir(ch_dir) or entry == os.path.basename(OUT_DIR):
            continue
        out_mp3 = os.path.join(OUT_DIR, f"{entry}.mp3")
        if chapter_mp3(ch_dir, out_mp3):
            ok += 1
            size = os.path.getsize(out_mp3) / 1024 / 1024
            print(f"  [ok] {entry}.mp3  ({size:.1f} MB)")

    print(f"\n=== 完成: 生成 {ok} 个章节 MP3 ===")


if __name__ == "__main__":
    main()
