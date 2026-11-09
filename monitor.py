#!/usr/bin/env python3
"""iPhone Duo pickup-stock watcher for Apple Store Hong Kong (v2).

- Records every iPhone Duo model's in-store pickup availability (data collection).
- Pushes phone alerts (ntfy) only for ALERT_TARGETS (default: 1TB and 2TB, both colours).
- Watch and alert only: never logs in, adds to bag or checks out.

Files in DATA_DIR (committed to the `data` branch by the workflow):
  state.json   open restock windows, alert state, baseline delivery date
  events.csv   one row per closed restock window: model x store, start, end, minutes
  polls.csv    one row per check (coverage + what was in stock)
"""
import csv, json, os, random, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
BASE = "https://www.apple.com/hk/shop"
BUY = "https://www.apple.com/hk/shop/buy-iphone/iphone-duo"
REPORT_URL = "https://github.com/ryancwho/duo-watch/blob/data/REPORT.md"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
MODELS = {
    "MK2D4ZA/A": "256GB Star White", "MK2E4ZA/A": "256GB Night Sky",
    "MK2F4ZA/A": "512GB Star White", "MK2G4ZA/A": "512GB Night Sky",
    "MK2H4ZA/A": "1TB Star White",   "MK2J4ZA/A": "1TB Night Sky",
    "MK2K4ZA/A": "2TB Star White",   "MK2L4ZA/A": "2TB Night Sky",
}
# The pickup endpoint omits the queried model and lists ~3 in-stock alternatives per store,
# so query one anchor per capacity to see as many models as possible.
ANCHORS = ["MK2D4ZA/A", "MK2G4ZA/A", "MK2H4ZA/A", "MK2L4ZA/A"]
POSITIVE_CONTROL = "MG6J4ZA/A"  # iPhone 17; its alternatives are normally in stock somewhere
DEFAULT_ALERT = "MK2H4ZA/A,MK2J4ZA/A,MK2K4ZA/A,MK2L4ZA/A"
ALERT = [p.strip() for p in (os.environ.get("ALERT_TARGETS") or DEFAULT_ALERT).split(",") if p.strip() in MODELS]
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
STOP_DATE = os.environ.get("STOP_DATE", "2027-01-31")
LOOP_MINUTES = float(os.environ.get("LOOP_MINUTES") or "0")
DATA = os.environ.get("DATA_DIR", "data")
STATE_FILE, EVENTS, POLLS = (os.path.join(DATA, f) for f in ("state.json", "events.csv", "polls.csv"))
ABSENT_TO_CLOSE = 2      # consecutive absent checks before a window is closed (absorbs list flicker)
GAP_MINUTES = 15         # if the last check is older than this, open windows are closed at the last check


class Blocked(Exception):
    pass


def now():
    return datetime.now(HKT)


def ts(t):
    return t.strftime("%Y-%m-%d %H:%M:%S")


