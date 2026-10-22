"""Per-user favourite stops, kept as one JSON file.

The file lives in a Docker volume (see docker-compose.yml), so it survives the
`docker compose up -d --build` rebuild that recreates the container.
"""
import json
import os
import tempfile
import threading

DATA_DIR = os.environ.get(
    'RAIL_DATA_DIR',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'),
)
PATH = os.path.join(DATA_DIR, 'favorites.json')

MAX_PER_USER = 12
MAX_NAME_CHARS = 24

_lock = threading.Lock()


class FavoritesError(Exception):
    """Something the user should be told about, in their own words."""


def _load():
    try:
        with open(PATH, encoding='utf-8') as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    except (ValueError, OSError) as e:
        # A corrupt or unreadable file must not take the bot down.
        print(f"favorites: cannot read {PATH}: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def _save(data):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        # Write to a temp file and rename, so an interrupted write cannot
        # leave a half-written favorites.json behind.
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, prefix='.favorites-', suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, ensure_ascii=False, indent=1)
            os.replace(tmp, PATH)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as e:
        print(f"favorites: cannot write {PATH}: {e}")
        raise FavoritesError("Could not save - the bot's storage is not writable.")


def list_for(user_id):
    """The user's favourites as {name: stop_code}, in insertion order."""
    with _lock:
        saved = _load().get(str(user_id))
    return dict(saved) if isinstance(saved, dict) else {}


def add(user_id, name, stop_code):
    """Save (or overwrite) one favourite. Raises FavoritesError if refused."""
    name = ' '.join(str(name).split())
    stop_code = str(stop_code).strip()

    if not name:
        raise FavoritesError("Give the stop a name.")
    if len(name) > MAX_NAME_CHARS:
        raise FavoritesError(f"Keep the name under {MAX_NAME_CHARS} characters.")
    if not stop_code.isdigit():
        raise FavoritesError("A stop code is all digits.")

    with _lock:
        data = _load()
        mine = data.setdefault(str(user_id), {})
        if name not in mine and len(mine) >= MAX_PER_USER:
            raise FavoritesError(
                f"You already have {MAX_PER_USER} favourites - remove one first."
            )
        mine[name] = stop_code
        _save(data)
    return name


def remove(user_id, name):
    """Delete one favourite. Returns True if it was there."""
    name = ' '.join(str(name).split())
    with _lock:
        data = _load()
        mine = data.get(str(user_id))
        if not isinstance(mine, dict) or name not in mine:
            return False
        del mine[name]
        _save(data)
    return True
