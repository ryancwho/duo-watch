# duo-watch

Watches Apple Store Hong Kong same-day pickup stock for all 8 iPhone Duo models, records every restock, and pushes phone alerts (ntfy) only for the alert models. Watch and alert only: no login, no bag, no checkout.

- **Trend report:** [`REPORT.md` on the `data` branch](https://github.com/ryancwho/duo-watch/blob/data/REPORT.md), refreshed after every run (about hourly): restocks by hour of day, store, model and day, plus restock waves.
- **Raw data (data branch):** `events.csv` one row per restock (model × store, start, end, minutes); `polls.csv` one row per check (coverage).
- **Phone alerts:** default 1TB and 2TB, Star White and Night Sky. Change with repo variable `ALERT_TARGETS` (comma-separated part numbers).
- **Daily 08:00 HKT report notification:** yesterday's restock count, busiest hours, positive-control result.
- **Test:** Actions → test-alert → Run workflow.
- **Cadence:** ~2 min 06:30–23:30 HKT, ~10 min overnight; runs of 55 min chained by a 15-minute schedule. Stops after 2027-01-31, or Actions → duo-watch → Disable workflow.

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
