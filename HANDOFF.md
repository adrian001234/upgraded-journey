# HANDOFF - read this first (updated 2026-10-11, end of session 2)
Repo: adrian001234/upgraded-journey. Wordless 3D snail comedy channel "Tiny Lawn Tales".
Stable facts: SHOW_BIBLE.md (show, hero, rules), PIPELINE.md (how it runs), CLAUDE.md (rules).
This file = what is happening RIGHT NOW. Delete finished items as you finish them.
Other Claude sessions edit this repo in parallel: re-read live files and run list_commits before trusting any note.

## Owner rules
- Not technical. ONE step at a time, plain words, every link/value in its own code block, no tables.
- Be proactive. Say first which GitHub identity you are connected to (get_me).
- Claude cannot write to this repo directly (403, tested 2026-10-11). Use the fork method in CLAUDE.md Rule 10:
  sync the fork aliwaziri10/upgraded-journey, write full files to a NEW branch there, open a pull request to this
  repo, owner merges, then read the live files and check size and last lines. Never upload a file named like one
  that exists (the browser renames it to "NAME (1).md"). Never open a pull request from the backup branch.
- Owner asked for honest disagreement, not agreement. Free tools only until the business makes $5,000.

## State right now
- YouTube channel renamed to Tiny Lawn Tales (owner said). Old TechPulse videos being set to Private (not verified).
  YOUTUBE_READY must stay false (publish only runs when it is exactly true).
- Hero: Mimsi the snail, spelled M-I-M-S-I (this is what the repo uses). The owner once dictated "Mimsy" and has not
  re-confirmed the spelling since. Ask once. Reference picture refs/mimsi.png: not yet confirmed to open and look right.
- Owner says the first pipeline run started 2026-10-11. Claude could not see it (no Actions access, and the Supabase
  connector refused queries with a permission error). Last known state of the test row 'TEST - Mimsi (4 shots)':
  narrated, 0 clips (checked 20:08 UTC 2026-10-10). Nothing has been proven against real Agnes yet.
- pipeline.yml: cron every 5 min, Video then Assembly then Publish only if YOUTUBE_READY == 'true'.

## Decisions made in session 2 (owner agreed)
- Fully automatic script stage, one video a day at most, 12 to 20 shots, no mass production.
- It uses the free Gemini key (the old script stage used GEMINI_API_KEY with gemini-3.5-flash-lite). No Anthropic key.
  The secrets list in PIPELINE.md has no GEMINI_API_KEY: check repo Settings, Secrets before building.
- Checks in code before a row is saved: no two close-ups in a row, at least 1 in 4 wide, one clear action per shot,
  every Mimsi shot has "Mimsi the snail" plus her full description, durations 4 to 12 s, no repeated story.
- Order: (1) judge the 4-shot test, (2) rewrite assembly to add music and effects from free sound files using the
  SOUND notes in the shot list, (3) build the script stage, (4) first real episode = Act 1 of EPISODE_01_SHOTS.md
  (shots 1 to 9, about 37 s). Do NOT render all 40 shots until the test is judged.
- Ideas to reuse: from Jakeschincariol/youtube-agent-skill (MIT, keep the licence notice): title and thumbnail
  checker, chapter builder, retention reader, a "gag in the first 5 seconds" check. From
  aliwaziri10/marius-command-center (HANDOFF_2026-10-08_VISUAL_QUALITY_AND_YT_SKILLS.md, section 4.3): a clip checker
  that samples frames and asks Gemini (free) if it is the same character, then re-renders on a fail.

## Review findings, not fixed yet
- No sound: assembly is still the old news version and needs narration_url. The show depends on sound.
- Episode 1 shots 26, 37 and 39 hold 3 to 4 actions each; AI clips handle one. Split or simplify. Shots under 4 s
  round up to 4 s. The Episode 1 story is not approved by the owner.
- Only Mimsi gets a reference picture. The sparrow, door, log and crumb are text only and will drift. Unknown if
  Agnes accepts two pictures.
- Rendering is one shot at a time, 14 to 38 min each, so a 40-shot episode takes many hours over several runs.
- Pipeline writes use the Supabase anon key: works only if tables and bucket allow public writes. Tighten later.

## Cleanup status
- The live repo no longer has script, research, narration or autoheal folders. NOT yet read or decided:
  assembly/assemble.py (will be rewritten), tracking/setup.sql, tools/reconcile_youtube.py. The owner liked how
  bright the old videos looked and said keep whatever is good. Read before deleting anything.
- Old fork-only work (12 commits: finance and true-crime pivots, OWNERSHIP.md, delete-clip-after-upload change) is on
  aliwaziri10/upgraded-journey, branch backup-before-sync-2026-10-11. Worth checking: OWNERSHIP.md, and the delete
  after upload change in publish/youtube_upload.py (the live copy may already differ).
- Stale notes to fix: SHOW_BIBLE lines 14-15 still say pip.png "do not rename it" (now refs/mimsi.png); SHOW_BIBLE
  has 1 leftover "Nori" and README.md has 2: replace with Mimsi.

## Next steps (one at a time)
1. The pull request from branch claude-access-note on the fork (this file and CLAUDE.md) must be merged by the owner.
   Then read the live files and check size and last lines.
2. Ask the owner whether GEMINI_API_KEY is in the repo secrets (Settings, Secrets and variables, Actions).
3. Owner opens the Actions page for pipeline.yml, says what is spinning, green or red, and pastes the "Row ..." lines.
4. When clips exist (public bucket video_clips, <row id>/shot_000.mp4 ...) judge them together: same snail as the
   picture, eyes emote, sprinkler water, sparrow. A wide shot may start close because the picture is a medium shot.
5. Read setup.sql and reconcile_youtube.py, propose what to delete. Then assembly with sound, then the script stage.

## Open decisions and honest risks
- YouTube monetization: inauthentic and mass-produced content rules, extra scrutiny of AI kids content. Review every
  video by hand, upload Private first, publish a few polished different stories, not volume.
- "Tiny Lawn Tales" was never checked for name collisions on YouTube. Mimsi collisions also not checked.
- Comedy that needs precise timing is hard for AI video; expect re-renders. Agnes credits and limits unknown.

## Later
Make publish kid-safe (made-for-kids flag, category, Private or unlisted first, description source); episodes 2 to 5;
compilations of 4 to 5 episodes; vertical cuts for Shorts.
