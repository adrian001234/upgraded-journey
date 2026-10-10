# HANDOFF - read this first (updated 2026-10-11, end of session 3)
Repo: adrian001234/upgraded-journey. Wordless 3D snail comedy channel "Tiny Lawn Tales".
Stable facts: SHOW_BIBLE.md (show, hero, rules), PIPELINE.md (how it runs), CLAUDE.md (rules).
This file = what is happening RIGHT NOW. Delete finished items as you finish them.
Other Claude sessions edit this repo in parallel: re-read live files and run list_commits before trusting any note.

## Owner rules
- Not technical. ONE step at a time, plain words, every link/value in its own code block, no tables.
- Owner uses voice dictation: garbles happen (cron heard as "Quran", Mimsi as "mismi"). Treat as transcription errors.
- Be proactive. Say first which GitHub identity you are connected to (get_me). Tell the owner what you are about to do BEFORE each lookup or edit.
- Claude cannot write to this repo directly (403). Use the fork method in CLAUDE.md Rule 10: new branch on
  aliwaziri10/upgraded-journey (branch from claude-access-note or a synced main), write full files, give the owner
  the compare link, owner clicks Create pull request then Merge, then read the live files and check last lines.
  Files inside .github/workflows CANNOT be written even on the fork (403, tested 2026-10-11): give the owner the
  full file in a code block plus the link https://github.com/adrian001234/upgraded-journey/edit/main/.github/workflows/<name>.yml
  to paste over, then read the live file and check its last lines.
- Never upload a file named like one that exists (the browser renames it to "NAME (1).md").
- Owner asked for honest disagreement, not agreement. Free tools only until the business makes $5,000.

## State right now
- YouTube channel renamed to Tiny Lawn Tales (owner said). Old TechPulse videos being set to Private (not verified).
  YOUTUBE_READY must stay false (publish only runs when it is exactly true).
- Hero: Mimsi the snail, spelling confirmed by the owner 2026-10-11. Reference picture refs/mimsi.png: not yet
  confirmed to open and look right.
- NOTHING HAS RENDERED YET. Test row 'TEST - Mimsi (4 shots)' (id b6ab9697-ae40-4ae0-a3a5-7071708e7f9d) is
  'narrated' with 0 clips. Runs #887 (scheduled) and #888 (manual, 1:32 AM 2026-10-11, 58 min) both ended the
  same way: Agnes answered 503 video_queue_full on shot 1 for all 20 tries (180 s apart), so 0 shots were made. The row
  stays 'narrated' and no retry is used up. The owner's Agnes Usage page shows 0 requests and 0 video seconds ever:
  Agnes never accepted a job. Code was read and is right (model agnes-video-2.5-flash, endpoints /v1/videos and
  /agnesapi). A public write-up says the free plan allows about 1 video request per minute. Cause looks like Agnes
  capacity, not our code. Unknown if it clears. Do not rewrite the video stage for this.
