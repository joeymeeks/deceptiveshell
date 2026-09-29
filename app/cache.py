# just an in memory cache for llm responses
#
# keys off (session_key, cwd, command) now that session_state.py exists -
# so the same command in a different fake directory or different session
# doesnt collide with a cached answer that doesnt actually apply to it
import hashlib

_cache: dict[str, str] = {}


def _make_key(session_key: str, cwd: str, command: str) -> str:
    raw = f"{session_key}\x00{cwd}\x00{command}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(session_key: str, cwd: str, command: str) -> str | None:
    # returns the cached response if weve seen this exact command in this
    # exact session + directory before
    return _cache.get(_make_key(session_key, cwd, command))


def set(session_key: str, cwd: str, command: str, response: str) -> None:
    # saves the response so we dont call claude again for the same thing
    _cache[_make_key(session_key, cwd, command)] = response


def clear() -> None:
    # wipes the whole cache, only used by tests
    _cache.clear()
