#!/usr/bin/env python3
"""Health check for the duo-watch listener. One source of truth for the GitHub watchdog and Grok Bot.

Usage:  python3 scripts/health.py [--repo ryancwho/duo-watch] [--act]
Needs:  gh CLI with a token that can read Actions and Contents (and dispatch workflows for --act).
Prints one JSON line: {"verdict": ..., "last_check_age_min": ..., "active_runs": [...], "action": ...}

Verdicts
  OK        a watcher run is active and the data branch saw a check within STALE_MIN minutes
  STARTING  a watcher run is active, data is stale, but the newest run began < 15 min ago (handover in progress)
  STUCK     a watcher run is active but no check has been published for > STALE_MIN minutes -> alert a human
  DOWN      no watcher run is queued or running -> start one (with --act)
  BACKOFF   DOWN, but >= 3 watcher runs failed in the last 60 min (GitHub Actions likely degraded) -> alert, do not retry
  ENDED     past STOP_DATE; nothing to do
"""
import argparse, base64, json, subprocess, sys
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
STALE_MIN = 25          # publishes happen at least every 10 min, overnight checks every ~10 min
STOP_DATE = "2027-01-31"


def gh(args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout) if r.stdout.strip() else {}


def parse(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def check(repo):
    now = datetime.now(timezone.utc)
    if now.astimezone(HKT).strftime("%Y-%m-%d") > STOP_DATE:
        return {"verdict": "ENDED", "action": "none"}
    st = json.loads(base64.b64decode(gh(["api", f"repos/{repo}/contents/state.json?ref=data"])["content"]))
    age = (now - parse(st["last_poll"])).total_seconds() / 60
    active = []
    for status in ("in_progress", "queued"):
        for r in gh(["api", f"repos/{repo}/actions/workflows/watch.yml/runs?status={status}&per_page=20"]).get("workflow_runs", []):
            active.append({"id": r["id"], "status": status, "started": r.get("run_started_at") or r["created_at"]})
    recent = gh(["api", f"repos/{repo}/actions/workflows/watch.yml/runs?per_page=30"]).get("workflow_runs", [])
    failures = [r["id"] for r in recent if r.get("conclusion") in ("failure", "startup_failure")
                and now - parse(r["created_at"]) < timedelta(minutes=60)]
    out = {"last_check_hkt": parse(st["last_poll"]).astimezone(HKT).strftime("%Y-%m-%d %H:%M"),
           "last_check_age_min": round(age, 1), "active_runs": active, "failures_last_60min": failures}
    if active:
        newest = max(parse(a["started"]) for a in active)
        if age <= STALE_MIN:
            out.update(verdict="OK", action="none")
        elif now - newest < timedelta(minutes=15):
            out.update(verdict="STARTING", action="none")
        else:
            out.update(verdict="STUCK", action="alert: active run publishes nothing; cancel it and start a new one")
    elif len(failures) >= 3:
        out.update(verdict="BACKOFF", action="alert: GitHub Actions failing; check githubstatus.com, retry later")
    else:
        out.update(verdict="DOWN", action="start watcher")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="ryancwho/duo-watch")
    ap.add_argument("--act", action="store_true", help="start a watcher run when DOWN")
    a = ap.parse_args()
    try:
        out = check(a.repo)
    except Exception as e:
        out = {"verdict": "UNKNOWN", "action": "retry next check", "error": str(e)}
    if a.act and out["verdict"] == "DOWN":
        r = subprocess.run(["gh", "workflow", "run", "watch.yml", "--repo", a.repo, "-f", "loop_minutes=340"],
                           capture_output=True, text=True, timeout=60)
        out["action"] = "started watcher" if r.returncode == 0 else f"start failed: {r.stderr.strip()[:200]}"
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
