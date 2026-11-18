#!/usr/bin/env python3
"""Fetch one public Instagram reel: caption, counts and (when exposed) the video file.

Usage: fetch_reel.py <reel-url-or-shortcode> [--out DIR] [--no-video]

Reads the public embed page (no login, no API key). Writes DIR/<shortcode>/meta.json
and DIR/<shortcode>/video.mp4. If the page does not expose the video it falls back to
yt-dlp when installed; if that fails too, meta.json says so. Standard library only.
"""
import argparse, html, json, os, re, shutil, subprocess, sys, urllib.request

UA = "hook-reels-skill/1.0"


def shortcode(s):
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{5,}", s):
        return s
    sys.exit(f"Not an Instagram post/reel link or shortcode: {s}")


def get(url, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def unescape_js(s):
    # value sits inside a JSON string that is itself inside a JSON string
    for _ in range(3):
        s = s.replace("\\/", "/").replace("\\\\", "\\")
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)
    return s.replace("\\", "")


def first_int(pattern, text):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def parse(code, page):
    meta = {"shortcode": code, "url": f"https://www.instagram.com/reel/{code}/"}
    m = re.search(r'<div class="Caption"[^>]*>(.*?)<div class="CaptionComments"', page, re.S)
    if m:
        body = m.group(1)
        u = re.search(r'class="CaptionUsername"[^>]*>([^<]+)<', body)
        if u:
            meta["username"] = u.group(1).strip()
            body = body.split(u.group(0), 1)[1]
            body = re.sub(r"^\s*/a>", "", body)
        body = re.sub(r"<br\s*/?>", "\n", body)
        text = html.unescape(re.sub(r"<[^>]+>", "", body))
        meta["caption"] = re.sub(r"[ \t]+", " ", text).strip()
    if "username" not in meta:
        u = re.search(r'class="UsernameText"[^>]*>([^<]+)<', page)
        if u:
            meta["username"] = u.group(1).strip()
    meta["views"] = first_int(r'video_view_count\\*":\s*(\d+)', page)
    meta["plays"] = first_int(r'video_play_count\\*":\s*(\d+)', page)
    meta["likes"] = first_int(r'edge_liked_by\\*":\s*\{\\*"count\\*":\s*(\d+)', page)
    if meta["likes"] is None:
        m = re.search(r'likeCountClick"[^>]*>([\d,]+) likes', page)
        if m:
            meta["likes"] = int(m.group(1).replace(",", ""))
    if meta["views"] is None and not meta["likes"]:
        meta["likes"] = None  # account hides counts; 0 here is not a real zero
    meta["comments"] = first_int(r'edge_media_to_comment\\*":\s*\{\\*"count\\*":\s*(\d+)', page)
    d = re.search(r'video_duration\\*":\s*([\d.]+)', page)
    meta["duration_s"] = float(d.group(1)) if d else None
    t = first_int(r'taken_at_timestamp\\*":\s*(\d+)', page)
    meta["taken_at_unix"] = t
    v = re.search(r'video_url\\*":\s*\\*"(.*?)\\*"[,}]', page)
    meta["video_url"] = unescape_js(v.group(1)) if v else None
    meta["is_video"] = bool(v) or "video_view_count" in page
    return meta


def ytdlp(code, path):
    """Fallback downloader. Returns None on success, else a reason."""
    exe = shutil.which("yt-dlp")
    cmd = [exe] if exe else [sys.executable, "-m", "yt_dlp"]
    try:
        r = subprocess.run(cmd + ["-q", "--no-warnings", "-f", "mp4/best", "-o", path,
                                  f"https://www.instagram.com/reel/{code}/"],
                           capture_output=True, text=True, timeout=180)
    except Exception as e:
        return f"yt-dlp could not run ({e})"
    if r.returncode == 0 and os.path.exists(path):
        return None
    return "yt-dlp failed: " + (r.stderr.strip().splitlines() or ["not installed (pip install yt-dlp)"])[-1][:200]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("reel")
    ap.add_argument("--out", default="reels")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    code = shortcode(a.reel)
    d = os.path.join(a.out, code)
    os.makedirs(d, exist_ok=True)
    try:
        page = get(f"https://www.instagram.com/p/{code}/embed/captioned/").decode("utf8", "ignore")
    except Exception as e:
        sys.exit(f"Could not open the reel page ({e}). Instagram may be blocked or rate-limiting; "
                 "ask the user for the downloaded video file instead.")
    meta = parse(code, page)
    meta["video_file"] = None
    if not meta.get("caption") and meta["views"] is None:
        meta["note"] = "Embed page had no data: the reel may be private, deleted, age-gated or login-only."
    elif not a.no_video:
        path = os.path.join(d, "video.mp4")
        err = "page did not expose a video URL"
        if meta["video_url"]:
            try:
                open(path, "wb").write(get(meta["video_url"], timeout=120))
                err = None
            except Exception as e:
                err = f"direct download failed ({e})"
        if err:
            err2 = ytdlp(code, path)
            if err2:
                meta["note"] = f"No video: {err}; {err2}. Ask the user for the downloaded file."
            else:
                meta["downloaded_with"] = "yt-dlp"
        if os.path.exists(path):
            meta["video_file"] = path
    json.dump(meta, open(os.path.join(d, "meta.json"), "w"), indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in meta.items() if k != "video_url"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
