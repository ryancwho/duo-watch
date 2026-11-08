#!/usr/bin/env python3
"""iPhone Duo pickup-stock watcher for Apple Store Hong Kong.

Watch and alert only: never logs in, adds to bag or checks out.
Alerts go to ntfy (https://ntfy.sh) topic in env NTFY_TOPIC.
"""
import json, os, random, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
BASE = "https://www.apple.com/hk/shop"
BUY = "https://www.apple.com/hk/shop/buy-iphone/iphone-duo"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
MODELS = {
    "MK2D4ZA/A": "256GB Star White", "MK2E4ZA/A": "256GB Night Sky",
    "MK2F4ZA/A": "512GB Star White", "MK2G4ZA/A": "512GB Night Sky",
    "MK2H4ZA/A": "1TB Star White",   "MK2J4ZA/A": "1TB Night Sky",
    "MK2K4ZA/A": "2TB Star White",   "MK2L4ZA/A": "2TB Night Sky",
}
POSITIVE_CONTROL = "MG6K4ZA/A"  # iPhone 17 256GB White, normally in stock
TARGETS = [p.strip() for p in os.environ.get("TARGETS", ",".join(MODELS)).split(",") if p.strip()]
TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
STOP_DATE = os.environ.get("STOP_DATE", "2027-01-31")
LOOP_MINUTES = float(os.environ.get("LOOP_MINUTES", "0"))  # 0 = single check
STATE_FILE = os.environ.get("STATE_FILE", "state/state.json")
LOG_FILE = os.environ.get("LOG_FILE", "state/log.csv")


class Blocked(Exception):
    pass


def now():
    return datetime.now(HKT)


