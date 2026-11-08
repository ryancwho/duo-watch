# duo-watch

Watches Apple Store Hong Kong in-store pickup stock for iPhone Duo and pushes an alert to the ntfy app. Watch and alert only: no login, no bag, no checkout.

- `monitor.py`: two pickup-recommendation queries per cycle (anchors MK2D4, MK2L4 cover all 8 models), delivery date every 5th cycle, 2-min cadence by day and 10-min overnight (HKT), backoff and a stop alert after 5 failures in a row.
- Secret `NTFY_TOPIC`: the ntfy topic to push to. Optional variable `TARGETS`: comma-separated part numbers (default all 8).
- Stops itself after 2027-01-31. To stop sooner: Actions → duo-watch → Disable workflow.
