# duo-watch repository rules (binding on every bot and every Cursor chat)

Purpose: watch Apple Store Hong Kong same-day pickup stock for iPhone Duo, log every restock posting,
alert the owner's phone (ntfy). Watch and alert only.

## Never
- Never add login, add-to-bag, reservation, checkout or any purchase step.
- Never increase the check rate (daytime ~120 s ± 45 s, overnight ~600 s) or add Apple endpoints,
  proxies or header tricks to get round a block. If Apple refuses requests, stop and escalate.
- Never print, commit or post the ntfy topic (secret `NTFY_TOPIC`). The repo is public.
- Never rewrite `data` branch history, delete data files, or force-push any branch.
- Never change `ALERT_TARGETS`, `RING_TARGETS`, `STOP_DATE`, repo visibility or secrets without
  the owner's written ruling on the dispatch issue.
- Never commit straight to `main` except docs-only commits by the CEO (Perplexity).
- Never run two watchers on purpose. Never cancel a healthy run.

## Done means
`scripts/check.sh` passes. Never weaken, skip or delete a check to go green.

## Change rules
- One ticket per Cursor chat and per PR. Branch `ld/<ticket>` from latest `main`.
- Merge `main` into the branch (never rebase); merge commit, no squash.
- Every PR: the ticket's tests, a line in `CHANGELOG.md`, the ticket's evidence block filled.
- `monitor.py` changes go live at the next watcher run (runs last ~5 h 40 min). A PR that changes
  `monitor.py` or a workflow is not proven until one full handover after merge has been observed
  (see docs/OPERATIONS.md § Verify after merge).
- `report.py` changes go live within 10 minutes (the running watcher pulls `main` before each publish).

## Protected (edit only under a ticket that names them)
`monitor.py` alert/ring logic and models, `.github/workflows/*.yml`, `scripts/health.py`.
