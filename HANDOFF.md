# HANDOFF - read this first (updated 2026-10-11, end of session 5)
Repo: adrian001234/upgraded-journey. Wordless 3D snail comedy channel "Tiny Lawn Tales".
Stable facts: SHOW_BIBLE.md (show, hero, rules), PIPELINE.md (how it runs), CLAUDE.md (rules).
This file = what is happening RIGHT NOW. Delete finished items as you finish them.
Other Claude sessions edit this repo in parallel: re-read live files and run list_commits before trusting any note.

## Owner rules
- Not technical. ONE step at a time, plain words, every link/value in its own code block, no tables.
- Voice dictation garbles words (cron heard as "Quran", Mimsi as "mismi"). Treat as transcription errors.
- Be proactive. Say first which GitHub identity you are connected to (get_me). Tell the owner what you are about to do BEFORE each lookup or edit.
- Do the checking yourself. He gets angry when Claude asks him to fetch things Claude could read, or asks permission to read files. Search, compare, give a verdict.
- EVERYTHING FREE, built on Agnes. He has spent nothing in six months. Never suggest paid tools, paid plans or paid budgets, not even as a fallback. This annoyed him a lot in session 5.
- Claude cannot write to this repo directly (403, the connector is aliwaziri10). USE METHOD (b): give the owner the FULL file in a code block plus the edit link https://github.com/adrian001234/upgraded-journey/edit/main/<path>, he pastes it, then read the live file and check size and last lines. The owner HATES the fork method (Sync fork every time, pull request forms): it needed many clicks per change. Use it only for a very large file where pasting is unrealistic, and tell him the exact clicks. Files inside .github/workflows can only be done with (b).
- Never upload a file named like one that exists (the browser renames it "NAME (1).md").
- Owner asked for honest disagreement, not agreement.

## State right now (2026-10-11, re-verify)
- Channel renamed to Tiny Lawn Tales (owner said). Old TechPulse videos being set Private (not verified). YOUTUBE_READY must stay false (publish only runs when it is exactly true).
- Hero: Mimsi the snail. Reference picture refs/mimsi.png not yet confirmed to look right.
- NOTHING HAS RENDERED YET. Test row 'TEST - Mimsi (4 shots)' (id b6ab9697-ae40-4ae0-a3a5-7071708e7f9d) is 'narrated' with 0 clips. Cron "3,18,33,48 * * * *"; GitHub schedules are best effort.
- DONE in session 5: video/generate_video.py now waits 65 s between queue-full tries and tries 55 times per round (was 180 s and 20). Merged and verified live (15999 bytes).
- agnes-test.yml was rewritten: it tests only agnes-video-2.5-flash. Latest result (about 12:00 UTC 2026-10-11, with the newest key the owner pasted into AGNES_API_KEY): HTTP 503 video_queue_full in 0.4 to 1.4 s. Which Agnes login that key came from was not confirmed.
- Sound and assembly were built by the owner on 2026-10-11 (assembly/assemble.py, sound.py, store.py): ffmpeg-made effects and music, no downloads, Agnes audio discarded, clips trimmed to planned durations. NOT tested on real clips.

## AGNES: why nothing renders
PROVEN (sessions 4 and 5):
- 2.5-flash answers video_queue_full in under 2 s every time, with several keys, before Agnes looks at our request. v2.0 answers model_not_found "No available channel". The owner's Agnes Usage page shows 0 requests ever for Adrian's key.
- The AGNES_API_URL secret is NOT used by code. KIE_API_KEY is unused. Two Agnes logins exist (Adrian: this repo; Ali Waziri: the Marius and Nova keys).
- Marius and Nova (aliwaziri10 repos) hard-code agnes-video-v2.0. Marius got model_not_found on 2026-10-11 06:28 UTC and generated 0 shots; it treats any 503 as busy and ends green. Nova is stuck earlier, at narration.
- The Supabase connector is DENIED for Claude (no permission): use GitHub only.
RESEARCH (session 5, web):
- The same error is reported by many unrelated users since at least 2026-09-20: AgnesAI-Labs/AgnesAI-Models issue 142 (opened 2026-10-10, no Agnes reply), lcy362/agnes-video-generator issues 63, 75, 87, and Dream-Pixels-Forge/brandly-cli issues 191, 192, 294 (50+ minutes of refusals on 2026-10-10).
- Best explanation, SECONDHAND from the maintainer of a third-party app (not Agnes): free 2.5-flash runs on a shared GPU pool; when it is full, a submission is rejected at once (no real queue); demand is far above free capacity; v2.0 is a separate pool; retrying over time and off-peak times help. Flash is advertised as free for a limited time.
- model_not_found "No available channel" is gateway routing state, not proof that a model is retired (brandly-cli issue 148). The claim "Agnes retired v2.0 on 2026-09-25" in CLAUDE.md and the generate_video.py header is NOT confirmed. Do not repeat it as fact.
- No Reddit threads, status page or official Agnes statement were found.
- Free alternatives checked: none that is free, allowed for commercial use and automatable. Veo has no free API tier; Pixazo's own API terms say no free calls and forbid unattended scripts; the PixVerse and Magic Hour free tiers are non-commercial; ZSky is browser only; LTX weights are licensed free under 10M USD revenue but need a GPU. Stay on Agnes.
- Do not rewrite generate_video.py for this. The refusal happens before Agnes looks at our request.

