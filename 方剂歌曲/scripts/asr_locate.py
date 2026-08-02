#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""转写章节MP3, 找出包含关键词的片段时间戳。用法: python3 asr_locate.py <mp3> <关键词>"""
import sys

from faster_whisper import WhisperModel

mp3 = sys.argv[1]
kw = sys.argv[2] if len(sys.argv) > 2 else "来了"

model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe(mp3, language="zh", word_timestamps=True,
                                  vad_filter=True)
print(f"音频时长: {info.duration:.1f}s  语言: {info.language}")
n = 0
for seg in segments:
    text = seg.text.replace("\n", " ").strip()
    if kw in text:
        n += 1
        print(f"[{seg.start:7.2f}s - {seg.end:7.2f}s] {text}")
    elif n < 3 and seg.end < 60:
        pass
print(f"\n含「{kw}」的片段数: {n}")
