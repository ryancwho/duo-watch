#!/usr/bin/env python3
"""Build REPORT.md (restock trend) from data/events.csv, data/polls.csv and data/state.json."""
import csv, json, os, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
FMT = "%Y-%m-%d %H:%M:%S"
WAVE_GAP_MIN = 10   # restocks starting within 10 min of each other count as one wave
CAPS = ["256GB", "512GB", "1TB", "2TB"]


def read(name):
    p = os.path.join(DATA, name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


def cap(model):
    return model.split()[0]


def main():
    events = read("events.csv")
    polls = read("polls.csv")
    try:
        state = json.load(open(os.path.join(DATA, "state.json")))
    except Exception:
        state = {}
    from monitor import MODELS  # same folder via PYTHONPATH
    ongoing = []
    for k, w in (state.get("open") or {}).items():
        part, store = k.split("|", 1)
        st = datetime.fromisoformat(w["start"]).replace(tzinfo=None)
        ls = datetime.fromisoformat(w["last_seen"]).replace(tzinfo=None)
        ongoing.append({"start_hkt": st.strftime(FMT), "end_hkt": "(still in stock)",
                        "minutes": str(max(1, round((ls - st).total_seconds() / 60))),
                        "part": part, "model": MODELS.get(part, part), "store": store, "note": "ongoing"})
    allev = sorted(events + ongoing, key=lambda r: r["start_hkt"])

    ok = [p for p in polls if p["status"] == "ok"]
    errs = len(polls) - len(ok)
    days_hour = defaultdict(set)   # hour -> set of dates with >=1 ok check (coverage)
    for p in ok:
        days_hour[p["time_hkt"][11:13]].add(p["time_hkt"][:10])
    gaps = []
    for a, b in zip(ok, ok[1:]):
        ta, tb = datetime.strptime(a["time_hkt"], FMT), datetime.strptime(b["time_hkt"], FMT)
        if tb - ta > timedelta(minutes=20):
            gaps.append((ta, tb))

    # waves
    waves, cur = [], []
    for e in allev:
        t = datetime.strptime(e["start_hkt"], FMT)
        if cur and t - datetime.strptime(cur[-1]["start_hkt"], FMT) > timedelta(minutes=WAVE_GAP_MIN):
            waves.append(cur); cur = []
        cur.append(e)
    if cur:
        waves.append(cur)

    L = []
    now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=8)
    L.append("# iPhone Duo restock trend — Apple Store Hong Kong\n")
    L.append(f"Updated {now:%Y-%m-%d %H:%M} HKT. All times HKT.\n")
    L.append("A **restock** here is one model becoming available for same-day pickup at one store, "
             "from first sighting until it disappears. A **wave** is a group of restocks starting within "
             f"{WAVE_GAP_MIN} minutes of each other. Apple does not publish unit quantities, so “how many” is counted in "
             "store × model slots, not phones.\n")

    L.append("## Coverage\n")
    if ok:
        L.append(f"- Checks: {len(ok)} successful, {errs} failed, from {ok[0]['time_hkt']} to {ok[-1]['time_hkt']}.")
        L.append("- Cadence: every ~2 min 06:30–23:30, every ~10 min overnight.")
        recent = [g for g in gaps if g[1] > now - timedelta(days=7)]
        L.append(f"- Monitoring gaps over 20 min in the last 7 days: {len(recent)}"
                 + ("" if not recent else " — " + "; ".join(f"{a:%m-%d %H:%M}→{b:%H:%M}" for a, b in recent[-10:])) + ".")
    else:
        L.append("- No checks recorded yet.")
    L.append("- Limitation: Apple's pickup list shows about three in-stock models per store per query; four queries per "
             "check reduce, but cannot rule out, missed models when a store has many models at once.\n")

    L.append("## Summary\n")
    L.append(f"- Restocks recorded: **{len(allev)}** in **{len(waves)}** waves"
             + (f"; {len(ongoing)} still in stock now." if ongoing else "."))
    if allev:
        mins = sorted(int(e["minutes"]) for e in allev)
        L.append(f"- Typical time in stock: median {mins[len(mins)//2]} min (range {mins[0]}–{mins[-1]}).")
    L.append("")

    L.append("## By hour of day\n")
    L.append("Restocks starting in each hour, by capacity. “Days watched” = days with at least one check in that hour.\n")
    L.append("| Hour | " + " | ".join(CAPS) + " | Total | Days watched | Per watched day |")
    L.append("|---|" + "---|" * (len(CAPS) + 3))
    byh = defaultdict(Counter)
    for e in allev:
        byh[e["start_hkt"][11:13]][cap(e["model"])] += 1
    for h in [f"{i:02d}" for i in range(24)]:
        tot = sum(byh[h].values())
        dw = len(days_hour.get(h, ()))
        rate = f"{tot/dw:.2f}" if dw else "–"
        bar = "█" * tot if tot <= 30 else "█" * 30 + "…"
        L.append(f"| {h}:00 | " + " | ".join(str(byh[h][c] or "") for c in CAPS) + f" | {tot} {bar} | {dw} | {rate} |")
    L.append("")

    L.append("## By store\n")
    L.append("| Store | Restocks | " + " | ".join(CAPS) + " | Median minutes in stock |")
    L.append("|---|---|" + "---|" * (len(CAPS) + 1))
    bys = defaultdict(list)
    for e in allev:
        bys[e["store"]].append(e)
    for s, es in sorted(bys.items(), key=lambda x: -len(x[1])):
        c = Counter(cap(e["model"]) for e in es)
        m = sorted(int(e["minutes"]) for e in es)
        L.append(f"| {s} | {len(es)} | " + " | ".join(str(c[k] or "") for k in CAPS) + f" | {m[len(m)//2]} |")
    L.append("")

    L.append("## By model\n")
    L.append("| Model | Restocks | Stores | Median minutes |")
    L.append("|---|---|---|---|")
    bym = defaultdict(list)
    for e in allev:
        bym[e["model"]].append(e)
    for mname in MODELS.values():
        es = bym.get(mname, [])
        if not es:
            L.append(f"| {mname} | 0 | | |"); continue
        m = sorted(int(e["minutes"]) for e in es)
        L.append(f"| {mname} | {len(es)} | {', '.join(sorted({e['store'] for e in es}))} | {m[len(m)//2]} |")
    L.append("")

    L.append("## By day\n")
    L.append("| Date | Waves | Restocks | " + " | ".join(CAPS) + " |")
    L.append("|---|---|---|" + "---|" * len(CAPS))
    byd = defaultdict(list)
    for e in allev:
        byd[e["start_hkt"][:10]].append(e)
    wd = Counter(w[0]["start_hkt"][:10] for w in waves)
    for d in sorted(byd, reverse=True):
        c = Counter(cap(e["model"]) for e in byd[d])
        L.append(f"| {d} | {wd[d]} | {len(byd[d])} | " + " | ".join(str(c[k] or "") for k in CAPS) + " |")
    L.append("")

    L.append("## Waves (newest first)\n")
    L.append("| Started | Slots | Stores | Models | Longest (min) |")
    L.append("|---|---|---|---|---|")
    for w in reversed(waves[-60:]):
        L.append(f"| {w[0]['start_hkt'][:16]} | {len(w)} | {', '.join(sorted({e['store'] for e in w}))} | "
                 f"{', '.join(sorted({e['model'] for e in w}))} | {max(int(e['minutes']) for e in w)} |")
    L.append("")

    L.append("## All restocks, last 7 days (newest first)\n")
    L.append("| Start | End | Minutes | Model | Store | Note |")
    L.append("|---|---|---|---|---|---|")
    cutoff = (now - timedelta(days=7)).strftime(FMT)
    for e in reversed([e for e in allev if e["start_hkt"] >= cutoff]):
        L.append(f"| {e['start_hkt'][:16]} | {e['end_hkt'][:16] if e['end_hkt'][0].isdigit() else e['end_hkt']} | "
                 f"{e['minutes']} | {e['model']} | {e['store']} | {e.get('note','')} |")
    L.append("\nRaw data: `events.csv` (one row per restock) and `polls.csv` (one row per check) on this branch.")
    open(os.path.join(DATA, "REPORT.md"), "w").write("\n".join(L) + "\n")
    print(f"REPORT.md: {len(allev)} restocks, {len(waves)} waves, {len(ok)} checks")


if __name__ == "__main__":
    main()
