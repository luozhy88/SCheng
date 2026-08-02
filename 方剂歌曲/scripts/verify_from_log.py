#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 remove_lailai_from_mp3.py 的日志中提取每章「切点」, 调用 verify_clean2.py 验证。

用法:
  python3 verify_from_log.py [日志文件]   # 默认 scripts/reprocess_all2.log
"""
import re
import subprocess
import sys

BASE = "scripts"


def main():
    log = sys.argv[1] if len(sys.argv) > 1 else "scripts/reprocess_all2.log"
    chapter_cutoffs = []   # [(章节, [cutoffs...])]
    cur = None
    with open(log, encoding="utf-8") as f:
        for line in f:
            m = re.search(r"\[识别\] (\S+) \.\.\.", line)
            if m:
                cur = m.group(1)
                continue
            m = re.search(r"切点: \[(.*)\]", line)
            if m and cur:
                vals = [float(x) for x in re.findall(r"\d+\.\d+", m.group(1))]
                chapter_cutoffs.append((cur, vals))
                cur = None
    print(f"从 {log} 解析到 {len(chapter_cutoffs)} 个章节的切点")
    bad = 0
    for ch, cutoffs in chapter_cutoffs:
        cmd = [f"{BASE}/.venv_asr/bin/python", f"{BASE}/verify_clean2.py",
               ch, "--cutoffs", ",".join(f"{c:.3f}" for c in cutoffs)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        out = (r.stdout + r.stderr)
        out = "\n".join(l for l in out.splitlines() if "Warning" not in l)
        print(out)
        if "有疑点" in out:
            bad += 1
    print(f"\n=== 完成: {len(chapter_cutoffs)-bad}/{len(chapter_cutoffs)} 章干净 ===")


if __name__ == "__main__":
    main()
