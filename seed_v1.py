"""One-off: convert v1 per-check logs (white 512GB+ only) into v2 events.csv / polls.csv."""
import csv, glob, json, os, sys
from datetime import datetime, timedelta
from monitor import MODELS
out = sys.argv[1]
rows = {}
for f in glob.glob(sys.argv[2] + "/*/log.csv"):
    for r in csv.DictReader(open(f)):
        rows[(r["time_hkt"][:16], r["part"])] = r          # dedupe across cumulative logs
by_t = {}
for (t, p), r in rows.items():
    by_t.setdefault(t, []).append(r)
times = sorted(by_t)
os.makedirs(out, exist_ok=True)
FMT = "%Y-%m-%d %H:%M"
with open(f"{out}/polls.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["time_hkt", "status", "n_in_stock", "in_stock", "delivery"])
    for t in times:
        pairs = [(r["model"], s.split(" (")[0]) for r in by_t[t] for s in r["stores"].split(" | ") if s]
        w.writerow([t + ":00", "ok", len(pairs), "; ".join(f"{m} @ {s}" for m, s in pairs), ""])
openw, events = {}, []
for i, t in enumerate(times):
    seen = {(r["part"], s.split(" (")[0]) for r in by_t[t] for s in r["stores"].split(" | ") if s}
    for k in seen:
        openw.setdefault(k, {"start": t, "last": t, "absent": 0}).update(last=t, absent=0)
    for k in list(openw):
        if k not in seen:
            openw[k]["absent"] += 1
            if openw[k]["absent"] >= 2:
                events.append((k, openw.pop(k)))
for k, v in openw.items():
    events.append((k, v))
with open(f"{out}/events.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["start_hkt", "end_hkt", "minutes", "part", "model", "store", "note"])
    for (p, s), v in sorted(events, key=lambda e: e[1]["start"]):
        a, b = datetime.strptime(v["start"], FMT), datetime.strptime(v["last"], FMT)
        w.writerow([v["start"] + ":00", v["last"] + ":00", max(1, round((b - a).total_seconds() / 60)), p, MODELS[p], s,
                    "v1 log (only Star White 512GB/1TB/2TB watched)"])
print(len(times), "checks,", len(events), "restocks from v1 logs; first", times[0], "last", times[-1])