- Schedule: GitHub runs scheduled workflows best-effort. With cron */5 only about one scheduled run every 4 hours
  appeared (#882 8:20 PM, #887 12:25 AM) and none for 2.5 hours after #888. On 2026-10-11 the owner pasted a new
  pipeline.yml with cron "3,18,33,48 * * * *" (verified live, file complete). Check whether scheduled runs now
  appear. If still unreliable: an outside trigger (cron-job.org calling workflow_dispatch with a token) is the fallback.
- pipeline.yml: concurrency allows one run at a time. Video, then Assembly, then Publish only if YOUTUBE_READY == 'true'.
- Repo secrets present (names only): AGNES_API_KEY, AGNES_API_URL, FREELLM_API_KEY, FREELLM_API_URL, GEMINI_API_KEY,
  GH_WRITE_TOKEN, GOOGLE_SERVICE_ACCOUNT_JSON, KIE_API_KEY, SUPABASE_ANON_KEY, SUPABASE_URL, TELEGRAM_BOT_TOKEN,
  TELEGRAM_CHAT_ID, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN. GEMINI_API_KEY is 3 months old, never tested.
  Several look like leftovers: check the code before removing any.

## Decisions made in session 2 (owner agreed)
- Fully automatic script stage, one video a day at most, 12 to 20 shots, no mass production.
- It uses the free Gemini key (GEMINI_API_KEY exists in secrets; the old script stage used gemini-3.5-flash-lite).
  No Anthropic key. Test the key before building on it.
- Checks in code before a row is saved: no two close-ups in a row, at least 1 in 4 wide, one clear action per shot,
  every Mimsi shot has "Mimsi the snail" plus her full description, durations 4 to 12 s, no repeated story.
- Order: (1) judge the 4-shot test, (2) rewrite assembly to add music and effects from free sound files using the
  SOUND notes in the shot list, (3) build the script stage, (4) first real episode = Act 1 of EPISODE_01_SHOTS.md
  (shots 1 to 9, about 37 s). Do NOT render all 40 shots until the test is judged.
- Ideas to reuse: Jakeschincariol/youtube-agent-skill (MIT, keep the licence notice): title and thumbnail checker,
  chapter builder, retention reader, "gag in the first 5 seconds" check. From aliwaziri10/marius-command-center
  (HANDOFF_2026-10-08_VISUAL_QUALITY_AND_YT_SKILLS.md, section 4.3): a clip checker that samples frames and asks
  Gemini (free) if it is the same character, then re-renders on a fail.

## Review findings, not fixed yet
- No sound: assembly is still the old news version and needs narration_url. The show depends on sound.
- Episode 1 shots 26, 37 and 39 hold 3 to 4 actions each; AI clips handle one. Split or simplify. Shots under 4 s
  round up to 4 s. The Episode 1 story is not approved by the owner.
- Only Mimsi gets a reference picture. The sparrow, door, log and crumb are text only and will drift.
- Rendering is one shot at a time, 14 to 38 min each, so a 40-shot episode takes many hours over several runs.
- Pipeline writes use the Supabase anon key: works only if tables and bucket allow public writes. Tighten later.

## Cleanup status
- DONE 2026-10-11: README.md and SHOW_BIBLE.md fixed (Mimsi, refs/mimsi.png). The one "Nori" left in SHOW_BIBLE is the history note.
- tracking/setup.sql: old wrong schema (no shot_list or video_urls). Recommended: delete it. Not done yet.
- tools/reconcile_youtube.py: manual only, never changes YouTube. Keep. Owner must NOT press the Reconcile workflow
  button: it would copy every old TechPulse video into video_pipeline.
- NOT yet read: assembly/assemble.py (will be rewritten). The owner liked how bright the old videos looked: keep what is good.
- Old fork-only work (12 commits: finance and true-crime pivots, OWNERSHIP.md, delete-clip-after-upload change) is on
  aliwaziri10/upgraded-journey, branch backup-before-sync-2026-10-11. Worth checking: OWNERSHIP.md, and the delete
  after upload change in publish/youtube_upload.py (the live copy may already differ).

## Next steps (one at a time)
1. Owner opens the Actions page for pipeline.yml, says if scheduled runs now appear and how often, and pastes the
   "Row ..." lines from the newest Video step (run-pipeline, Video stage).
2. If a clip exists (public bucket video_clips, <row id>/shot_000.mp4 ...), judge it: same snail as the picture,
   eyes emote. A wide shot may start close because the picture is a medium shot. If Agnes still says queue full
   after a day, ask the owner to check the Agnes Discord or docs for the cause.
3. Delete tracking/setup.sql through a fork pull request. Read assembly/assemble.py. Then rewrite assembly with sound,
   test the Gemini key, then build the script stage.

## Open decisions and honest risks
- YouTube monetization: inauthentic and mass-produced content rules, extra scrutiny of AI kids content. Review every
  video by hand, upload Private first, publish a few polished different stories, not volume.
- "Tiny Lawn Tales" and "Mimsi" were never checked for name collisions on YouTube.
- Comedy that needs precise timing is hard for AI video; expect re-renders. Agnes credits and limits unknown.

## Later
Make publish kid-safe (made-for-kids flag, category, Private or unlisted first, description source); episodes 2 to 5;
compilations of 4 to 5 episodes; vertical cuts for Shorts.
