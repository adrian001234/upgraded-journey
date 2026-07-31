"""
TechPulse - Auto-Heal Stage
Runs only when the main pipeline (pipeline.yml) fails. Pulls the failed
run's logs, isolates the Python traceback, identifies the offending file,
asks Gemini for a corrected full-file replacement, writes it, and commits
directly to main. Then re-triggers the pipeline so it runs again with the
fix applied - no human needs to be online for any of this.

Safety limits (deliberate, not accidental):
- Only ever touches files inside the known pipeline stage folders
  (research/, script/, video/, narration/, assembly/, tracking/, publish/).
  Never touches .github/workflows/, this file itself, or anything outside
  the repo's own pipeline code.
- Caps itself at 2 consecutive auto-heal commits. If the pipeline still
  fails after 2 patch attempts, it stops and leaves the failure for a human
  to look at instead of looping forever rewriting the same file.
- Never invents a fix for anything that isn't a Python traceback pointing
  at a specific file/line in this repo (e.g. an external API being down,
  a bad/expired secret, a billing/quota error) - those get logged plainly
  and left alone, since no code patch can fix them.
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
MAX_CONSECUTIVE_HEALS = 2

NON_CODE_ERROR_HINTS = (
    "quota", "billing", "429", "insufficient", "unauthorized", "401", "403",
    "connection refused", "timed out", "timeout", "dns", "service unavailable",
    "502", "503", "504",
)


def sh(cmd, **kw):
    print(f"+ {cmd}")
    return subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True, **kw)


def gh_api(path, method="GET"):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def get_failed_step_log():
    """Fetch the full log bundle for the failed run and return it as text."""
    raw = gh_api(f"/repos/{REPO}/actions/runs/{FAILED_RUN_ID}/logs")
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


def count_recent_autoheal_commits():
    result = sh("git log -n 5 --pretty=format:%s")
    lines = [l for l in result.stdout.splitlines() if l.strip()]
    streak = 0
    for line in lines:
        if line.startswith("[auto-heal]"):
            streak += 1
        else:
            break
    return streak


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
                # normalize to repo-relative path
                idx = path.find(allowed.rstrip("/"))
                return path[idx:]
    return None


def looks_like_non_code_failure(traceback_text):
    lowered = traceback_text.lower()
    return any(hint in lowered for hint in NON_CODE_ERROR_HINTS)


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


def trigger_pipeline_rerun():
    body = json.dumps({"ref": "main"}).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/workflows/pipeline.yml/dispatches",
        data=body,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30)


def main():
    streak = count_recent_autoheal_commits()
    if streak >= MAX_CONSECUTIVE_HEALS:
        print(f"Already made {streak} consecutive auto-heal commits with no green run in between. "
              f"Stopping - this needs a human, not another patch attempt.")
        sys.exit(0)

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

    with open(file_path, "w") as f:
        f.write(fixed_content)

    sh('git config user.name "TechPulse Auto-Heal Bot"')
    sh('git config user.email "auto-heal@techpulsedaily.local"')
    sh(f"git add {file_path}")
    sh(f'git commit -m "[auto-heal] fix {file_path} after run {FAILED_RUN_ID}"')
    sh("git push origin main")

    print(f"Committed an automated fix to {file_path} and pushed to main. Re-triggering the pipeline.")
    trigger_pipeline_rerun()


if __name__ == "__main__":
    main()
