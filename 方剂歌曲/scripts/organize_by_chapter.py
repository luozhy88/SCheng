#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按章节整理抖音方剂合集视频
==========================
读取 scripts/章节顺序.txt（章节 + 方剂顺序），把 output/video/ 下的视频
按章节复制到「方剂合集_按章节整理/」文件夹，每个章节一个子文件夹，
文件名带章节内序号（按列表顺序）。

用法：
  python3 organize_by_chapter.py
"""
import os
import re
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SRC_DIR = os.path.join(ROOT, "output", "video")
OUT_DIR = os.path.join(ROOT, "output", "方剂合集_按章节整理")
LIST_FILE = os.path.join(BASE, "章节顺序.txt")

# 标题与文件名不一致的映射（用户列表中的名字 → 视频文件名中的名字）
FUZZY = {
    "麻黄杏仁甘草石膏汤": ["麻杏石甘汤"],
    "人参败毒散": ["败毒散"],
    "犀角地黄汤": ["xi角地黄汤歌", "犀角地黄汤"],
    "黄连解毒汤": ["黄连解毒汤歌"],
    "青蒿鳖甲汤": ["青蒿鳖甲汤汤"],
    "香薷散": ["香薷饮"],
    "萆薢分清散": ["萆薢分清饮"],
    "川芎茶调散": ["咳血方"],          # 第109天被博主误标为《咳血方》
}
# 同名多文件时按天指定
BY_DAY = {
    "咳血方": 106,
    "川芎茶调散": 109,
}


CN = "零一二三四五六七八九"

def cn_to_int(s):
    """汉字数字(一~十八)转整数"""
    if s == "十":
        return 10
    if "十" in s:
        a, b = s.split("十")
        return (cn_to_int(a) if a else 1) * 10 + (cn_to_int(b) if b else 0)
    return CN.index(s)


def parse_list():
    chapters = []          # [(章节名, [方剂名, ...]), ...]
    cur = None
    for raw in open(LIST_FILE, encoding="utf-8"):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^([一二三四五六七八九十]+)[、，,.]+\s*(.+剂)$", line)
        if m:
            if cur is not None:
                chapters.append(cur)
            cur = (f"{cn_to_int(m.group(1)):02d}_{m.group(2)}", [])   # 数字打头，如 01_解表剂
            continue
        m = re.match(r"^(\d+)[\.、]?\s*([\u4e00-\u9fff]+)", line)
        if m and cur is not None:
            cur[1].append(m.group(2))
    if cur is not None:
        chapters.append(cur)
    return chapters


def collect_videos():
    """返回 {文件名中的方剂名(标准化): [绝对路径, ...]}"""
    index = {}
    for f in sorted(os.listdir(SRC_DIR)):
        if not f.endswith(".mp4"):
            continue
        m = re.match(r"第(\d+)天_(.+)\.mp4$", f)
        if not m:
            continue
        day = int(m.group(1))
        name = m.group(2)
        norm = re.sub(r"[\s_]+", "", name).lower()
        index.setdefault((norm, name), []).append((day, os.path.join(SRC_DIR, f)))
    return index


def pick_file(index, formula):
    """根据方剂名找源视频文件路径。返回 (绝对路径, 天) 或 None"""
    day_target = BY_DAY.get(formula)
    candidates = []

    def scan(names):
        for cand in names:
            norm = re.sub(r"[\s_]+", "", cand).lower()
            for (n, disp), lst in index.items():
                if norm in n:
                    candidates.extend(lst)

    scan([formula])
    scan(FUZZY.get(formula, [formula]))

    # 去重
    seen, uniq = set(), []
    for day, path in candidates:
        if path in seen:
            continue
        seen.add(path)
        uniq.append((day, path))
    if not uniq:
        return None
    uniq.sort(key=lambda x: abs(x[0] - (day_target or 0)) if day_target else (x[0] == 0))
    if day_target:
        for day, path in uniq:
            if day == day_target:
                return path, day
    day, path = uniq[0]
    return path, day


def main():
    chapters = parse_list()
    print(f"解析到 {len(chapters)} 个章节, 共 {sum(len(c[1]) for c in chapters)} 个方剂")
    index = collect_videos()
    print(f"源目录视频: {len(index)} 个")

    os.makedirs(OUT_DIR, exist_ok=True)
    used = set()
    missing = []        # 列表中有但没视频的
    matched = 0
    other_left = list(index.values())

    for ch_name, formulas in chapters:
        ch_dir = os.path.join(OUT_DIR, ch_name)
        os.makedirs(ch_dir, exist_ok=True)
        print(f"\n== {ch_name} ==")
        for pos, formula in enumerate(formulas, start=1):
            res = pick_file(index, formula)
            if not res:
                missing.append((ch_name, formula))
                print(f"  缺视频: 第{pos:02d}位 {formula}")
                continue
            path, day = res
            if path in used:
                print(f"  警告: {formula} 的视频已被其他条目使用: {path}")
                continue
            used.add(path)
            matched += 1
            fname = f"{pos:02d}_{formula}(第{day:03d}天).mp4"
            shutil.copy2(path, os.path.join(ch_dir, fname))
            print(f"  {fname}")

    # 未匹配到任何章节条目的视频 → 其他文件夹
    other = os.path.join(OUT_DIR, "其他（未在列表中）")
    os.makedirs(other, exist_ok=True)
    for lst in other_left:
        for day, path in lst:
            if path in used:
                continue
            shutil.copy2(path, os.path.join(other, os.path.basename(path)))
            used.add(path)

    print("\n=== 结果 ===")
    print(f"已归入章节: {matched}")
    print(f"未匹配放入「其他」: {len(used) - matched}")
    print(f"列表中缺少视频: {len(missing)}")
    for ch, f in missing:
        print(f"  [{ch}] {f}")
    print(f"\n输出目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