def get_json(path):
    req = urllib.request.Request(BASE + path, headers={
        "User-Agent": UA, "Referer": BUY,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-HK,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body, status = r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        raise Blocked(f"HTTP {e.code}")
    except Exception as e:
        raise Blocked(f"network: {e}")
    try:
        return json.loads(body)
    except ValueError:
        raise Blocked(f"non-JSON reply (HTTP {status})")


PRIO = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5, "max": 5}


def notify(title, msg, priority="default", tags="", click=BUY, actions=None):
    print(f"[{ts(now())}] ALERT {title}: {msg}", flush=True)
    if not TOPIC:
        return
    body = {"topic": TOPIC, "title": title, "message": msg, "priority": PRIO.get(priority, 3),
            "tags": [t for t in tags.split(",") if t], "click": click}
    if actions:
        body["actions"] = actions
    req = urllib.request.Request("https://ntfy.sh", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print("ntfy failed:", e, flush=True)


# ---------- ringing (repeat until acknowledged) ----------
RING = [p.strip() for p in (os.environ.get("RING_TARGETS") or "MK2H4ZA/A").split(",") if p.strip()]
RING_EVERY_S = int(os.environ.get("RING_EVERY_S") or "30")
RING_MAX = int(os.environ.get("RING_MAX") or "10")      # 10 x 30 s = 5 minutes
ACK_TOPIC = f"{TOPIC}-ack" if TOPIC else ""


def star_title(part):
    return f"\u2b50\U0001f6a8 iPhone Duo {MODELS.get(part, part)} IN STOCK"


def ack_action():
    return [{"action": "http", "label": "Got it - stop ringing", "url": f"https://ntfy.sh/{ACK_TOPIC}",
             "method": "POST", "body": "ack", "clear": False},
            {"action": "view", "label": "Open Apple Store", "url": BUY}]


def acked_since(unix):
    if not ACK_TOPIC:
        return False
    try:
        with urllib.request.urlopen(f"https://ntfy.sh/{ACK_TOPIC}/json?poll=1&since={int(unix)}", timeout=15) as r:
            return any(json.loads(l).get("event") == "message" for l in r.read().decode().splitlines() if l.strip())
    except Exception:
        return False


def start_ring(st, part, where, label=""):
    st["ring"] = {"part": part, "where": where, "since": time.time(), "count": 1,
                  "next": time.time() + RING_EVERY_S, "label": label}
    notify(star_title(part), f"{label}{where}\n{now():%H:%M} HKT. Tap 'Got it' to stop the repeats. "
           f"Buy in the web browser if the app errors at payment. Limit 2; bring photo ID.",
           priority="urgent", actions=ack_action())


def ring_tick(st, still_in_stock=None):
    r = st.get("ring")
    if not r:
        return
    stop = None
    if acked_since(r["since"]):
        stop = "acknowledged"
    elif still_in_stock is not None and not still_in_stock(r["part"]):
        stop = "stock gone"
    elif r["count"] >= RING_MAX:
        stop = f"{RING_MAX} rings sent"
    if stop:
        print(f"[{ts(now())}] ring stopped: {stop}", flush=True)
        st["ring"] = None
        return
    if time.time() >= r["next"]:
        r["count"] += 1
        r["next"] = time.time() + RING_EVERY_S
        notify(star_title(r["part"]), f"{r.get('label','')}Repeat {r['count']}/{RING_MAX}: {r['where']}. Tap 'Got it' to stop.",
               priority="urgent", actions=ack_action())


def pickup_hits(anchor):
    """{part: {store: quote}} for in-stock alternatives Apple lists for `anchor`."""
    d = get_json(f"/pickup-message-recommendations?mts.0=regular&location=Central&product={anchor}")
    hits = {}
    for s in d["body"]["PickupMessage"]["stores"]:
        for p, pa in (s.get("partsAvailability") or {}).items():
            if pa.get("pickupDisplay") == "available":
                q = ((pa.get("messageTypes") or {}).get("regular") or {}).get("storePickupQuote") or pa.get("pickupSearchQuote", "")
                hits.setdefault(p, {})[s["storeName"]] = q
    return hits


def duo_hits():
    hits = {}
    for a in ANCHORS:
        for p, stores in pickup_hits(a).items():
            if p in MODELS:
                hits.setdefault(p, {}).update(stores)
    return hits


def delivery_date():
    q = "&".join(f"parts.{i}={p}" for i, p in enumerate(ALERT or MODELS))
    d = get_json(f"/sba/availability-message?{q}")
    for c in (d.get("body") or {}).get("content") or []:
        msgs = (c.get("deliveryMessage") or {}).get("deliveryOptionMessages") or [{}]
        m = re.search(r"(\d{2})/(\d{2})/(\d{4})", msgs[0].get("displayName", ""))
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


# ---------- persistence ----------
def load_state():
    try:
        st = json.load(open(STATE_FILE))
    except Exception:
        st = {}
    st.setdefault("open", {})            # "part|store" -> {"start":..., "last_seen":..., "absent":0}
    st.setdefault("alerted", [])         # alert parts currently announced as in stock
    st.setdefault("baseline", None)
    st.setdefault("last_poll", None)
    st.setdefault("last_heartbeat", None)
    st.setdefault("stats", {"cycles": 0, "errors": 0})
    st.setdefault("ring", None)
    return st


def save_state(st):
    os.makedirs(DATA, exist_ok=True)
    json.dump(st, open(STATE_FILE, "w"), indent=1, sort_keys=True)


def append_csv(path, header, row):
    os.makedirs(DATA, exist_ok=True)
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerow(row)


def close_window(key, w, end, note=""):
    part, store = key.split("|", 1)
    start = datetime.fromisoformat(w["start"])
    endt = datetime.fromisoformat(end)
    mins = max(1, round((endt - start).total_seconds() / 60))
    append_csv(EVENTS, ["start_hkt", "end_hkt", "minutes", "part", "model", "store", "note"],
               [ts(start), ts(endt), mins, part, MODELS.get(part, part), store, note])


def close_after_gap(st):
    """If we were offline for a while, end open windows at the last check we made."""
    if not st["last_poll"] or not st["open"]:
        return
    last = datetime.fromisoformat(st["last_poll"])
    if (now() - last) > timedelta(minutes=GAP_MINUTES):
        for k, w in list(st["open"].items()):
            close_window(k, w, w["last_seen"], "ended during a monitoring gap")
            del st["open"][k]
        st["alerted"] = []


# ---------- one check ----------
def cycle(st, with_delivery):
    t = now()
    hits = duo_hits()
    seen_keys = {f"{p}|{s}" for p, stores in hits.items() for s in stores}

    # open new windows
    for k in seen_keys:
        if k in st["open"]:
            st["open"][k].update(last_seen=t.isoformat(), absent=0)
        else:
            st["open"][k] = {"start": t.isoformat(), "last_seen": t.isoformat(), "absent": 0}
    # close windows absent for ABSENT_TO_CLOSE checks
    for k, w in list(st["open"].items()):
        if k not in seen_keys:
            w["absent"] = w.get("absent", 0) + 1
            if w["absent"] >= ABSENT_TO_CLOSE:
                close_window(k, w, w["last_seen"])
                del st["open"][k]

    # phone alerts for ALERT models only (RING models get the star alert that repeats until acknowledged)
    for p in ALERT:
        name = MODELS[p]
        if p in hits and p not in st["alerted"]:
            where = "; ".join(f"{s} ({q})" for s, q in sorted(hits[p].items()))
            if p in RING:
                start_ring(st, p, where)
            else:
                notify(f"\U0001f6a8 iPhone Duo {name} IN STOCK",
                       f"{where}\n{t:%H:%M} HKT. Buy in the web browser if the app errors at payment. Limit 2; bring photo ID.",
                       priority="urgent")
            st["alerted"].append(p)
        elif p in st["alerted"] and not any(k.startswith(p + "|") for k in st["open"]):
            notify(f"iPhone Duo {name} gone", f"No store lists it any more ({t:%H:%M} HKT).", priority="low")
            st["alerted"].remove(p)

    delivery = ""
    if with_delivery:
        d = delivery_date()
        if d:
            delivery = d
            if st["baseline"] is None:
                st["baseline"] = d
            elif d < st["baseline"]:
                notify("iPhone Duo delivery moved earlier",
                       f"Online delivery for your models is now {d} (was {st['baseline']}). Supply may be improving.")
                st["baseline"] = d

    pairs = "; ".join(f"{MODELS[p]} @ {s}" for p in sorted(hits) for s in sorted(hits[p]))
    append_csv(POLLS, ["time_hkt", "status", "n_in_stock", "in_stock", "delivery"],
               [ts(t), "ok", len(seen_keys), pairs, delivery])
    st["last_poll"] = t.isoformat()
    st["stats"]["cycles"] += 1
    return hits


PUBLISH = os.environ.get("PUBLISH") == "1"
PUBLISH_EVERY_S = 600


def publish(st, reason):
    """Rebuild REPORT.md and push the data branch (workflow sets PUBLISH=1)."""
    if not PUBLISH:
        return
    import subprocess
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        # pick up report-format changes from main without restarting the watcher
        subprocess.run(f'git -C "{here}" pull -q --ff-only origin main', shell=True, timeout=60)
        subprocess.run([sys.executable, os.path.join(here, "report.py"), DATA], check=True,
                       env={**os.environ, "PYTHONPATH": here}, timeout=60)
        cmd = (f'cd "{DATA}" && git add -A && (git diff --cached --quiet || (git commit -qm "data {now():%Y-%m-%d %H:%M} HKT ({reason})" '
               f'&& (git push -q origin HEAD:data || (git pull -q --rebase origin data && git push -q origin HEAD:data))))')
        subprocess.run(cmd, shell=True, timeout=90)
    except Exception as e:
        print("publish failed:", e, flush=True)
    st["last_publish"] = time.time()


def yesterday_summary():
    y = (now() - timedelta(days=1)).strftime("%Y-%m-%d")
    rows = []
    if os.path.exists(EVENTS):
        rows = [r for r in csv.DictReader(open(EVENTS)) if r["start_hkt"].startswith(y)]
    if not rows:
        return f"Yesterday ({y}): no restock postings recorded."
    by_model, by_hour = {}, {}
    for r in rows:
        by_model[r["model"]] = by_model.get(r["model"], 0) + 1
        h = r["start_hkt"][11:13]
        by_hour[h] = by_hour.get(h, 0) + 1
    top_h = sorted(by_hour.items(), key=lambda x: -x[1])[:3]
    return (f"Yesterday ({y}): {len(rows)} restock postings (batch sizes unknown). "
            + ", ".join(f"{m} x{n}" for m, n in sorted(by_model.items()))
            + ". Busiest hours: " + ", ".join(f"{h}:00 ({n})" for h, n in top_h) + ".")


def heartbeat(st):
    t = now()
    today = f"{t:%Y-%m-%d}"
    if t.hour >= 8 and st.get("last_heartbeat") != today:
        try:
            pc = "Positive control OK." if pickup_hits(POSITIVE_CONTROL) else "Positive control saw NO stock - check."
        except Blocked as e:
            pc = f"Positive control failed ({e})."
        s = st["stats"]
        notify("Duo watch daily report",
               f"{yesterday_summary()} {s['cycles']} checks, {s['errors']} errors since last report. {pc} Full report: {REPORT_URL}",
               priority="min", tags="bar_chart", click=REPORT_URL)
        st["last_heartbeat"] = today
        st["stats"] = {"cycles": 0, "errors": 0}


def self_test():
    ok = bool(pickup_hits(POSITIVE_CONTROL))
    print("self-test", "ok" if ok else "WARNING: positive control shows no stock", flush=True)
    return ok


def positive_test():
    """End-to-end proof: Apple endpoint -> parser -> ntfy (used by the test-alert workflow)."""
    hits = {}
    for a in ["MG6J4ZA/A", "MG6P4ZA/A"]:
        for p, stores in pickup_hits(a).items():
            hits.setdefault(p, {}).update(stores)
    if hits:
        p, stores = sorted(hits.items())[0]
        notify("TEST: Apple listener works",
               f"Read live Apple HK pickup data: iPhone 17 {p} in stock at {'; '.join(sorted(stores))}. "
               f"{len(hits)} iPhone 17 model(s) seen. Phone alerts are set for: {', '.join(MODELS[p] for p in ALERT)}.",
               priority="high", tags="white_check_mark")
    else:
        notify("TEST: listener saw no stock",
               "Apple answered, but no iPhone 17 pickup stock was listed. Rerun later.", priority="high", tags="warning")
    print("Duo now:", {MODELS[k]: sorted(v) for k, v in duo_hits().items()} or "none", flush=True)


def wait_seconds():
    t = now()
    h = t.hour + t.minute / 60
    base = 120 if 6.5 <= h < 23.5 else 600
    return max(60, base + random.uniform(-45, 45))


def main():
    if f"{now():%Y-%m-%d}" > STOP_DATE:
        print("Past STOP_DATE; exiting.")
        return
    st = load_state()
    close_after_gap(st)
    if not self_test():
        notify("Duo watch self-test warning", "iPhone 17 positive control showed no stock. Watching anyway.", priority="low")
    deadline = time.time() + LOOP_MINUTES * 60
    fails, backoff, n = 0, 120, 0
    while True:
        try:
            before = set(st["open"])
            hits = cycle(st, with_delivery=(n % 5 == 0))
            n += 1
            changed = set(st["open"]) != before
            if changed or time.time() - st.get("last_publish", 0) >= PUBLISH_EVERY_S:
                save_state(st)
                publish(st, "change" if changed else "periodic")
            fails, backoff = 0, 120
            print(f"[{now():%H:%M:%S}] in stock: " + ("; ".join(f"{MODELS[p]}@{len(s)}" for p, s in hits.items()) or "none"), flush=True)
            heartbeat(st)
        except Blocked as e:
            fails += 1
            st["stats"]["errors"] += 1
            append_csv(POLLS, ["time_hkt", "status", "n_in_stock", "in_stock", "delivery"], [ts(now()), f"error: {e}", "", "", ""])
            print(f"[{now():%H:%M:%S}] blocked/failed ({fails}): {e}", flush=True)
            if fails >= 5:
                notify("Duo watch stopped", f"5 failures in a row ({e}). Apple may be blocking GitHub's servers. Not retrying.", priority="high")
                save_state(st)
                sys.exit(1)
        save_state(st)
        if time.time() >= deadline:
            break
        pause = wait_seconds() if fails == 0 else min(backoff := backoff * 2, 1800)
        if time.time() + pause >= deadline:
            break
        end = time.time() + pause
        while time.time() < end:
            ring_tick(st, still_in_stock=lambda p: p in st["alerted"])
            time.sleep(min(15, max(0, end - time.time())))


def ring_test():
    """Send the real star alert (labelled TEST) and repeat it until 'Got it' is tapped (max RING_MAX)."""
    st = {"ring": None}
    start_ring(st, "MK2H4ZA/A", "ifc mall (example only)", label="TEST - not real stock. ")
    while st.get("ring"):
        time.sleep(5)
        ring_tick(st)
    print("ring test finished", flush=True)


if __name__ == "__main__":
    if os.environ.get("TEST_RING") == "1":
        ring_test()
    elif os.environ.get("TEST_POSITIVE") == "1":
        positive_test()
    else:
        main()
