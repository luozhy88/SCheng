#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证所有章节MP3中「来了」是否已清除。用法: python3 verify_clean.py <mp3...>"""
import sys

from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

for path in sys.argv[1:]:
    segments, info = model.transcribe(path, language="zh", vad_filter=False, beam_size=1)
    hits = []
    for seg in segments:
        t = seg.text.strip()
        if "来了" in t or "來" in t:
            hits.append(f"[{seg.start:.1f}-{seg.end:.1f}] {t[:40]}")
    name = path.split("/")[-1]
    status = "OK 无「来了」" if not hits else f"仍有 {len(hits)} 处!"
    print(f"{name}: 时长{info.duration:6.1f}s  {status}")
    for h in hits:
        print("   ", h)
