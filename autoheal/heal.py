"""
TechPulse - Auto-Heal Stage
Runs only when the main pipeline (pipeline.yml) fails. Pulls the failed
run's logs, isolates the Python traceback, identifies the offending file,
asks Gemini for a corrected full-file replacement, and opens a PULL
REQUEST with the proposed fix - it never commits to main directly.

REWRITTEN 2026-08-06 (safety redesign): the previous version committed
straight to main and re-triggered the pipeline automatically, with no
human checkpoint. That's exactly the mechanism behind the 2026-08-04/05
schema-mismatch incident - a change that looks correct in isolation can
silently break the handoff to an adjacent stage, and nothing caught it
before it went live. This version keeps everything else about auto-heal
(diagnosis, drafting a fix) but requires a human to actually merge the
fix before it touches production code. It also no longer auto-retriggers
the pipeline - the existing 15-min cron continues on its own regardless,
so healthy stories keep moving/publishing exactly as before; only the one
broken row waits on a human merge.

Safety limits (deliberate, not accidental):
- Only ever touches files inside the known pipeline stage folders
  (research/, script/, video/, narration/, assembly/, tracking/, publish/).
  Never touches .github/workflows/, this file itself, or anything outside
  the repo's own pipeline code.
- NEVER commits to main. Always opens a PR on a new branch instead - a
  human must review and merge before the fix takes effect.
- Skips creating a PR if one is already open for the same file, to avoid
  spamming a new PR every 15 minutes while a persistent bug goes unfixed.
- Fixes touching publish/ (the YouTube upload code - highest real-world
  consequence of anything in this repo, since a bad "fix" here could
  double-upload or upload to the wrong channel) get an explicit
  "HIGH RISK" prefix on the PR title so they're not accidentally
  rubber-stamped.
- Never invents a fix for anything that isn't a Python traceback pointing
  at a specific file/line in this repo (e.g. an external API being down,
  a bad/expired secret, a billing/quota error) - those get logged plainly
  and left alone, since no code patch can fix them.
- Does not re-trigger the pipeline. The existing cron schedule already
  covers that - this stage's only job is to propose a reviewed fix.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_KEY}"
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]  # e.g. "adrian001234/upgraded-journey"
FAILED_RUN_ID = os.environ["FAILED_RUN_ID"]

ALLOWED_DIRS = ("research/", "script/", "video/", "narration/", "assembly/", "tracking/", "publish/")
HIGH_RISK_DIRS = ("publish/",)

NON_CODE_ERROR_HINTS = (
    "quota", "billing", "429", "insufficient", "unauthorized", "401", "403",
    "connection refused", "timed out", "timeout", "dns", "service unavailable",
    "502", "503", "504",
)


def sh(cmd, **kw):
    print(f"+ {cmd}")
    return subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True, **kw)


def gh_api(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw.strip() else None


def get_failed_step_log():
    """Fetch the full log bundle for the failed run and return it as text."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/runs/{FAILED_RUN_ID}/logs",
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    log_path = "/tmp/failed_run_logs.zip"
    with open(log_path, "wb") as f:
        f.write(raw)
    out_dir = "/tmp/failed_run_logs"
    sh(f"mkdir -p {out_dir} && cd {out_dir} && unzip -o -q {log_path}")
    combined = ""
    for root, _, files in os.walk(out_dir):
        for name in files:
            if name.endswith(".txt"):
                with open(os.path.join(root, name), errors="replace") as f:
                    combined += f.read() + "\n"
    return combined


def extract_traceback(log_text):
    """Find the last Python traceback block in the combined logs."""
    blocks = re.findall(r"Traceback \(most recent call last\):.*?(?:Error|Exception)[^\n]*", log_text, re.DOTALL)
    if not blocks:
        return None
    return blocks[-1][-4000:]  # last traceback, capped in size


def find_offending_file(traceback_text):
    """Pull the last in-repo file path referenced in the traceback."""
    matches = re.findall(r'File "([^"]+\.py)", line (\d+)', traceback_text)
    for path, _ in reversed(matches):
        for allowed in ALLOWED_DIRS:
            if allowed.rstrip("/") in path:
                idx = path.find(allowed.rstrip("/"))
                return path[idx:]
    return None


def looks_like_non_code_failure(traceback_text):
    lowered = traceback_text.lower()
    return any(hint in lowered for hint in NON_CODE_ERROR_HINTS)


def branch_name_for(file_path):
    safe = file_path.replace("/", "-").replace(".", "-")
    return f"auto-heal/{safe}"


def existing_open_pr_for_branch(branch):
    prs = gh_api(f"/repos/{REPO}/pulls?state=open&head={REPO.split('/')[0]}:{branch}")
    return bool(prs)


