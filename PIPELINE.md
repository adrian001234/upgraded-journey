# TechPulse Pipeline — Status

Last verified live against GitHub + Supabase: 2026-08-06.
Re-verify against live data before trusting this doc at face value — it drifts.

## Architecture (long-form, single workflow, Supabase-native)

One GitHub Actions workflow (`.github/workflows/pipeline.yml`), cron every 5
minutes, `concurrency: techpulse-pipeline` with `cancel-in-progress: false`
so overlapping triggers queue instead of racing. `timeout-minutes: 300`.

Every video is a single `video_pipeline` row in Supabase, created once by
the script stage and updated in place by every stage after it — nothing
downstream ever matches rows back together by title/text.

Status progression: `scripted` → `narrated` → `video_complete` →
`video_generated` → `published` (or `failed` at any stage after
`RETRY_LIMIT` exhausted, where retry logic exists).

**Gate step** (runs every tick, before anything else): if any row has
`status in (scripted, narrated, video_complete)`, a story is already in
progress and Research/Script are skipped this tick — only Narration/Video/
Assembly/Publish run, each picking up whatever's oldest at their own stage.

| Stage | File | Reads | Writes | Notes |
|---|---|---|---|---|
| Research | `research/sources.py` | RSS feeds, `video_pipeline` (dedup check) | `research/latest_headlines.json` | Dedup by `link`, falls back to exact `title` match if link is empty (fixed 2026-08-06) |
| Script | `script/generate_script.py` | `latest_headlines.json` | new row: `script`, `shot_list` (JSON, `{narration_excerpt, visual_description}` per shot), `status='scripted'` | Gemini `gemini-3.5-flash-lite`, ~900-1100 word narration, 45 shots |
| Narration | `narration/generate_narration.py` | oldest `status='scripted'` row | `narration_url`, `shot_durations`, `status='narrated'` | Chatterbox TTS, per-sentence synthesis, voice=Mark F. Smith (LibriVox), `TEMPO_FACTOR=1.25` |
| Video | `video/generate_video.py` | oldest `status='narrated'` row (`shot_list` + `shot_durations`) | `video_urls`, `status='video_complete'` | Agnes API, one shot at a time, sized to real narration timing (not hardcoded) |
| Assembly | `assembly/assemble.py` | oldest `status='video_complete'` row | `video_url`, `status='video_generated'` | ffmpeg concat + ambient bed mix; has `retry_count`/`RETRY_LIMIT=3`, requeues to `video_complete` on failure instead of failing permanently |
| Publish | `publish/youtube_upload.py` | oldest `status='video_generated'` row with `youtube_video_id is null` | `youtube_video_id`, `youtube_url`, `published_at`, `status='published'` | Gated behind repo variable `YOUTUBE_READY` (confirmed `true`, permanent). Matches by stable row `id`, not text. Retries via `retry_count` before permanent `failed`. |

## Known-good fixes already live (don't re-break these)
- Script/Narration/Video schema is fully aligned on `shot_list` /
  `narration_excerpt` / `visual_description` / `shot_durations` — all three
  files were mismatched against each other until 2026-08-05; verify all
  three still agree before editing any one of them in isolation.
- `timeout-minutes: 300` (raised from 20 on 2026-08-06) — Chatterbox TTS is
  a real per-sentence CPU inference (60-90 sentences for a long-form
  script) plus up to 45 sequential Agnes shot generations in the same job;
  20 min was silently killing runs mid-pipeline.
- Research dedup checks `title` as a fallback when RSS `link` is empty —
  don't revert to link-only dedup.
- Assembly and Publish both match by row `id`, retry via `retry_count`
  before permanent `failed` — don't reintroduce text-based matching.

## Standing risks (flagged, not fixed — decide before touching)
- **`autoheal/heal.py`** (triggered by `.github/workflows/auto_heal.yml` on
  any pipeline failure) asks Gemini to patch one file in isolation from a
  traceback and commits straight to `main` via its own `GITHUB_TOKEN` —
  bypasses the 403 that blocks all other GitHub write access to this repo.
  Zero cross-file schema awareness; this is what produced the Script/
  Narration/Video mismatch on 2026-08-04. **Currently disabled by Zia
  (2026-08-06).** Re-enabling it without a cross-file consistency check is
  a real risk of re-breaking the schema fix above.
- `public.video_shots` table: RLS disabled (anon key can read/write it),
  and no longer used by the rewritten `generate_video.py`. Candidate for
  dropping entirely rather than just enabling RLS — pending confirmation.

## GitHub write access
`create_or_update_file` and `push_files` both confirmed 403 on this repo
(retested 2026-08-05) — not intermittent, not an exception to the Nova/
Marius pattern. All edits go through the GitHub web editor:
give the exact `https://github.com/adrian001234/upgraded-journey/edit/main/<path>`
link and full file content, Zia pastes and commits, then re-verify live.
