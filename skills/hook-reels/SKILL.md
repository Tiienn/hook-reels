---
name: hook-reels
description: Finds, watches and breaks down Instagram "hook reels" - reels that show or teach viral hooks (the opening seconds that stop the scroll). Use this whenever the user pastes an Instagram reel or post link and wants to know what is in it, wants the hook of a reel, asks for the most popular hook reels, viral hooks, hook clips, hook templates or hook ideas for their own reels, or names hook-teaching accounts to scan. An Instagram link is not something you can watch on your own - this skill downloads the reel, pulls the opening frames and transcribes the speech, so never describe a reel from its link or caption alone. Free, no API key, no login.
---

# Hook reels

A "hook reel" is a reel from a creator who teaches hooks. The usual shapes:

- **Borrowed clip + explanation**: a proven viral clip plays silently for the first seconds (often with an on-screen "45M views" label), then a voice explains why it stops the scroll.
- **Template list**: "7 hooks that always work" - fill-in-the-blank lines, each with an example.
- **Named technique**: one hook pattern with a name ("Unfinished Countdown Hook") and a breakdown.

The user wants the hooks out of these reels: what the hook is, why it works, which ones are most popular, and hooks they can use themselves.

## Tools

All in this skill's `scripts/` folder (call them by absolute path). Python 3, `ffmpeg`, and for speech `pip install faster-whisper` (optional `pip install yt-dlp` as a download fallback). Work in a scratch folder, not inside the skill folder.

| Script | Does |
|---|---|
| `find_hook_reels.py --accounts a b --links url url --out ranked.json` | Ranks reels by views. Prints a markdown table. |
| `fetch_reel.py <link> --out reels` | Caption, views, likes, comments, duration → `reels/<code>/meta.json`, plus `video.mp4`. |
| `watch_reel.py reels/<code>/video.mp4` | `hook.jpg` (a frame every 0.5 s for the first 3 s), `timeline.jpg` (12 frames across the reel), `transcript.txt` (plus `transcript.json` with word timings), `watch.json`. Add `--every 0.7` for `dense_NN.jpg` sheets covering the whole reel. |

Then **Read `hook.jpg` and `timeline.jpg` as images** and read `transcript.txt`. The frames carry what the transcript cannot: the borrowed clip, on-screen text, the view-count label.

**When the reel shows several hooks or templates** (a list reel, or any reel where the timeline shows text changing between frames), the 12-frame timeline skips most of them. Re-run with `--every 0.7 --no-transcript` and read every `dense_NN.jpg`. This is what lets you copy templates and view-count badges from the screen instead of from a transcript that mishears them.

Links may be `/p/<code>/`, `/reel/<code>/` or `/reels/<code>/`; all work. In `meta.json`, `null` means Instagram did not expose that field.

If a download fails, the scripts say why. Do not guess the content: ask the user for the downloaded file and run `watch_reel.py` on it. If `faster-whisper` cannot fetch its model, retry with `HF_HUB_DISABLE_XET=1`.

## Which job is it?

**"What's in this reel?" / a pasted link** → `fetch_reel.py`, `watch_reel.py`, look at both images, then report (format below). For several links, do each.

**"Find the most popular hook reels"** → build a candidate list, rank it, then watch the top ones:
1. Candidates: accounts the user names and links the user gives. If they name none, use `references/accounts.txt` (a starter list of hook-teaching accounts) and say that you did. If you have web search, add more: search for things like `instagram reel viral hooks <niche>` or `site:instagram.com/reel hook templates`, and collect reel links and account handles from the results.
2. Run `find_hook_reels.py` on all of them.
3. Drop rows where "Hook topic?" is `no` unless the full caption in `ranked.json` is clearly about hooks (a creator's top reel is often off-topic). Mention what you dropped.
4. Pick 5-10 to watch (fewer if the user wants a quick answer). Go down the ranking, but spread the picks: at least one reel per account the user named, and when one account has several reels in the same format (same caption opener), watch the top one or two, not all of them.
5. Some accounts hide view and like counts. Those reels show `hidden` and sit at the bottom ordered by comments. That is unknown, not zero: still watch the most-commented one from such an account, and list it as unranked.
6. Report. Describe unwatched reels from their captions only and label them "not watched".

**"Give me hooks for my niche"** → do one of the above first so the ideas rest on real reels, then adapt. Read `references/hook-patterns.md` for the pattern names and how to adapt a pattern to a niche.

## What to report

For each reel:

- **Link, account, views, likes, comments** (from `meta.json`).
- **The hook being shown**: describe the opening seconds from `hook.jpg` - what is on screen, any text overlay, and the first spoken words with their timestamp. If the reel showcases someone else's clip, describe that clip and quote any view count shown for it.
- **Pattern**: one name from `references/hook-patterns.md`, or your own short label if none fits.
- **Why it works**: the creator's stated reason (from the transcript), marked as their claim.
- **Templates**, if the reel lists them: copy each one with its example and any view count shown for the example clip. When screen and speech differ, the on-screen text is the template and the speech is the fallback; say which words you could not confirm on screen.
- Use the creator's own name for a hook when they give one ("Warning Hook"), and add the pattern name from the reference in brackets if it differs.

Then, across the set: which patterns show up most, and **5-10 ready-to-use hooks** for the user's niche, each tagged with the reel it is modelled on. If you do not know the niche, ask, or give niche-neutral versions and say so.

Keep it scannable: a ranked table first, then one short block per reel, then the ideas.

For a single link, skip the ranked table and the cross-set tally: give the one block, and answer the question asked first (if they asked only for the templates, lead with the templates).

## How sure you can be

Say these plainly when they matter; they are the difference between a useful report and a misleading one.

- **No post dates.** The pages do not expose when a reel was posted, so "right now" can only mean "among each account's newest posts".
- **View counts are real but narrow.** They come from Instagram's public embed page at the moment you ran the script, and tick up between runs. Some reels expose no view count; list them as unknown rather than dropping or guessing.
- **"Most popular" means most viewed among the reels you checked**, not on Instagram. An account page exposes only its ~6 newest posts, so older hits are invisible unless someone supplies the link. State what you covered: "ranked 23 reels from 5 accounts".
- **Claims inside a reel are unverified.** "This clip hit 45M views" is the creator's on-screen claim about someone else's video. Report it as claimed.
- **A hook reel's own views do not prove the hook works.** These reels usually end with "comment HOOKS", which inflates comments and reach. High views show the reel is popular, not that the pattern will work for the user.
- **Transcripts mishear.** Short words, names and template placeholders ("X for Y") often come out wrong. Check lines against on-screen text in the frames, and fix obvious errors rather than quoting nonsense.
- **Silent openings are normal.** Borrowed-clip reels often have no speech for 3-8 seconds; the hook is visual. `first_spoken_word_at_s` tells you.
- **Frames are samples**, one every 0.5 s. Fast cuts between them are missed.

## Limits and manners

- Public reels only. Private, deleted or age-gated reels return nothing; say so.
- Instagram may rate-limit or block a network. The scripts pause between requests; do not strip the delay or scan dozens of accounts in one go. If requests start failing, stop and report what you have.
- Downloaded videos are for analysis. Do not offer to repost a creator's clip; if the user wants to reuse a borrowed clip as their own hook, point out it belongs to someone else and suggest filming their own version of the pattern.