def call_gemini_for_fix(file_path, file_content, traceback_text):
    prompt = f"""You are fixing a Python file in an automated content pipeline that just crashed.

FILE: {file_path}

CURRENT CONTENT:
{file_content}

TRACEBACK FROM THE FAILED RUN:
{traceback_text}

Fix the bug that caused this traceback. Rules:
- Output the COMPLETE corrected file content, nothing else - no markdown fences, no explanation, no commentary.
- Make the minimal change needed to fix the actual bug. Do not refactor, rename things, change formatting style, or "improve" unrelated code.
- Do not remove any existing functionality, comments, or safety/retry logic that isn't related to this bug.
- Do not change field names, status values, or the shape of any data written to or read from the database unless the traceback explicitly requires it - other pipeline stages depend on these staying exactly as they are.
- If you cannot determine a confident fix from the traceback alone, output exactly: NO_CONFIDENT_FIX
"""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
    }).encode()
    req = urllib.request.Request(GEMINI_URL, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read())
    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = text.removeprefix("```python").removeprefix("```").removesuffix("```").strip()
    return text


def open_pr(branch, file_path, traceback_text, is_high_risk):
    title = f"[auto-heal] fix {file_path} after run {FAILED_RUN_ID}"
    if is_high_risk:
        title = f"\u26a0\ufe0f HIGH RISK - {title} (touches YouTube publish code - review carefully)"

    body_lines = [
        f"Automated fix proposed after pipeline run {FAILED_RUN_ID} failed.",
        "",
        "**This PR was NOT auto-merged.** Auto-heal only drafts a fix now - review it like any other change before merging.",
        "",
        f"File: `{file_path}`",
    ]
    if is_high_risk:
        body_lines += [
            "",
            "**This file is part of the YouTube publish stage.** A wrong fix here could ",
            "cause a duplicate upload, an upload to the wrong channel, or a silently lost ",
            "status write-back. Read the diff carefully before merging.",
        ]
    body_lines += [
        "",
        "<details><summary>Traceback that triggered this fix</summary>",
        "",
        "```",
        traceback_text,
        "```",
        "</details>",
    ]

    gh_api(f"/repos/{REPO}/pulls", method="POST", body={
        "title": title,
        "head": branch,
        "base": "main",
        "body": "\n".join(body_lines),
    })


def main():
    log_text = get_failed_step_log()
    traceback_text = extract_traceback(log_text)

    if not traceback_text:
        print("No Python traceback found in the failed run's logs. This isn't a code bug I can "
              "patch (likely a config, secret, or infra issue) - leaving it for a human to check.")
        sys.exit(0)

    if looks_like_non_code_failure(traceback_text):
        print("Failure looks like an external/infra issue (quota, auth, timeout, service outage) "
              "rather than a code bug. No patch can fix this - leaving it as-is:")
        print(traceback_text)
        sys.exit(0)

    file_path = find_offending_file(traceback_text)
    if not file_path:
        print("Traceback didn't point at a file inside the pipeline's own code "
              "(research/script/video/narration/assembly/tracking/publish). Not touching anything outside that scope.")
        print(traceback_text)
        sys.exit(0)

    if not os.path.exists(file_path):
        print(f"Traceback pointed at {file_path} but it doesn't exist in this checkout. Aborting.")
        sys.exit(0)

    branch = branch_name_for(file_path)
    if existing_open_pr_for_branch(branch):
        print(f"An auto-heal PR for {file_path} is already open (branch {branch}). "
              f"Not opening a duplicate - merge or close the existing one first.")
        sys.exit(0)

    with open(file_path) as f:
        original_content = f.read()

    fixed_content = call_gemini_for_fix(file_path, original_content, traceback_text)

    if fixed_content == "NO_CONFIDENT_FIX" or not fixed_content.strip():
        print(f"Gemini could not produce a confident fix for {file_path}. Leaving it for a human.")
        print(traceback_text)
        sys.exit(0)

    if fixed_content.strip() == original_content.strip():
        print("Proposed fix is identical to the current file - nothing to change. Stopping.")
        sys.exit(0)

    is_high_risk = any(file_path.startswith(d) for d in HIGH_RISK_DIRS)

    with open(file_path, "w") as f:
        f.write(fixed_content)

    sh('git config user.name "TechPulse Auto-Heal Bot"')
    sh('git config user.email "auto-heal@techpulsedaily.local"')
    sh(f"git checkout -b {branch}")
    sh(f"git add {file_path}")
    sh(f'git commit -m "[auto-heal] fix {file_path} after run {FAILED_RUN_ID}"')
    sh(f"git push origin {branch}")

    open_pr(branch, file_path, traceback_text, is_high_risk)

    print(f"Opened a PR proposing a fix to {file_path} on branch {branch}. "
          f"Waiting for human review - main is untouched, and the normal pipeline cron "
          f"continues running on its existing schedule regardless.")


if __name__ == "__main__":
    main()
