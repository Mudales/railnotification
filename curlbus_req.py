"""Bus arrivals via the curlbus JSON API (https://github.com/elad661/curlbus).

curlbus wraps the Israeli Ministry of Transport realtime SIRI feed. The only
realtime endpoint is /<stop_code>, so "line 460 towards Tel Aviv" is expressed
here as "line 460 as seen from the stop it departs from in that direction".
"""
import datetime
import math
import threading
import time

import requests
import pytz

API_BASE = 'https://curlbus.app'
TIMEOUT = 15
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# How far ahead "what's coming soon" looks, in minutes.
DEFAULT_WINDOW_MINUTES = 30

# curlbus is a free service run by one person, and ETAs only move every few
# seconds, so repeated taps on the same stop are served from memory.
CACHE_SECONDS = 25
CACHE_MAX_STOPS = 64
_cache = {}
_cache_lock = threading.Lock()

# Bus stops we care about, per line and direction.
# Stop codes verified against the GTFS feed (open-bus stride API) and against
# live curlbus responses. Each physical stop serves one direction only, so
# filtering by line at the stop is enough to pin the direction down.
BUS_ROUTES = {
    '460 Lod → Tel Aviv': {
        'line': '460',
        'stop': '35096',
        'stop_name': 'Lod Train Station / Yoseftal',
    },
    '460 Tel Aviv → Lod': {
        'line': '460',
        'stop': '20001',
        'stop_name': 'TA Savidor Station / Platforms A',
    },
    '464 Lod → Tel Aviv': {
        'line': '464',
        'stop': '35096',
        'stop_name': 'Lod Train Station / Yoseftal',
    },
    '464 Tel Aviv → Lod': {
        'line': '464',
        'stop': '20349',
        'stop_name': 'TA Savidor Station / Derech Namir',
    },
}


class CurlbusError(Exception):
    """Raised when curlbus could not answer the question we asked."""


class UnknownStop(CurlbusError):
    """The stop code itself is wrong - retrying will not help."""


def _now():
    return datetime.datetime.now(ISRAEL_TZ)


def _parse_eta(eta_str):
    """curlbus sends '2026-10-22 22:34:00+03:00' - not quite ISO on py<3.11."""
    if not eta_str:
        return None
    try:
        return datetime.datetime.fromisoformat(eta_str.replace(' ', 'T', 1))
    except ValueError:
        print(f"curlbus: unparsable eta {eta_str!r}")
        return None


def _text(multilingual, fallback=''):
    """Pick a human readable string out of curlbus' {HE,EN,AR} dicts."""
    if not isinstance(multilingual, dict):
        return fallback
    for key in ('HE', 'EN', 'AR'):
        value = multilingual.get(key)
        if value:
            return value
    return fallback


def _haversine_km(from_point, to_point):
    """Straight-line distance between two (lat, lon) pairs, in km."""
    lat1, lon1 = from_point
    lat2, lon2 = to_point
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return 2 * radius * math.asin(math.sqrt(a))


def _point(location):
    """curlbus sends lat/lon as strings in visits and floats in stop_info."""
    if not isinstance(location, dict):
        return None
    try:
        return float(location['lat']), float(location['lon'])
    except (KeyError, TypeError, ValueError):
        return None


def fetch_stop(stop_code, use_cache=True):
    """curlbus' raw JSON for a stop code, cached briefly. Raises CurlbusError.

    Only successful responses are cached - an error is always retried.
    """
    if use_cache:
        with _cache_lock:
            cached = _cache.get(stop_code)
            if cached and (time.monotonic() - cached[0]) < CACHE_SECONDS:
                return cached[1]

    payload = _request_stop(stop_code)

    with _cache_lock:
        if len(_cache) >= CACHE_MAX_STOPS:
            _cache.clear()
        _cache[stop_code] = (time.monotonic(), payload)
    return payload


