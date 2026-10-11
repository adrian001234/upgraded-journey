# HANDOFF - read this first (updated 2026-10-11, end of session 4)
Repo: adrian001234/upgraded-journey. Wordless 3D snail comedy channel "Tiny Lawn Tales".
Stable facts: SHOW_BIBLE.md (show, hero, rules), PIPELINE.md (how it runs), CLAUDE.md (rules).
This file = what is happening RIGHT NOW. Delete finished items as you finish them.
Other Claude sessions edit this repo in parallel: re-read live files and run list_commits before trusting any note.

## Owner rules
- Not technical. ONE step at a time, plain words, every link/value in its own code block, no tables.
- Owner uses voice dictation: garbles happen (cron heard as "Quran", Mimsi as "mismi"). Treat as transcription errors.
- Be proactive. Say first which GitHub identity you are connected to (get_me). Tell the owner what you are about to do BEFORE each lookup or edit.
- Do the checking yourself. The owner got angry in session 4 when Claude kept asking him to fetch things Claude could read (Marius and Nova repos, logs). Search, compare with the sister repos, and give a verdict without hedging.
- Claude cannot write to this repo directly (403). Two ways: (a) CLAUDE.md Rule 10 fork method (owner must first press Sync fork on aliwaziri10/upgraded-journey; the fork was STALE on 2026-10-11), or (b) give the owner the FULL file in a code block plus the edit link https://github.com/adrian001234/upgraded-journey/edit/main/<path> to paste over, then read the live file and check size and last lines. Session 4 used (b). Files inside .github/workflows can only be done with (b).
- Never upload a file named like one that exists (the browser renames it to "NAME (1).md").
- Owner asked for honest disagreement, not agreement. Free tools only until the business makes $5,000.

## State right now (all dated 2026-10-11, re-verify)
- YouTube channel renamed to Tiny Lawn Tales (owner said). Old TechPulse videos being set to Private (not verified).
  YOUTUBE_READY must stay false (publish only runs when it is exactly true).
- Hero: Mimsi the snail. Reference picture refs/mimsi.png: not yet confirmed to open and look right.
- NOTHING HAS RENDERED YET. Test row 'TEST - Mimsi (4 shots)' (id b6ab9697-ae40-4ae0-a3a5-7071708e7f9d) is
  'narrated' with 0 clips. The pipeline retries by itself (cron "3,18,33,48 * * * *") and uses no retry while Agnes refuses.
  Last known scheduled-run behaviour: unreliable, GitHub runs schedules best-effort. Re-check the Actions page.

