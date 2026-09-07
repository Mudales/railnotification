#!/usr/bin/env python3
"""
Israel Railways (rail.co.il) timetable client — standard-library only.

A self-contained CLI that queries the public Israel Rail journey-planner API for
the next trains between two stations and prints structured JSON. Designed to be
called directly by a human OR shelled out to by any agent framework (Claude Code,
Hermes, etc.): no third-party deps (no requests / pytz), stable JSON on stdout,
diagnostics on stderr, and meaningful exit codes.

Station names/IDs for all ~68 Israel Rail stations come from the vendored
stations.py (see its header for source). Resolve a station by numeric ID, by
English name, or by Hebrew name — full or partial.

Usage:
    rail_query.py --from lod --to "kiryat gat"
    rail_query.py --from 5000 --to 4600 --date 2026-09-08 --time 08:30
    rail_query.py --from "tel aviv" --to haifa            # partial match resolves
    rail_query.py --from 5000 --to 7000 --raw             # full API response
    rail_query.py --find jerusalem                        # search stations
    rail_query.py --list-stations                         # dump id -> name table

Exit codes: 0 ok, 1 request/parse failure, 2 bad arguments/ambiguous station.
"""

import argparse
import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None

# Import the vendored station table sitting next to this script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from stations import STATIONS  # id(str) -> {Heb, Eng, Rus, Arb}
except ImportError:
    STATIONS = {}

# --- API constants (public journey-planner API used by www.rail.co.il) ---
API_BASE = "https://rail-api.rail.co.il/rjpa/api/v1"
ENDPOINT = "/timetable/searchTrain"
# Azure APIM subscription key the public site ships with (not a personal secret;
# every browser on rail.co.il sends it). Override with --api-key if it rotates.
DEFAULT_API_KEY = "5e64d66cf03f4547bcac5de2de06b566"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)


def _norm(s: str) -> str:
    """Lowercase; keep latin letters, digits and Hebrew; collapse the rest."""
    return re.sub(r"[^a-z0-9֐-׿]+", " ", s.lower()).strip()


def _build_index():
    """Map normalized English & Hebrew names -> station id (str)."""
    idx = {}
    for sid, names in STATIONS.items():
        for lang in ("Eng", "Heb"):
            n = _norm(names.get(lang, ""))
            if n:
                idx.setdefault(n, sid)
                idx.setdefault(n.replace(" ", ""), sid)  # e.g. "kiryatgat"
    return idx


_INDEX = _build_index()


def resolve_station(value: str) -> int:
    """Resolve numeric ID or English/Hebrew name (exact, then unique partial)."""
    v = value.strip()
    if v.isdigit():
        return int(v)  # allow any numeric id, even if not in the table

    n = _norm(v)
    if n in _INDEX:
        return int(_INDEX[n])
    if n.replace(" ", "") in _INDEX:
        return int(_INDEX[n.replace(" ", "")])

    # Unique partial match on English or Hebrew names
    hits = {
        sid
        for sid, names in STATIONS.items()
        if n and (n in _norm(names.get("Eng", "")) or n in _norm(names.get("Heb", "")))
    }
    if len(hits) == 1:
        return int(next(iter(hits)))
    if len(hits) > 1:
        opts = ", ".join(
            sorted(f"{STATIONS[s]['Eng']} ({s})" for s in hits)
        )
        raise ValueError(f"'{value}' is ambiguous; matches: {opts}")
    raise ValueError(
        f"Unknown station '{value}'. Use a numeric ID, an English/Hebrew name, "
        f"or run with --find to search."
    )


def now_israel():
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Jerusalem"))
    return datetime.utcnow() + timedelta(hours=3)  # fallback (IDT); DST-naive


def station_name(sid) -> str:
    return STATIONS.get(str(sid), {}).get("Eng", str(sid))


def build_payload(from_station: int, to_station: int, date: str, hour: str) -> dict:
    return {
        "methodName": "searchTrainLuzForDateTime",
        "fromStation": from_station,
        "toStation": to_station,
        "date": date,
        "hour": hour,
        "systemType": "2",
        "scheduleType": "ByDeparture",
        "languageId": "English",
        "requestLocation": '{"latitude":"0.0","longitude":"0.0"}',
        "requestIP": "0.0.0.0",
        "userAgent": USER_AGENT,
        "screenResolution": '{"height":800,"width":1280}',
        "searchFromFavorites": False,
    }


