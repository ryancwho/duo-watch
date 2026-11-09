# Changelog

- 2026-11-10 Watchdog workflow (hook on every watcher run end + every 20 min) restarts the listener if none is active; `scripts/health.py` health verdicts; repo rules, runbook and Listener Director brief.
- 2026-11-10 Verified handover: each run starts the next, waits until it is really running, retries for up to 18 min, alerts if it cannot.
- 2026-11-09 Report shows hours actually watched per clock hour and the cause of each gap.
- 2026-11-09 v2: all 8 models logged; alerts for 1TB/2TB both colours; ringing alert for 1TB Star White; live report on `data` branch.
