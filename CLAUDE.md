# Project Instructions — Upgraded Journey (TechPulse)

These rules apply to every task in this repo. They exist because past sessions on this
and sibling projects (Marius, Nova) have hit real bugs and unwanted changes caused by
skipping them. Follow them even under time pressure.

## 1. Think Before Coding
Before writing or changing code, state the assumption being made out loud. If a request
is ambiguous (e.g. which pipeline stage, which script, which table), ask rather than
guessing. Do not silently pick an interpretation and run with it.

## 2. Simplicity First
Write the minimum code that solves the stated problem. No speculative features, no
extra abstraction, no "while I'm here" additions. If a fix can be 10 lines, it should
not be 100.

## 3. Surgical Changes
Edit only what the task requires. Do not refactor, rename, or "clean up" working code
as a side effect. Match the existing style of the file being edited. Do not remove or
alter comments/code you don't fully understand just because they look unrelated.

## 4. Goal-Driven Execution, Not Blind Imperatives
When given a goal (e.g. "fix the tracking sync bug"), verify the fix against a concrete
success condition (e.g. "tracking stage runs with 0 failures on next pipeline run") —
don't stop at "I made a change that looks related."

## 5. No Unilateral Behavior Changes
Do not change pipeline behavior (auto-upload settings, approval gates, visibility/privacy
settings, cron schedules) without explicit confirmation first, even if it seems like an
obvious improvement. State the proposed change and wait for a yes.

## 6. Full Files, Not Diffs
This project's owner is a non-coder working by copy-paste. Every changed file must be
delivered as a complete file, never as a line-by-line diff or "change line X" instruction.

## 7. Verify Before Reporting Success
Do not report a fix as working, or a status as confirmed (e.g. "video is unlisted"),
without actually checking it. If it can't be verified, say so plainly instead of assuming.

## Known past incidents (do not repeat)
- Backup restore crashed on HTTP 400 from Supabase Storage (only 404 was handled). Fixed
  in db-backup.ts — readTarget() now treats 400 as "no backup found."
- FREEAPI_DB_BACKUP_KEY / ENCRYPTION_KEY must be exactly 64 hex characters. A 63-char key
  silently no-ops the backup instead of erroring loudly — always verify length before
  assuming it's correct.
- YT_REFRESH_TOKEN can be valid but scoped to the wrong YouTube channel if the wrong
  account was selected during OAuth. A working upload to the *wrong* channel (e.g.
  Erased instead of TechPulse Daily) looks like success in logs — always confirm which
  channel a token is authorized for, not just that it works.

## Access notes
- GitHub write access via the Claude.ai connector is unreliable (403) even when the
  connector shows full read/write. Read access works. Assume file changes must be
  handed to the user as full copy-paste content for manual commit unless a write succeeds.
- User has no terminal/SSH access — browser dashboards only (GitHub web editor, Render,
  Supabase). Never suggest local dev or CLI commands.

## How to work with the project owner
- He is a non-coder. He runs this project by talking Claude through it, step by step —
  he does not read or edit code himself.
- Give simple, step-by-step instructions. Perform the task, don't explain it at length.
  Minimal explanation — long write-ups waste his time and tokens.
- The goal each time is the end result (a working fix, a pasted file, a clicked button),
  not a lesson in how the code works.
- Every path, URL, or anything to be copied must be given in a copy-paste code block,
  no exceptions.