def call_api(payload: dict, api_key: str, timeout: int = 30) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.8",
        "Accept-Encoding": "gzip",  # stdlib can decompress gzip; avoid brotli
        "Content-Type": "application/json",
        "ocp-apim-subscription-key": api_key,
        "Origin": "https://www.rail.co.il",
        "Referer": "https://www.rail.co.il/",
        "DNT": "1",
    }
    req = urllib.request.Request(
        API_BASE + ENDPOINT, data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding", "").lower() == "gzip":
            raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def find_closest_trains(data: dict, target_time_str: str):
    """Latest train up to 15 min before target, plus the next two at/after it."""
    travels = data.get("result", {}).get("travels", [])
    if not travels:
        return []

    first_dep = travels[0].get("trains", [{}])[0].get("departureTime")
    if not first_dep or len(first_dep) < 10:
        return []
    date_part = first_dep[:10]
    target_dt = datetime.strptime(
        f"{date_part}T{target_time_str}:00", "%Y-%m-%dT%H:%M:%S"
    )

    trains = []
    for travel in travels:
        tlist = travel.get("trains")
        if not tlist:
            continue
        train = tlist[0]
        dep_str = train.get("departureTime")
        if not dep_str:
            continue
        try:
            dep_dt = datetime.fromisoformat(dep_str)
        except ValueError:
            continue
        pos = train.get("trainPosition")
        orig = train.get("orignStation")
        dest = train.get("destinationStation")
        trains.append(
            {
                "trainNumber": train.get("trainNumber"),
                "originStation": orig,
                "originStationName": station_name(orig),
                "destinationStation": dest,
                "destinationStationName": station_name(dest),
                "originPlatform": train.get("originPlatform"),
                "destPlatform": train.get("destPlatform"),
                "departureTime": dep_str,
                "arrivalTime": train.get("arrivalTime"),
                "freeSeats": train.get("freeSeats"),
                "crowded": train.get("crowded"),
                "handicap": train.get("handicap"),
                "delayMinutes": (pos or {}).get("calcDiffMinutes"),
                "_dep": dep_dt,
            }
        )

    window_start = target_dt - timedelta(minutes=15)
    before = sorted(
        [t for t in trains if window_start <= t["_dep"] < target_dt],
        key=lambda t: t["_dep"],
        reverse=True,
    )
    after = sorted(
        [t for t in trains if t["_dep"] >= target_dt], key=lambda t: t["_dep"]
    )

    closest = []
    if before:
        closest.append(before[0])
    closest.extend(after[: 3 - len(closest)])
    for t in closest:
        t.pop("_dep", None)
    return closest


def cmd_list_stations():
    for sid, names in sorted(STATIONS.items(), key=lambda kv: names_key(kv)):
        print(f"{sid}\t{names['Eng']}\t{names['Heb']}")


def names_key(kv):
    return kv[1].get("Eng", "")


def cmd_find(query: str):
    n = _norm(query)
    hits = [
        (sid, names)
        for sid, names in STATIONS.items()
        if n in _norm(names.get("Eng", "")) or n in _norm(names.get("Heb", ""))
    ]
    if not hits:
        print(f"No station matches '{query}'.", file=sys.stderr)
        return 1
    for sid, names in sorted(hits, key=lambda kv: kv[1]["Eng"]):
        print(f"{sid}\t{names['Eng']}\t{names['Heb']}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Query Israel Railways next trains.")
    p.add_argument("--from", dest="from_station", help="origin station: ID or name")
    p.add_argument("--to", dest="to_station", help="destination station: ID or name")
    p.add_argument("--date", help="YYYY-MM-DD (default: today, Asia/Jerusalem)")
    p.add_argument("--time", help="HH:MM (default: now, Asia/Jerusalem)")
    p.add_argument("--raw", action="store_true", help="print full API JSON response")
    p.add_argument("--api-key", default=DEFAULT_API_KEY, help="override subscription key")
    p.add_argument("--find", metavar="QUERY", help="search stations by name, then exit")
    p.add_argument("--list-stations", action="store_true", help="print all stations")
    args = p.parse_args(argv)

    if args.list_stations:
        cmd_list_stations()
        return 0
    if args.find is not None:
        return cmd_find(args.find)

    if not args.from_station or not args.to_station:
        p.error("--from and --to are required (or use --find / --list-stations)")

    try:
        from_id = resolve_station(args.from_station)
        to_id = resolve_station(args.to_station)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    now = now_israel()
    date = args.date or now.strftime("%Y-%m-%d")
    hour = args.time or now.strftime("%H:%M")

    payload = build_payload(from_id, to_id, date, hour)
    try:
        data = call_api(payload, args.api_key)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        print(f"error: HTTP {e.code} from rail API\n{detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"error: request failed: {e.reason}", file=sys.stderr)
        return 1
    except (json.JSONDecodeError, ValueError) as e:
        print(f"error: bad response: {e}", file=sys.stderr)
        return 1

    if args.raw:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    trains = find_closest_trains(data, hour)
    print(
        json.dumps(
            {
                "from": from_id,
                "fromName": station_name(from_id),
                "to": to_id,
                "toName": station_name(to_id),
                "date": date,
                "queryTime": hour,
                "count": len(trains),
                "trains": trains,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
