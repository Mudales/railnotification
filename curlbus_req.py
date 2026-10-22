"""Bus arrivals via the curlbus JSON API (https://github.com/elad661/curlbus).

curlbus wraps the Israeli Ministry of Transport realtime SIRI feed. The only
realtime endpoint is /<stop_code>, so "line 460 towards Tel Aviv" is expressed
here as "line 460 as seen from the stop it departs from in that direction".
"""
import datetime

import requests
import pytz

API_BASE = 'https://curlbus.app'
TIMEOUT = 15
ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')

# How far ahead "what's coming soon" looks, in minutes.
DEFAULT_WINDOW_MINUTES = 30

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


def fetch_stop(stop_code):
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
        raise CurlbusError(' '.join(str(e).strip() for e in errors))

    return payload


def get_stop(stop_code, within_minutes=DEFAULT_WINDOW_MINUTES, lines=None):
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
    payload = fetch_stop(stop_code)

    # curlbus names the stop in stop_info, independently of whether any bus is
    # due - but it is absent for stops it has no GTFS entry for.
    info = payload.get('stop_info') or {}
    address = info.get('address') or {}

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

        arrivals.append({
            'line': str(line),
            'destination': destination,
            'operator': operator,
            'eta': eta,
            'minutes': minutes,
        })

    arrivals.sort(key=lambda a: a['eta'])

    return {
        'code': stop_code,
        'name': _text(info.get('name')) or None,
        # The plain 'city' field is the English one, which keeps the subtitle
        # left-to-right next to the Hebrew stop name.
        'city': address.get('city') or None,
        'arrivals': arrivals,
    }


def get_arrivals(stop_code, within_minutes=DEFAULT_WINDOW_MINUTES, lines=None):
    """Just the arrivals for a stop, soonest first. See get_stop()."""
    return get_stop(stop_code, within_minutes=within_minutes, lines=lines)['arrivals']


if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else '35096'
    stop = get_stop(code, within_minutes=30)
    print(f"{stop['code']}  {stop['name']}  [{stop['city']}]")
    for arrival in stop['arrivals']:
        print(f"{arrival['line']:<5} {arrival['minutes']:>3} min  {arrival['destination']}")
