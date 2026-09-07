---
name: rail-api
description: >-
  Query Israel Railways (rail.co.il) train schedules — next departures, arrival
  times, platform numbers, and live delay info between any two of the ~68 Israel
  Rail stations. Use whenever someone asks about Israel train times, when the next
  train is, or rail schedules between stations (Lod, Kiryat Gat, Tel Aviv, Haifa,
  Jerusalem, Be'er Sheva, etc.). Stations resolve by numeric ID or by English/Hebrew
  name. Also the reference for the railnotification bot on the 192.168.0.123 server.
---

# Israel Railways (rail.co.il) API

Fetch upcoming trains between any two Israel Railways stations via the public
journey-planner API that powers www.rail.co.il.

The core is `rail_query.py` — a **standalone, dependency-free CLI** (Python 3.9+,
standard library only). It prints structured JSON on stdout and diagnostics on
stderr, so it's usable directly, from this skill, or shelled out to by any other
agent/framework (see "Using from any agent" below).

## Quick start

```bash
python3 "$CLAUDE_SKILL_DIR/rail_query.py" --from lod --to "kiryat gat"
```

If `$CLAUDE_SKILL_DIR` isn't set, use the script's directory directly (e.g.
`~/.claude/skills/rail-api/rail_query.py`, or the copy inside a checkout at
`.claude/skills/rail-api/rail_query.py`).

Common invocations:

```bash
# Next trains right now (Asia/Jerusalem), stations by name
python3 rail_query.py --from lod --to "tel aviv hashalom"

# By numeric station ID
python3 rail_query.py --from 5000 --to 4600

# Specific date/time
python3 rail_query.py --from 5000 --to 7000 --date 2026-09-08 --time 08:30

# Search for a station id/name (by English or Hebrew, partial ok)
python3 rail_query.py --find jerusalem
python3 rail_query.py --find חיפה

# Dump every station (id, English, Hebrew)
python3 rail_query.py --list-stations

# Full unparsed API response (all travels/legs)
python3 rail_query.py --from lod --to kiryat-gat --raw
```

## Station resolution

`--from` / `--to` accept:

- a **numeric station ID** (e.g. `5000`),
- an **English name** (e.g. `"kiryat gat"`, `"beer sheva center"`),
- a **Hebrew name** (e.g. `"קריית גת"`),
- a **unique partial** of either (e.g. `jerusalem` → Yitzhak Navon only if
  unique; `"tel aviv"` is ambiguous and the tool lists the candidates so you can
  pick one).

All ~68 stations come from the vendored `stations.py` (see its header for the
upstream source), so name↔ID lookup needs no network and no extra packages. Use
`--find` / `--list-stations` to discover IDs.

## Output

Default JSON is the closest 3 trains (the latest departing up to 15 min before
the query time, plus the next two at/after it):

```json
{
  "from": 5000, "fromName": "Lod",
  "to": 7000, "toName": "Kiryat Gat",
  "date": "2026-09-08", "queryTime": "08:30", "count": 3,
  "trains": [
    {
      "trainNumber": 49,
      "originStation": 5000, "originStationName": "Lod",
      "destinationStation": 7000, "destinationStationName": "Kiryat Gat",
      "originPlatform": 1, "destPlatform": 3,
      "departureTime": "2026-09-08T08:35:00",
      "arrivalTime":   "2026-09-08T09:13:00",
      "freeSeats": 0, "handicap": 1,
      "delayMinutes": 0
    }
  ]
}
```

`delayMinutes` is the live delay (`null` when the train isn't tracked yet). Use
`--raw` to get every field under `result.travels[].trains[]`.

Exit codes: **0** ok, **1** request/parse failure, **2** bad args / ambiguous
station. Errors go to stderr as `error: ...`.

## How the API works

- **Endpoint:** `POST https://rail-api.rail.co.il/rjpa/api/v1/timetable/searchTrain`
- **Auth:** header `ocp-apim-subscription-key` — an Azure APIM subscription key.
  The default in the script is the public key the site ships to every browser
  (not a personal secret). Override with `--api-key` if it rotates; find the
  current value in a browser DevTools Network tab on rail.co.il.
- **Required headers:** browser-like `User-Agent`, plus `Origin`/`Referer` set to
  `https://www.rail.co.il` — the API rejects requests without them.
- **Payload** (JSON): `methodName: "searchTrainLuzForDateTime"`, `fromStation` /
  `toStation` (numeric IDs), `date` (`YYYY-MM-DD`), `hour` (`HH:MM`),
  `scheduleType: "ByDeparture"`, `languageId: "English"`, `systemType: "2"`.
  Times are Asia/Jerusalem.

## Using from any agent (Hermes, etc.)

This skill's logic lives entirely in the standalone `rail_query.py`, so it isn't
Claude-Code-specific. Any agent or framework can use it by shelling out and
reading stdout as JSON:

```python
import json, subprocess
out = subprocess.run(
    ["python3", "rail_query.py", "--from", "lod", "--to", "kiryat gat"],
    capture_output=True, text=True,
)
trains = json.loads(out.stdout)["trains"] if out.returncode == 0 else []
```

Keep `rail_query.py` and `stations.py` together in the same directory (the script
imports the station table from its own folder). No install step is required.

## Notes

- Needs outbound internet to `rail-api.rail.co.il`; it does **not** need the
  192.168.0.123 server. That server only runs the Telegram bot
  (`rail-notification-bot`) which wraps this same API.
- Files: `rail_query.py` (client + CLI), `stations.py` (vendored station table),
  `SKILL.md` (this file).
