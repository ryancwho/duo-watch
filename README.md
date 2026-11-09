# duo-watch

Watches Apple Store Hong Kong same-day pickup stock for all 8 iPhone Duo models, records every restock, and pushes phone alerts (ntfy) only for the alert models. Watch and alert only: no login, no bag, no checkout.

- **Trend report:** [`REPORT.md` on the `data` branch](https://github.com/ryancwho/duo-watch/blob/data/REPORT.md), rebuilt within about a minute of any posting appearing or disappearing, and at least every 10 minutes: restocks by hour of day, store, model and day, plus restock waves.
- **Raw data (data branch):** `events.csv` one row per restock (model × store, start, end, minutes); `polls.csv` one row per check (coverage).
- **Phone alerts:** 1TB and 2TB, Star White and Night Sky (repo variable `ALERT_TARGETS`). 1TB Star White (`RING_TARGETS`) gets a ⭐🚨 alert repeated every 30 s, up to 10 times, until you tap "Got it - stop ringing" or the posting disappears.
- **Counts are restock postings, not phones:** batch size per posting is unknown.
- **Daily 08:00 HKT report notification:** yesterday's restock count, busiest hours, positive-control result.
- **Test:** Actions → test-alert → Run workflow → choose ring or listener.
- **Cadence:** ~2 min 06:30–23:30 HKT, ~10 min overnight; runs of about 5 h 40 min, each starting the next itself (a 30-minute schedule is only a backup). Stops after 2027-01-31, or Actions → duo-watch → Disable workflow.

| Part | Model |
|---|---|
| MK2D4ZA/A | 256GB Star White |
| MK2E4ZA/A | 256GB Night Sky |
| MK2F4ZA/A | 512GB Star White |
| MK2G4ZA/A | 512GB Night Sky |
| MK2H4ZA/A | 1TB Star White |
| MK2J4ZA/A | 1TB Night Sky |
| MK2K4ZA/A | 2TB Star White |
| MK2L4ZA/A | 2TB Night Sky |
