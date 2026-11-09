# LD — Listener maintenance board

Status: OPS LIVE (watchdog + handover on main). T1 open. Cursor work waits until the Mac mini is online.
Dispatch issue: see DIRECTOR_BRIEF.md § 1.

| Ticket | Title | Depends | Status |
|---|---|---|---|
| T1 | Unit tests for `scripts/health.py` verdicts | – | open |

New maintenance tickets are written by the CEO (Perplexity) at the owner's request. The director may
propose one on the issue as `PROPOSE` (problem, evidence, suggested fix); it becomes a ticket only
when it lands here.

## T1 — Unit tests for health verdicts

Outcome: `scripts/health.py` verdict logic is covered by offline tests with synthetic API replies.

Files: `scripts/health.py` (refactor only: split `check()` into a pure `decide(now, last_poll,
active_runs, recent_runs)` plus the API fetch; behaviour unchanged), `tests/test_health.py` (new),
`CHANGELOG.md`.

Non-goals: no threshold changes, no new verdicts, no network in tests.

Acceptance (all times UTC, now = 2026-12-01T04:00:00Z):
- S1 OK: one in_progress run started 03:00, last_poll 11:55 HKT (5 min old) → OK.
- S2 STARTING: run started 03:50, last_poll 11:20 HKT (40 min) → STARTING.
- S3 STUCK: run started 01:00, last_poll 11:20 HKT → STUCK.
- S4 DOWN: no active runs, 1 failure at 03:30 → DOWN.
- S5 BACKOFF: no active runs, failures at 03:10, 03:30, 03:50 → BACKOFF.
- S6 old failures ignored: no active runs, 3 failures at 02:00–02:40 → DOWN.
- S7 ENDED: now = 2027-02-01T01:00:00Z → ENDED, regardless of other inputs.

Gate: `scripts/check.sh` (runs `pytest -q tests` once `tests/` exists).
CHANGELOG: "Offline tests for health verdicts (LD-T1)."

Implementation evidence:
- PR:
- check.sh tail:
