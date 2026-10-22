# just an in memory cache for llm responses
#
# keys off (session_key, cwd, files_fingerprint, command) - files_fingerprint
# is a stable hash of whatever files/dirs session_state has tracked for this
# session (see session_state.files_fingerprint). without it, "ls" right
# after "touch foo" would hit the SAME cache entry as an earlier "ls" in the
# same cwd and return the stale pre-touch answer, since cwd+command alone
# dont change when a file gets created - found this live, not in a test
import hashlib

_cache: dict[str, str] = {}


def _make_key(session_key: str, cwd: str, files_fingerprint: str, command: str) -> str:
    raw = f"{session_key}\x00{cwd}\x00{files_fingerprint}\x00{command}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(session_key: str, cwd: str, files_fingerprint: str, command: str) -> str | None:
    # returns the cached response if weve seen this exact command in this
    # exact session + directory + file state before
    return _cache.get(_make_key(session_key, cwd, files_fingerprint, command))


def set(
    session_key: str, cwd: str, files_fingerprint: str, command: str, response: str
) -> None:
    # saves the response so we dont call claude again for the same thing
    _cache[_make_key(session_key, cwd, files_fingerprint, command)] = response


def clear() -> None:
    # wipes the whole cache, only used by tests
    _cache.clear()
