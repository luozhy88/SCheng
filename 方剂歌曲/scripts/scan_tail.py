#!/usr/bin/env python
"""Scan all videos: find where whisper's 今天 anchor falls vs actual greeting speech end.

Output (JSON): per video, whisper anchor T, energy-derived speech end before anchor,
and flag "TAIL" if speech continues past T (i.e. cutting at T leaves greeting tail).
"""
import sys, glob, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

SR = 16000
WIN = 0.02
SPEECH = 0.06     # rms above -> speech
LOW = 0.04        # rms below -> silence-ish

def energy_profile(audio, upto=3.5):
    a = audio[:int(upto*SR)]
    n = int(WIN*SR)
    rms = []
    for i in range(0, len(a)-n, n):
        rms.append(float(np.sqrt(np.mean(a[i:i+n]**2))))
    return rms

def first_speech_block_end(rms):
    """End of the first continuous speech block (greeting), after initial silence.
    Returns (start, end) in seconds, or None if no clear block."""
    n = len(rms)
    i = 0
    # skip initial silence
    while i < n and rms[i] < SPEECH:
        i += 1
    if i >= n:
        return None
    start = i * WIN
    # walk while speech; then find where low region begins
    while i < n and rms[i] >= SPEECH:
        i += 1
    # now i is first frame below SPEECH after greeting start
    # find the dip: require >=5 consecutive low frames (>=0.1s)
    j = i
    low_run = 0
    while j < n:
        if rms[j] < LOW:
            low_run += 1
            if low_run >= 5:
                return (start, (j - low_run + 1) * WIN)
        else:
            low_run = 0
        j += 1
    return (start, (i) * WIN)  # no clear dip; end at first frame below speech

def main():
    model = WhisperModel("base", device="cpu", compute_type="int8")
    vids = sorted(glob.glob(os.path.join("output", "video", "*.mp4")))
    out = []
    for v in vids:
        name = os.path.basename(v)
        rec = {"video": name}
        try:
            audio = decode_audio(v, sampling_rate=SR)
            seg = audio[:int(3.0*SR)]
            segs, _ = model.transcribe(seg, language="zh", word_timestamps=True,
                                       vad_filter=False, beam_size=1)
            words = []
            for s in segs:
                for w in (s.words or []):
                    words.append((w.start, w.end, w.word))
            rec["words"] = [(round(a,2), b, c) for a, b, c in words[:6]]
            # anchor: first word whose first char is a known 今天 variant
            t = None
            for a, b, c in words:
                ch = c.strip()[:1]
                if ch in "今經进進経要背備备":
                    t = a
                    break
            rec["anchor"] = round(t, 3) if t is not None else None
            rms = energy_profile(audio)
            blk = first_speech_block_end(rms)
            rec["greeting_block"] = [round(blk[0],3), round(blk[1],3)] if blk else None
            if t is not None and blk is not None:
                speech_end = blk[1]
                rec["tail_if_cut_at_anchor"] = round(speech_end - t, 3)
                rec["flag"] = "TAIL" if speech_end > t + 0.04 else "ok"
            elif t is None:
                rec["flag"] = "NO_ANCHOR"
            else:
                rec["flag"] = "NO_BLOCK"
            out.append(rec)
            print(f"{name}: {rec['flag']} anchor={rec.get('anchor')} block_end={rec.get('greeting_block')} words={[(w[0],w[2]) for w in rec['words']]}", flush=True)
        except Exception as ex:
            rec["flag"] = "ERR"
            rec["err"] = str(ex)
            out.append(rec)
            print(f"{name}: ERR {ex}", flush=True)
    with open("scripts/scan_tail_results.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    ntail = [r for r in out if r.get("flag") == "TAIL"]
    print(f"\nDONE. {len(out)} videos, TAIL candidates: {len(ntail)}")
    for r in ntail:
        print("  TAIL:", r["video"], "anchor=", r["anchor"], "speech_end=", r["greeting_block"][1] if r.get("greeting_block") else None)

if __name__ == "__main__":
    main()
