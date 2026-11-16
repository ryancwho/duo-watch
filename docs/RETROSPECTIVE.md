# Retrospective: iPhone Duo listener, 8–17 Nov 2026

Status: **STOPPED 2026-11-17 07:42 HKT** — goal reached. Workflows `duo-watch` and `watchdog` disabled,
last runs cancelled. Repo, `data` branch, ntfy channel and dispatch issue #1 kept for reuse.

## Outcome
Ryan bought an **iPhone Duo 1TB Star White (MK2H4ZA/A) at Apple Causeway Bay (R409, CWB)** on
**17 Nov 2026, around 07:40 HKT** (time of his report). The listener saw that Causeway Bay
posting from 07:35:20 HKT; the first ⭐🚨 ringing alert for 1TB Star White that morning went out at 07:17:44 HKT
(Canton Road posting).

## Time audit (HKT)

| Milestone | Time | Elapsed from channel setup |
|---|---|---|
| Request: check XHS restock claim, build monitor | 8 Nov 12:03 | – |
| Mac mini / Grok route offline; switch to GitHub Actions | 8 Nov 12:11 | – |
| Repo created; first check logged | 8 Nov 12:13 / 12:15 | – |
| **ntfy channel set up and test alerts delivered** | **8 Nov ~12:25** | 0 |
| v2: all models logged, alerts 1TB+, ringing for 1TB Star White | 9 Nov | ~1 d |
| Verified handover, watchdog, Listener Director brief | 10 Nov 08:30 | ~1 d 20 h |
| First alert-model posting (2TB Star White, Canton Road, 1-check flash) | 11 Nov 08:35 | ~2 d 20 h |
| 1TB + 2TB Star White flash at ifc mall (1 check) | 12 Nov 08:37 | ~3 d 20 h |
| First ⭐🚨 ring, 1TB Star White (Canton Road) | 17 Nov 07:17:44 | 8 d 18 h 53 min |
| 1TB Star White posting at Causeway Bay seen | 17 Nov 07:35:20 | 8 d 19 h 10 min |
| **Purchase at Causeway Bay (reported)** | **17 Nov ~07:40** | **≈ 8 d 19 h 15 min (≈ 211 h)** |
| Shutdown | 17 Nov 07:42 | – |

Alert to purchase: about 22 minutes from the first ring; about 5 minutes from the Causeway Bay posting.

## Coverage
- 4,524 checks: 4,521 ok, 3 failed (2 network timeouts, 1 HTTP 307). Apple never blocked the watcher.
- Gaps over 20 min, all on the GitHub side: 8 Nov 18:05–19:52 (107 min, hourly cron skipped);
  9 Nov 11:23–14:52 (209 min, cron never fired); 10 Nov 02:14–07:40 (326 min, GitHub Actions outage at
  handover); 12 Nov 04:44–05:33 (49 min, failed starts; Listener Director restarted it).
- 177 restock postings logged (batch sizes unknown), 76 waves.

## What worked
- GitHub Actions + ntfy, $0, independent of the home Mac mini.
- The ringing alert with an "I've seen it" (ack) button: the alert that led to the purchase.
- Logging every model, not just the targets: it showed that the target models appeared in early-morning
  flashes (11 Nov 08:35, 12 Nov 08:37, 17 Nov 07:17–07:39), most lasting a single check.
- Health verdicts in `scripts/health.py`, the GitHub watchdog and the Grok Listener Director
  (daily OPS lines, 12 Nov restart).

## What went wrong (fix before reuse)
1. **GitHub schedules are not a clock.** Hourly and 15-min crons skipped for hours. Use self-chaining
   runs and an outside check; treat cron only as a backup.
2. **A plain self-chain dies in an outage** (10 Nov). The fix — confirm the successor is really running,
   retry, alert — worked.
3. **The retry created a second chain** (16 Nov 19:25 onwards). A successor that took > 5 min to start was
   treated as lost; the retry started another; both ran and each started its own successors. Effects:
   duplicate rings (20 instead of 10), `git` merge conflicts in the runners' local data copies,
   `report.py` crashes, runs marked failed and two false "Duo watch stopped" alerts (17 Nov 06:45,
   07:06). The `data` branch itself stayed clean. **Fix before reuse:** before retrying, cancel the
   earlier dispatched run that is still queued; have a successor stand down if another run already took over
   from the same predecessor; give `health.py` a verdict for two active watchers (DUPLICATE).
4. **`workflow_run` is not sent for runs that another workflow started** (via GITHUB_TOKEN); the
   watcher must call the watchdog itself as its last step.
5. Report wording: count **restock postings**, never "units"; batch size is unknown.

## Reuse checklist (next product)
1. Find the product's part numbers from the Apple product page; update `MODELS`, `ANCHORS`, alert and
   ring targets; one store-list query per capacity anchor.
2. Fix item 3 above first (ticket), then `scripts/check.sh`.
3. Re-enable: Actions → `duo-watch` → Enable, `watchdog` → Enable; run `duo-watch` with loop 340.
4. Send `test-alert` → `listener` and `ring` and confirm on the phone.
5. Restart the Grok Listener Director schedule (issue #1).
