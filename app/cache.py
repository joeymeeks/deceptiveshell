# just an in memory cache for llm responses
#
# keying off the whole conversation for now since we dont have session
# state tracking yet - once that exists this should key off
# (session_id, cwd, command) instead of the raw convo
import hashlib
import json

_cache: dict[str, str] = {}


def _make_key(conversation: list[dict]) -> str:
    serialized = json.dumps(conversation, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get(conversation: list[dict]) -> str | None:
    # returns the cached response if we've seen this exact convo before
    return _cache.get(_make_key(conversation))


def set(conversation: list[dict], response: str) -> None:
    # saves the response so we dont call claude again for the same convo
    _cache[_make_key(conversation)] = response


def clear() -> None:
    # wipes the whole cache, only used by tests
    _cache.clear()
