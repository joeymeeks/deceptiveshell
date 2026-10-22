# tracks a fake filesystem per session so cd/mkdir/touch stay consistent
# across commands, since cowrie itself never tracks any of this (self.cwd
# on cowrie's side is set once to "/" and never updated - see readme's
# "known limitation: no session identifier" section for more on this)
import posixpath
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

DEFAULT_CWD = "/root"

# cowrie always appends "...username is '<name>'..." to the system message
# it builds, no matter what custom system_prompt template is configured in
# cowrie.cfg, so this works without needing any cowrie.cfg changes at all
_USERNAME_RE = re.compile(r"username is '([^']*)'")


@dataclass
class SessionState:
    cwd: str = DEFAULT_CWD
    files: set[str] = field(default_factory=set)


_sessions: dict[str, SessionState] = {}


def get_session_key(system_text: str | None) -> str:
    # falls back to "default" when theres no cowrie-shaped system message at
    # all, like when just curling the middleware directly for testing
    if system_text:
        match = _USERNAME_RE.search(system_text)
        if match:
            return match.group(1)
    return "default"


def get_state(session_key: str) -> SessionState:
    return _sessions.setdefault(session_key, SessionState())


def _resolve_path(cwd: str, target: str) -> str:
    if not posixpath.isabs(target):
        target = posixpath.join(cwd, target)
    return posixpath.normpath(target)


def update_state(session_key: str, command: str) -> None:
    # only cares about cd/mkdir/touch - every other command leaves state
    # untouched since it doesnt create anything or change directory
    state = get_state(session_key)
    parts = command.split()
    if not parts:
        return

    cmd, args = parts[0], [a for a in parts[1:] if not a.startswith("-")]

    if cmd == "cd":
        target = args[0] if args else DEFAULT_CWD
        state.cwd = _resolve_path(state.cwd, target)
    elif cmd in ("mkdir", "touch"):
        for name in args:
            state.files.add(_resolve_path(state.cwd, name))


def build_state_prompt(session_key: str) -> str:
    # this gets injected into claude's system prompt so it stays consistent
    # with whats already there instead of making stuff up each time
    state = get_state(session_key)
    lines = [
        f"Current working directory: {state.cwd} "
        "(this ALREADY includes the effect of every earlier command in the "
        "history, including cd. Never re-apply earlier cd commands; pwd must "
        "print exactly this path.)"
    ]
    if state.files:
        listing = ", ".join(sorted(state.files))
        lines.append(
            f"Files/directories that already exist from earlier in this session: {listing}"
        )
    else:
        lines.append("No files or directories have been created yet this session.")
    lines.append(
        "Current date/time: "
        + datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S UTC %Y")
    )
    return "\n".join(lines)


def clear() -> None:
    # wipes every tracked session, only used by tests
    _sessions.clear()