def _request_stop(stop_code):
    """Return curlbus' raw JSON for a stop code, or raise CurlbusError."""
    url = f"{API_BASE}/{stop_code}"
    try:
        response = requests.get(
            url,
            headers={'Accept': 'application/json'},
            timeout=TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise CurlbusError("The bus service did not answer in time.")
    except requests.exceptions.RequestException as e:
        print(f"curlbus request failed: {e}")
        raise CurlbusError("Could not reach the bus service.")

    if response.status_code != 200:
        print(f"curlbus returned {response.status_code} for {stop_code}")
        raise CurlbusError(f"The bus service returned an error ({response.status_code}).")

    try:
        payload = response.json()
    except ValueError:
        print(f"curlbus returned non-JSON for {stop_code}: {response.text[:200]}")
        raise CurlbusError("The bus service sent an unreadable answer.")

    errors = payload.get('errors')
    if errors:
        # Typically "Invalid stop code 99999999" - worth showing as-is.
        message = ' '.join(str(e).strip() for e in errors)
        if 'invalid stop code' in message.lower():
            raise UnknownStop(message)
        raise CurlbusError(message)

    return payload


def get_stop(stop_code, within_minutes=DEFAULT_WINDOW_MINUTES, lines=None,
             use_cache=True):
    """Everything we show for one stop, from a single curlbus request.

    Args:
        stop_code: the number printed on the bus stop sign.
        within_minutes: only keep arrivals due within this many minutes.
        lines: optional iterable of line numbers to keep (e.g. {'460'}).

    Returns:
        dict: code, name (or None), city (or None), arrivals - where each
        arrival is a dict of line, destination, operator, eta, minutes.
    """
    stop_code = str(stop_code).strip()
    payload = fetch_stop(stop_code, use_cache=use_cache)

    # curlbus names the stop in stop_info, independently of whether any bus is
    # due - but it is absent for stops it has no GTFS entry for.
    info = payload.get('stop_info') or {}
    address = info.get('address') or {}
    stop_point = _point(info.get('location'))

    visits = payload.get('visits') or {}
    # The key is normally the requested code, but don't assume it.
    raw_visits = visits.get(stop_code)
    if raw_visits is None:
        raw_visits = next(iter(visits.values()), [])

    now = _now()
    cutoff = now + datetime.timedelta(minutes=within_minutes)
    wanted = {str(line) for line in lines} if lines else None

    arrivals = []
    seen = set()
    for visit in raw_visits:
        line = visit.get('line_name')
        if not line or (wanted and str(line) not in wanted):
            continue

        eta = _parse_eta(visit.get('eta'))
        if eta is None or eta > cutoff:
            continue

        minutes = int(round((eta - now).total_seconds() / 60))
        if minutes < 0:
            continue

        route = (visit.get('static_info') or {}).get('route') or {}
        destination = _text((route.get('destination') or {}).get('name'))
        operator = _text((route.get('agency') or {}).get('name'))

        # The same bus sometimes shows up more than once in the SIRI feed.
        key = (line, destination, eta)
        if key in seen:
            continue
        seen.add(key)

        # A vehicle position means this ETA comes from a bus being tracked
        # right now, rather than from the timetable alone.
        vehicle_point = _point(visit.get('location'))
        distance_km = None
        if vehicle_point and stop_point:
            distance_km = _haversine_km(vehicle_point, stop_point)

        arrivals.append({
            'line': str(line),
            'destination': destination,
            'operator': operator,
            'eta': eta,
            'minutes': minutes,
            'tracked': vehicle_point is not None,
            'distance_km': distance_km,
        })

    arrivals.sort(key=lambda a: a['eta'])

    return {
        'code': stop_code,
        'name': _text(info.get('name')) or None,
        # The plain 'city' field is the English one, which keeps the subtitle
        # left-to-right next to the Hebrew stop name.
        'city': address.get('city') or None,
        'location': stop_point,
        'arrivals': arrivals,
    }


def get_arrivals(stop_code, within_minutes=DEFAULT_WINDOW_MINUTES, lines=None,
                 use_cache=True):
    """Just the arrivals for a stop, soonest first. See get_stop()."""
    return get_stop(stop_code, within_minutes=within_minutes, lines=lines,
                    use_cache=use_cache)['arrivals']


if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else '35096'
    stop = get_stop(code, within_minutes=30)
    print(f"{stop['code']}  {stop['name']}  [{stop['city']}]")
    for arrival in stop['arrivals']:
        where = f"{arrival['distance_km']:.1f} km" if arrival['distance_km'] else '-'
        print(f"{arrival['line']:<5} {arrival['minutes']:>3} min  "
              f"{'live' if arrival['tracked'] else '    '} {where:>8}  "
              f"{arrival['destination']}")
