#!/usr/bin/env python3
"""Watch a reel: frames you can look at + a timestamped transcript.

Usage: watch_reel.py <video-file> [--out DIR] [--hook-seconds 3] [--every 0.7] [--model base] [--no-transcript]

Writes into DIR (default: next to the video):
  hook.jpg       dense contact sheet of the opening seconds (one frame every 0.5 s)
  timeline.jpg   sparse contact sheet of the whole reel (about 12 frames)
  dense_NN.jpg   only with --every S: the whole reel, one frame every S seconds, 12 per sheet
  transcript.json / transcript.txt   speech with timestamps (needs faster-whisper)
  watch.json     duration, size, audio info, paths, and what could not be done
Needs ffmpeg/ffprobe. Transcript needs `pip install faster-whisper`.
"""
import argparse, json, os, shutil, subprocess, sys


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(video):
    r = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", video])
    if r.returncode != 0:
        sys.exit(f"ffprobe could not read {video}: {r.stderr.strip()[:300]}")
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    return {"duration_s": round(float(j["format"]["duration"]), 2),
            "width": v and v["width"], "height": v and v["height"], "has_audio": bool(a)}


def sheet(video, out, times, cols, frame_h=480):
    """One labelled frame per timestamp, tiled into a single image."""
    tmp = out + ".frames"
    os.makedirs(tmp, exist_ok=True)
    files = []
    for i, t in enumerate(times):
        f = os.path.join(tmp, f"{i:03d}.jpg")
        label = f"{t:.1f}s"
        vf = (f"scale=-2:{frame_h},drawbox=x=0:y=0:w=110:h=44:color=black@0.7:t=fill,"
              f"drawtext=text='{label}':x=8:y=8:fontsize=28:fontcolor=white")
        r = run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", vf, f])
        if r.returncode != 0:  # drawtext may be missing in minimal ffmpeg builds
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                 "-vf", f"scale=-2:{frame_h}", f])
        if os.path.exists(f):
            files.append(f)
    if not files:
        return None
    rows = -(-len(files) // cols)
    r = run(["ffmpeg", "-y", "-v", "error", "-framerate", "1", "-i", os.path.join(tmp, "%03d.jpg"),
             "-vf", f"tile={cols}x{rows}:padding=6:color=white", "-frames:v", "1", "-q:v", "3", out])
    shutil.rmtree(tmp, ignore_errors=True)
    return out if r.returncode == 0 else None


def transcribe(video, model):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, "faster-whisper is not installed (pip install faster-whisper)"
    try:
        m = WhisperModel(model, device="cpu", compute_type="int8")
        # decode with ffmpeg ourselves: avoids PyAV version problems inside faster-whisper
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                              "-f", "s16le", "-"], capture_output=True).stdout
        audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0
        segs, info = m.transcribe(audio, vad_filter=True, word_timestamps=True)
        segs = list(segs)
    except Exception as e:
        return None, f"Transcription failed ({type(e).__name__}: {str(e)[:200]})"
    out = []
    for s in segs:
        out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                    "words": [{"t": round(w.start, 2), "w": w.word.strip()} for w in (s.words or [])]})
    return {"language": info.language, "language_probability": round(info.language_probability, 2),
            "segments": out}, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("video")
    ap.add_argument("--out")
    ap.add_argument("--hook-seconds", type=float, default=3.0)
    ap.add_argument("--every", type=float, default=0,
                    help="also write dense_NN.jpg sheets with a frame every N seconds (for reels with fast on-screen text)")
    ap.add_argument("--model", default="base")
    ap.add_argument("--no-transcript", action="store_true")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is required (macOS: brew install ffmpeg).")
    out = a.out or os.path.dirname(os.path.abspath(a.video))
    os.makedirs(out, exist_ok=True)
    info = probe(a.video)
    dur = info["duration_s"]
    hook_end = min(a.hook_seconds, dur)
    hook_times = [x * 0.5 for x in range(int(hook_end / 0.5) + 1)]
    n = 12
    tl_times = [min(max(dur - 0.5, 0), hook_end + (dur - hook_end) * i / (n - 1)) for i in range(n)] if dur > hook_end else []
    res = {"video": a.video, **info, "problems": []}
    res["hook_sheet"] = sheet(a.video, os.path.join(out, "hook.jpg"), hook_times, cols=len(hook_times), frame_h=560)
    res["timeline_sheet"] = sheet(a.video, os.path.join(out, "timeline.jpg"), tl_times, cols=6) if tl_times else None
    res["dense_sheets"] = []
    if a.every > 0:
        step = max(a.every, 0.2)
        times = [i * step for i in range(int(dur / step) + 1) if i * step < dur]
        for n in range(0, len(times), 12):
            f = sheet(a.video, os.path.join(out, f"dense_{n // 12 + 1:02d}.jpg"), times[n:n + 12], cols=6)
            if f:
                res["dense_sheets"].append(f)
    res["hook_frame_times"], res["timeline_frame_times"] = hook_times, [round(t, 1) for t in tl_times]
    if not a.no_transcript and info["has_audio"]:
        tr, err = transcribe(a.video, a.model)
        if err:
            res["problems"].append(err)
        else:
            json.dump(tr, open(os.path.join(out, "transcript.json"), "w"), indent=2, ensure_ascii=False)
            lines = [f"[{s['start']:6.2f}-{s['end']:6.2f}] {s['text']}" for s in tr["segments"]]
            open(os.path.join(out, "transcript.txt"), "w").write("\n".join(lines) + "\n")
            res["transcript"] = os.path.join(out, "transcript.txt")
            res["language"] = tr["language"]
            words = [w for s in tr["segments"] for w in s["words"]]
            res["first_spoken_word_at_s"] = words[0]["t"] if words else None
            res["spoken_in_hook_window"] = " ".join(w["w"] for w in words if w["t"] < hook_end)
            if not words:
                res["problems"].append("No speech detected: the reel is likely music/sound only; rely on frames.")
    elif not info["has_audio"]:
        res["problems"].append("No audio track.")
    json.dump(res, open(os.path.join(out, "watch.json"), "w"), indent=2, ensure_ascii=False)
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