def get_json(path):
    req = urllib.request.Request(BASE + path, headers={
        "User-Agent": UA, "Referer": BUY,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-HK,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        raise Blocked(f"HTTP {e.code}")
    except Exception as e:  # network
        raise Blocked(f"network: {e}")
    try:
        return json.loads(body)
    except ValueError:
        raise Blocked(f"non-JSON reply (HTTP {status})")


def notify(title, msg, priority="default", tags="", click=BUY):
    print(f"[{now():%Y-%m-%d %H:%M:%S}] ALERT {title}: {msg}", flush=True)
    if not TOPIC:
        return
    req = urllib.request.Request(f"https://ntfy.sh/{TOPIC}", data=msg.encode(), headers={
        "Title": title.encode("utf-8").decode("latin-1", "ignore"),
        "Priority": priority, "Tags": tags, "Click": click})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print("ntfy failed:", e, flush=True)


def summary(parts):
    q = "&".join(f"parts.{i}={p}" for i, p in enumerate(parts))
    d = get_json(f"/sba/availability-message?{q}")
    out = {}
    for c in d["body"]["content"]:
        msgs = (c.get("deliveryMessage") or {}).get("deliveryOptionMessages") or [{}]
        out[c["partNumber"]] = {
            "count": int(c.get("partAvailableStoresCount") or 0),
            "any": bool(c.get("availableAtAnyStore")),
            "delivery": msgs[0].get("displayName", ""),
        }
    return out


ANCHORS = ["MK2D4ZA/A", "MK2L4ZA/A"]  # each query lists the OTHER in-stock models, so two anchors cover all 8


def pickup_hits(anchor):
    """{part: [store (quote)]} for in-stock models Apple lists as alternatives to `anchor`.
    The endpoint omits the queried part itself and shows up to ~3 alternatives per store."""
    d = get_json(f"/pickup-message-recommendations?mts.0=regular&location=Central&product={anchor}")
    hits = {}
    for s in d["body"]["PickupMessage"]["stores"]:
        for p, pa in (s.get("partsAvailability") or {}).items():
            if pa.get("pickupDisplay") == "available":
                q = ((pa.get("messageTypes") or {}).get("regular") or {}).get("storePickupQuote") or pa.get("pickupSearchQuote", "")
                hits.setdefault(p, []).append(f"{s['storeName']} ({q})")
    return hits


def duo_hits():
    hits = {}
    for a in ANCHORS:
        for p, where in pickup_hits(a).items():
            if p in MODELS:
                hits.setdefault(p, [])
                hits[p] += [w for w in where if w not in hits[p]]
    return hits


def ddate(text):
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def load_state():
    try:
        return json.load(open(STATE_FILE))
    except Exception:
        return {"parts": {}, "baseline": None, "last_heartbeat": None, "stats": {"cycles": 0, "errors": 0, "seen": []}}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    json.dump(st, open(STATE_FILE, "w"), indent=1)


def log(rows):
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
    new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a") as f:
        if new:
            f.write("time_hkt,part,model,store_count,stores,delivery,status\n")
        for r in rows:
            f.write(",".join('"%s"' % str(x).replace('"', "'") for x in r) + "\n")


def self_test():
    """Positive control: iPhone 17 alternatives should normally show stock somewhere."""
    pos = pickup_hits(POSITIVE_CONTROL)
    if pos:
        print(f"self-test ok: positive control lists {len(pos)} in-stock model(s)", flush=True)
    else:
        print("self-test WARNING: positive control shows no stock; parser may be stale", flush=True)
    return bool(pos)


def cycle(st, with_delivery):
    t = now()
    hits = duo_hits()
    s = summary(TARGETS) if with_delivery else {}
    rows = []
    for p in TARGETS:
        where_l = hits.get(p, [])
        info = s.get(p, {"delivery": ""})
        prev = st["parts"].get(p, {"in": False})
        name = MODELS.get(p, p)
        if where_l and not prev.get("in"):
            where = "; ".join(where_l)
            notify(f"iPhone Duo {name} IN STOCK",
                   f"{where}\n{t:%H:%M} HKT. Buy in the web browser if the app errors at payment. Limit 2; bring photo ID.",
                   priority="urgent", tags="rotating_light")
            st["parts"][p] = {"in": True, "since": t.isoformat()}
            st["stats"]["seen"].append(f"{t:%m-%d %H:%M} {name}: {where}")
        elif not where_l and prev.get("in"):
            mins = int((t - datetime.fromisoformat(prev["since"])).total_seconds() // 60)
            notify(f"iPhone Duo {name} gone", f"Back to zero after about {mins} min ({t:%H:%M} HKT).", priority="low")
            st["parts"][p] = {"in": False}
        d = ddate(info["delivery"])
        if d:
            if st["baseline"] is None:
                st["baseline"] = d
            elif d < st["baseline"]:
                notify("iPhone Duo delivery moved earlier",
                       f"{name}: delivery now {info['delivery']} (was {st['baseline']}). Supply may be improving.")
                st["baseline"] = d
        rows.append([f"{t:%Y-%m-%d %H:%M:%S}", p, name, len(where_l), " | ".join(where_l), info["delivery"], "ok"])
    log(rows)
    st["stats"]["cycles"] += 1
    return hits


def heartbeat(st):
    t = now()
    today = f"{t:%Y-%m-%d}"
    if t.hour >= 8 and st.get("last_heartbeat") != today:
        sts = st["stats"]
        seen = "; ".join(sts["seen"][-5:]) or "nothing"
        notify("Duo watch heartbeat",
               f"{sts['cycles']} checks, {sts['errors']} errors since last heartbeat. Seen: {seen}. Baseline delivery {st['baseline']}.",
               priority="min", tags="heartbeat")
        st["last_heartbeat"] = today
        st["stats"] = {"cycles": 0, "errors": 0, "seen": []}


def wait_seconds():
    h = now().hour + now().minute / 60
    base = 120 if 6.5 <= h < 23.5 else 600
    return max(60, base + random.uniform(-45, 45))


def main():
    if f"{now():%Y-%m-%d}" > STOP_DATE:
        print("Past STOP_DATE; exiting.")
        return
    st = load_state()
    if not self_test():
        notify("Duo watch self-test warning", "iPhone 17 positive control showed no stock. Watching anyway; check the log.", priority="low")
    deadline = time.time() + LOOP_MINUTES * 60
    fails, backoff, n = 0, 120, 0
    while True:
        try:
            hits = cycle(st, with_delivery=(n % 5 == 0))
            n += 1
            fails, backoff = 0, 120
            print(f"[{now():%H:%M:%S}] Duo in stock: " + (", ".join(f"{MODELS[p]}@{len(w)}" for p, w in hits.items()) or "none"), flush=True)
            heartbeat(st)
        except Blocked as e:
            fails += 1
            st["stats"]["errors"] += 1
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
        time.sleep(pause)


if __name__ == "__main__":
    main()