## Next steps (one at a time)
1. Let the pipeline retry. After a run, read the Actions log with the owner (lines "Agnes video queue is full (try n/55)" and "Row ..."). If a clip ever completes, judge it: same snail as the picture, eyes emote.
2. Test GEMINI_API_KEY (3 months old, never tested) with a tiny manual workflow, then build the script stage (see Decisions).
3. Reword the "retired on 2026-09-25" claim as unconfirmed in CLAUDE.md (Known past incidents) and in the generate_video.py header comment.
4. Delete tracking/setup.sql (read in session 5: old table shape, no shot_list, shot_durations, video_urls or YouTube columns; nothing Claude read uses it).
5. Confirm with the owner (screenshot of the Supabase table editor, since Claude is denied) that video_pipeline has retry_count and shot_retry_count columns and that a public bucket named videos exists. Assembly needs them.
6. Make sure every shot in a row's shot_list carries a "sound" note (assembly adds only music if not).
7. Optional: a Telegram message when a video finishes or fails (TELEGRAM_* secrets exist). Optional: a comment on Agnes issue 142 (the owner decides).
8. Later: kid-safe publish settings (made-for-kids, Private first), title and chapter helpers, Shorts cuts.

## Decisions (owner agreed, sessions 2 and 5)
- Fully automatic script stage using the free Gemini key (the old stage used gemini-3.5-flash-lite), one video a day at most, 12 to 20 shots, no mass production. No Anthropic key.
- Checks in code before a row is saved: no two close-ups in a row, at least 1 in 4 shots wide, one clear action per shot, every Mimsi shot has "Mimsi the snail" plus her full description, durations 4 to 12 s, no repeated story.
- Order: judge the first clips, then the script stage, then the first real episode = Act 1 of EPISODE_01_SHOTS.md (shots 1 to 9, about 37 s). Do NOT render all 40 shots first.
- Ideas to reuse (free): Jakeschincariol/youtube-agent-skill (MIT, keep the licence): title checker, chapters, retention reader, "gag in the first 5 seconds" check. From aliwaziri10/marius-command-center HANDOFF_2026-10-08_VISUAL_QUALITY_AND_YT_SKILLS.md section 4.3: a clip checker that samples frames and asks Gemini (free) if it is the same character.

## Review findings, not fixed
- Episode 1 shots 26, 37 and 39 hold 3 to 4 actions each; AI clips handle one. Split them. The Episode 1 story is not approved by the owner.
- Only Mimsi gets a reference picture; the sparrow, door, log and crumb are text only and will drift. Unknown if Agnes accepts two pictures.
- Rendering is one shot at a time, 14 to 38 min each: a 40-shot episode takes many hours over several runs.
- Pipeline writes use the Supabase anon key; this works only if the tables and bucket allow public writes. Tighten later.

## Pipeline facts
- pipeline.yml: one run at a time. Video, then Assembly, then Publish only if YOUTUBE_READY == 'true'.
- Repo secrets (names only): AGNES_API_KEY, AGNES_API_URL (unused), FREELLM_API_KEY, FREELLM_API_URL, GEMINI_API_KEY, GH_WRITE_TOKEN, GOOGLE_SERVICE_ACCOUNT_JSON, KIE_API_KEY (unused), SUPABASE_ANON_KEY, SUPABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN. Several look like leftovers: check the code before removing any.

## Cleanup status
- tools/reconcile_youtube.py: read in session 5. Manual only, never changes YouTube. Keep. The owner must NOT press its workflow button: it would copy every video on the channel, including old TechPulse videos, into video_pipeline as published rows.
- Old fork-only work (12 commits: finance and true-crime pivots, OWNERSHIP.md, delete-clip-after-upload change) is on aliwaziri10/upgraded-journey, branch backup-before-sync-2026-10-11. Worth checking: OWNERSHIP.md and the delete after upload change in publish/youtube_upload.py. NEVER open a pull request from that branch.
- Not yet read: publish/youtube_upload.py, make_character_sheet.py, and the two other workflow files.

## Open decisions and honest risks
- YouTube monetization: inauthentic and mass-produced content rules, extra scrutiny of AI kids content. Review every video by hand, upload Private first.
- Agnes Flash is advertised as free for a limited time: the free route may disappear.
- Name collisions for "Tiny Lawn Tales" and "Mimsi" on YouTube were not checked.
