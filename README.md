# hook-reels

An agent skill that finds, watches and breaks down Instagram "hook reels": reels that show or teach viral hooks.

- Paste a reel link and the agent downloads it, looks at the opening frames and reads the transcript.
- Ask for the most popular hook reels and it ranks reels from accounts and links by real view counts.
- Get the hook, the pattern behind it, and ready-to-use hooks for your niche.

Free: no API key, no login. Public reels only.

## Install

```
npx skills add Tiienn/hook-reels -a claude-code -g -y
```

Needs Python 3 and `ffmpeg` (`brew install ffmpeg`), plus:

```
pip install faster-whisper yt-dlp
```

## Skills

| Skill | What it does |
|---|---|
| [hook-reels](skills/hook-reels/SKILL.md) | Find, watch and break down Instagram hook reels |

## Honest limits

"Most popular" means most viewed among the reels checked, not across all of Instagram: an account's public page shows only its newest ~6 posts. Downloading reels is against Instagram's terms of use; use it for your own analysis and do not repost other people's clips.

MIT license.
