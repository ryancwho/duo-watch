# Listener operations runbook

The listener is a chain of GitHub Actions runs (`watch.yml`, ~5 h 40 min each). Each run starts its
successor about 10 minutes before it ends and only stops once the successor is running.

## Safety nets (in order)
1. **In-run handover**: retries up to 18 min; phone alert "Duo watch: handover failing" if it cannot.
2. **GitHub watchdog** (`watchdog.yml`): fires when any watcher run ends, and at :07/:27/:47 each
   hour; starts a watcher if none is active; phone alert on STUCK/BACKOFF or a failed start.
3. **Backup schedule** in `watch.yml` (every 30 min): a run that finds no watcher takes over;
   otherwise it stands down in seconds.
4. **Listener Director (Grok Bot)**: independent check from outside GitHub's scheduler (below).
   Works only while the Mac mini host is online.

All four share one failure they cannot fix: a long GitHub Actions outage. Then the right action is
to wait and retry, not to hammer.

## Health check
```
python3 scripts/health.py --repo ryancwho/duo-watch          # read-only verdict
python3 scripts/health.py --repo ryancwho/duo-watch --act    # also starts a watcher if DOWN
```
Without the script, the same check by API (token with Actions: read/write, Contents: read):
1. `GET /repos/ryancwho/duo-watch/contents/state.json?ref=data` → base64 → `last_poll` (ISO, HKT).
2. `GET /repos/ryancwho/duo-watch/actions/workflows/watch.yml/runs?status=in_progress` and `?status=queued`.
3. `GET /repos/ryancwho/duo-watch/actions/workflows/watch.yml/runs?per_page=30` → failures in last 60 min.

| Verdict | Meaning | Action |
|---|---|---|
| OK | watcher active, last check ≤ 25 min old | nothing |
| STARTING | watcher active < 15 min, data stale | nothing; re-check in 15 min |
| STUCK | watcher active > 15 min, no check for > 25 min | cancel that run, then start one (below) |
| DOWN | no watcher queued/running | start one (below), unless the watchdog already did in the last 10 min |
| BACKOFF | DOWN and ≥ 3 watcher runs failed in 60 min | check githubstatus.com; retry every 30 min; tell owner once |
| UNKNOWN | API error | retry next check |
| ENDED | after 2027-01-31 | nothing |

Start a watcher: `gh workflow run watch.yml -R ryancwho/duo-watch -f loop_minutes=340`
(API: `POST /repos/ryancwho/duo-watch/actions/workflows/watch.yml/dispatches` with
`{"ref":"main","inputs":{"loop_minutes":"340"}}`). A start while another watcher is active is
harmless: the new run stands down.

## Apple refusing requests (different from GitHub downtime)
Signs: `polls.csv` rows with `error:`; phone alert "Duo watch stopped … 5 failures in a row"; the
last run's conclusion `failure` after hours of running. Restart at most once; if it stops again
within 2 hours, do not restart — escalate to the owner. Never change endpoints or rate to evade.

## Verify after merge (monitor.py or workflow changes)
1. Next watcher run's log shows "Took over from run …" or "this run takes over".
2. Data branch commits continue every ≤ 10 min.
3. One full handover observed: the old run logs "next run … is running; handing over", and the gap in
   `polls.csv` across it is under 5 minutes.

## Test the phone path
Actions → test-alert → Run workflow → `ring` (star alert, repeats until "Got it") or `listener`.
Do not run `ring` without the owner's request (it rings their phone).
