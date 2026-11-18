#!/usr/bin/env python3
"""Rank Instagram reels by views, from accounts and/or reel links. Free, no login, no API key.

Usage:
  find_hook_reels.py --accounts erika.prompts brandinsights.ai --links <url> <url> [--out ranked.json]
  find_hook_reels.py --accounts-file accounts.txt --links-file links.txt

For each account it reads the public profile embed page, which lists only the ~6 most recent
posts, then reads each reel's public embed page for views/likes/comments/caption.
So the ranking covers "recent posts of these accounts + the links given", never all of Instagram.
Prints a markdown table and writes full JSON. Standard library only.
"""
import argparse, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_reel import get, parse, shortcode  # noqa: E402

HOOK_WORDS = re.compile(r"\bhooks?\b|scroll|first (second|3 seconds|three seconds)|viral", re.I)


def account_posts(user):
    user = user.strip().lstrip("@").rstrip("/").split("/")[-1]
    page = get(f"https://www.instagram.com/{user}/embed/").decode("utf8", "ignore")
    codes = list(dict.fromkeys(re.findall(r'shortcode\\*":\\*"([A-Za-z0-9_-]+)', page)))
    f = re.search(r'edge_followed_by\\*":\{\\*"count\\*":(\d+)', page)
    return user, codes, int(f.group(1)) if f else None


def read_list(path):
    return [l.strip() for l in open(path) if l.strip() and not l.startswith("#")] if path else []


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--accounts", nargs="*", default=[])
    ap.add_argument("--accounts-file")
    ap.add_argument("--links", nargs="*", default=[])
    ap.add_argument("--links-file")
    ap.add_argument("--out", default="ranked.json")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests (be gentle)")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()
    accounts = a.accounts + read_list(a.accounts_file)
    links = a.links + read_list(a.links_file)
    if not accounts and not links:
        sys.exit("Give --accounts and/or --links.")
    todo, followers, problems = {}, {}, []
    for l in links:
        todo.setdefault(shortcode(l), "link")
    for acc in accounts:
        try:
            user, codes, fol = account_posts(acc)
            followers[user] = fol
            if not codes:
                problems.append(f"@{user}: no posts visible (private, renamed, or blocked)")
            for c in codes:
                todo.setdefault(c, f"@{user}")
        except Exception as e:
            problems.append(f"@{acc}: {e}")
        time.sleep(a.delay)
    rows = []
    for code, src in todo.items():
        try:
            page = get(f"https://www.instagram.com/p/{code}/embed/captioned/").decode("utf8", "ignore")
            m = parse(code, page)
        except Exception as e:
            problems.append(f"{code}: {e}")
            continue
        time.sleep(a.delay)
        if not m["is_video"]:
            continue  # photo/carousel
        if m["views"] is None:
            problems.append(f"{code}: no view count exposed")
        m["found_via"] = src
        m["account_followers"] = followers.get(m.get("username"))
        m["views_per_follower"] = (round(m["views"] / m["account_followers"], 1)
                                   if m["views"] and m["account_followers"] else None)
        m["mentions_hooks"] = bool(HOOK_WORDS.search(m.get("caption") or ""))
        m.pop("video_url", None)
        rows.append(m)
    # known view counts first (by views); hidden-count reels after, by comments
    rows.sort(key=lambda r: (r["views"] is not None, r["views"] or 0, r["comments"] or 0), reverse=True)
    json.dump({"reels": rows, "followers": followers, "problems": problems,
               "coverage": "Only the links given plus the ~6 most recent posts per account."},
              open(a.out, "w"), indent=2, ensure_ascii=False)
    print("| # | Views | Likes | Comments | Views/follower | Account | Hook topic? | Link | Caption opener |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows[:a.top], 1):
        cap = (r.get("caption") or "").split("\n")[0][:70].replace("|", "/")
        f = lambda x: f"{x:,}" if isinstance(x, int) else "hidden"
        print(f"| {i} | {f(r['views'])} | {f(r['likes'])} | {f(r['comments'])} | {r['views_per_follower'] or '-'} | "
              f"@{r.get('username','?')} | {'yes' if r['mentions_hooks'] else 'no'} | {r['url']} | {cap} |")
    for p in problems:
        print("PROBLEM:", p, file=sys.stderr)
    hidden = sum(1 for r in rows if r["views"] is None)
    if hidden:
        print(f"\n{hidden} reel(s) have hidden view counts: listed last, ordered by comments. Not zero views.")
    print(f"\nFull data (complete captions): {a.out}")


if __name__ == "__main__":
    main()
