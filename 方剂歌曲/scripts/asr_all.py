#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""转写章节MP3, 输出全部片段。用法: python3 asr_all.py <mp3>"""
import sys

from faster_whisper import WhisperModel

mp3 = sys.argv[1]
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe(mp3, language="zh", word_timestamps=False,
                                  vad_filter=True)
print(f"音频时长: {info.duration:.1f}s")
for seg in segments:
    print(f"[{seg.start:7.2f}s - {seg.end:7.2f}s] {seg.text.strip()}")