## AGNES FINDINGS (session 4) - the blocker
PROVEN:
- Workflow ".github/workflows/agnes-test.yml" ("Agnes Quick Test", manual) now tests agnes-video-v2.0 and then
  agnes-video-2.5-flash with one plain 4-second text request each. Results with the key from ADRIAN's Agnes login,
  run twice (about 10:44 and 10:51 UTC, before and after making a new key under the same login):
  v2.0 -> HTTP 503 code model_not_found "No available channel for model agnes-video-v2.0 under group default".
  2.5-flash -> HTTP 503 code video_queue_full, answered in 0.2 to 0.4 s, every time. A new key made no difference.
  The earlier real pipeline runs (#887, #888) got the same queue-full answer for 14+ hours. The owner's Agnes Usage page shows 0 requests ever.
- The AGNES_API_URL secret is NOT used by any code. The address is written into the code (https://apihub.agnes-ai.com) and matches Agnes's own catalog. pipeline.yml gives the video stage only AGNES_API_KEY.
- KIE_API_KEY is not used by any code in this repo or in aliwaziri10's repos. Leftover, not a backup video source.
- Two separate Agnes accounts exist. The key in this repo's AGNES_API_KEY secret came from Adrian's login. Marius and Nova use
  keys from the Ali Waziri login (keys named "marius" created 2026-07-09 and "Nova Command Center" created 2026-07-07 and 2026-07-06).
  Screenshot of the Ali login: "Last used" marius 2026-10-09 09:48 UTC, Nova 2026-10-09 10:30 UTC.
- Marius (aliwaziri10/marius-command-center) hard-codes agnes-video-v2.0 in scripts/agnes_client.py. On 2026-10-06 its run really
  rendered clips on v2.0 (the video ids decode to model_id agnes-video-v2.0). On 2026-10-11 06:28 UTC its run got model_not_found four times
  and generated 0 shots. So v2.0 stopped working for the Ali account between about 2026-10-09 10:30 UTC and 2026-10-11 06:28 UTC.
  Marius treats any 503 as "Agnes is busy", files a quiet note and ends the run green, so it raised no alert. It has uploaded nothing
  since at least 2026-10-07 (uploaded=3, 14 scripts waiting; script 378fd92c is at 24 of 33 shots).
- Nova (aliwaziri10/NovaCommandCenter) also hard-codes agnes-video-v2.0 in .github/scripts/generate_videos.py. Its own notes show it stuck earlier, at the narration stage since 2026-10-06 (Render GITHUB_PAT suspect), so it has not reached clips.
- Supabase connector was DENIED ("no permission") on both the Marius and Nova projects in session 4: use GitHub only until reconnected.
NOT PROVEN / UNKNOWN:
- The date "Agnes retired agnes-video-v2.0 on 2026-09-25" (written in CLAUDE.md and the generate_video.py header) is NOT confirmed. It worked for the Ali account until about 2026-10-09. Do not repeat it as fact; ask Agnes.
- Whether the Ali Waziri Agnes account gets agnes-video-2.5-flash jobs accepted. NOT TESTED YET. This is the next test.
- Whether Agnes capacity or something on Adrian's account (plan, credits, approval) causes the queue-full answer.
- A support message for Agnes was drafted in chat (queue full, request ids 20261011105303498600848Uhevd3UA and 202610111045428644317163MD7tINL, asks if the queue is down or if the account needs a plan, credits or approval). Not known to be sent.
Do not rewrite generate_video.py for this. The code is right for 2.5-flash and the refusal happens before Agnes looks at our request.

## Next steps (one at a time)
1. The owner already made a NEW Agnes key under the Ali Waziri login and copied it (2026-10-11). It is NOT yet in any secret.
   Step: owner opens https://github.com/adrian001234/upgraded-journey/settings/secrets/actions , pencil on AGNES_API_KEY, pastes the key, Update secret.
2. Owner runs "Agnes Quick Test" (https://github.com/adrian001234/upgraded-journey/actions/workflows/agnes-test.yml : Run workflow twice),
   opens the run, step "Test old and new Agnes model with a 4 second clip", pastes the lines.
   - If 2.5-flash is ACCEPTED (status lines, DONE with a video URL): the Ali account works. The pipeline will start rendering by itself. Judge the clip when it exists (same snail as the picture, eyes emote).
     Then Marius and Nova should move to 2.5-flash too, but only after step 3 below is planned.
   - If it says video_queue_full again: Agnes is jammed or the free plan blocks video for all accounts. Owner sends the support message to Agnes (website agnes-ai.com, Discord or Contact). Then research free video options (spending rule: free only until $5,000).
3. Only if step 2 shows 2.5-flash works for the Ali account: update Marius scripts/agnes_client.py and Nova .github/scripts/generate_videos.py to agnes-video-2.5-flash. New request format: seconds as a string "4" to "12", size "720P", aspect_ratio "16:9", n 1, mode "text" or "reference" with an images list and "<Picture 1>" in the prompt, NO width/height/num_frames, poll with model_name=agnes-video-2.5-flash. Also make Marius treat model_not_found as a real FAULT (not an overload note) so the failed-run alert fires.
4. Edit CLAUDE.md "Known past incidents": the 2026-10-10 line says Agnes retired v2.0 on 2026-09-25 as fact. Reword it as unconfirmed.
5. Older items still open: judge the 4-shot test once a clip exists; delete tracking/setup.sql through a pull request; read assembly/assemble.py and rewrite assembly with sound; test the Gemini key; build the script stage.

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

## Pipeline facts
- pipeline.yml: concurrency allows one run at a time. Video, then Assembly, then Publish only if YOUTUBE_READY == 'true'.
- Repo secrets present (names only): AGNES_API_KEY, AGNES_API_URL (unused), FREELLM_API_KEY, FREELLM_API_URL, GEMINI_API_KEY,
  GH_WRITE_TOKEN, GOOGLE_SERVICE_ACCOUNT_JSON, KIE_API_KEY (unused), SUPABASE_ANON_KEY, SUPABASE_URL, TELEGRAM_BOT_TOKEN,
  TELEGRAM_CHAT_ID, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN. GEMINI_API_KEY is 3 months old, never tested.
  Several look like leftovers: check the code before removing any.

## Cleanup status
- DONE 2026-10-11: README.md and SHOW_BIBLE.md fixed (Mimsi, refs/mimsi.png). The one "Nori" left in SHOW_BIBLE is the history note.
- tracking/setup.sql: old wrong schema (no shot_list or video_urls). Recommended: delete it. Not done yet.
- tools/reconcile_youtube.py: manual only, never changes YouTube. Keep. Owner must NOT press the Reconcile workflow
  button: it would copy every old TechPulse video into video_pipeline.
- NOT yet read: assembly/assemble.py (will be rewritten). The owner liked how bright the old videos looked: keep what is good.
- Old fork-only work (12 commits: finance and true-crime pivots, OWNERSHIP.md, delete-clip-after-upload change) is on
  aliwaziri10/upgraded-journey, branch backup-before-sync-2026-10-11. Worth checking: OWNERSHIP.md, and the delete
  after upload change in publish/youtube_upload.py (the live copy may already differ).

## Open decisions and honest risks
- YouTube monetization: inauthentic and mass-produced content rules, extra scrutiny of AI kids content.
