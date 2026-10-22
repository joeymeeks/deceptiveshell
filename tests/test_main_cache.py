"""Endpoint-level tests for caching + session-state behavior. Mocks the
Claude call - no live LLM needed."""
from fastapi.testclient import TestClient

from app import cache, session_state
from app.main import app

client = TestClient(app)

REQUEST_BODY = {
    "model": "claude-haiku-4-5",
    "messages": [{"role": "user", "content": "ls -la"}],
}


def setup_function() -> None:
    cache.clear()
    session_state.clear()


def _mock_completion(monkeypatch, response: str = "total 0"):
    call_count = 0

    async def fake_get_completion(*args, **kwargs) -> str:
        nonlocal call_count
        call_count += 1
        return response

    monkeypatch.setattr("app.main.get_completion", fake_get_completion)
    return lambda: call_count


def test_repeated_request_only_calls_claude_once(monkeypatch) -> None:
    get_calls = _mock_completion(monkeypatch)

    first = client.post("/v1/chat/completions", json=REQUEST_BODY)
    second = client.post("/v1/chat/completions", json=REQUEST_BODY)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["choices"][0]["message"]["content"] == "total 0"
    assert second.json()["choices"][0]["message"]["content"] == "total 0"
    assert get_calls() == 1


def test_different_sessions_dont_share_a_cached_answer(monkeypatch) -> None:
    get_calls = _mock_completion(monkeypatch)

    body_root = {
        "model": "claude-haiku-4-5",
        "messages": [
            {"role": "system", "content": "hostname is 'svr04' and username is 'root'."},
            {"role": "user", "content": "pwd"},
        ],
    }
    body_admin = {
        "model": "claude-haiku-4-5",
        "messages": [
            {"role": "system", "content": "hostname is 'svr04' and username is 'admin'."},
            {"role": "user", "content": "pwd"},
        ],
    }

    client.post("/v1/chat/completions", json=body_root)
    client.post("/v1/chat/completions", json=body_admin)

    assert get_calls() == 2


def test_cd_persists_across_requests_in_the_same_session(monkeypatch) -> None:
    """A cd in one request should show up in the state prompt sent to
    Claude on the next request in that same session."""
    seen_state_prompts = []

    async def fake_get_completion(system_prompt, *args, **kwargs) -> str:
        seen_state_prompts.append(system_prompt)
        return ""

    monkeypatch.setattr("app.main.get_completion", fake_get_completion)

    cd_body = {
        "model": "claude-haiku-4-5",
        "messages": [{"role": "user", "content": "cd /tmp"}],
    }
    pwd_body = {
        "model": "claude-haiku-4-5",
        "messages": [{"role": "user", "content": "pwd"}],
    }

    client.post("/v1/chat/completions", json=cd_body)
    client.post("/v1/chat/completions", json=pwd_body)

    assert "/tmp" in seen_state_prompts[-1]


def test_repeated_command_after_file_creation_is_not_a_stale_cache_hit(
    monkeypatch,
) -> None:
    """Found live: 'ls' right after 'touch text.txt' was returning the
    cached answer from an EARLIER 'ls' (before the file existed), since the
    cache key was only (session, cwd, command) and touch doesn't change
    cwd. Claude must actually get asked again once a file's been created,
    even though the command and cwd are identical to before."""
    get_calls = _mock_completion(monkeypatch, response="total 0")

    ls_body = {"model": "claude-haiku-4-5", "messages": [{"role": "user", "content": "ls"}]}
    touch_body = {
        "model": "claude-haiku-4-5",
        "messages": [{"role": "user", "content": "touch text.txt"}],
    }

    client.post("/v1/chat/completions", json=ls_body)  # ls #1 - cache miss
    client.post("/v1/chat/completions", json=touch_body)  # not cached on "ls" at all
    client.post("/v1/chat/completions", json=ls_body)  # ls #2 - must NOT reuse ls #1's cache

    assert get_calls() == 3


def test_repeated_command_after_file_removal_is_not_a_stale_cache_hit(
    monkeypatch,
) -> None:
    """Same bug class as the touch case above, but for rm/rmdir/mv/cp -
    those weren't tracked by session_state at all until this was found, so
    none of them changed the files fingerprint either."""
    get_calls = _mock_completion(monkeypatch, response="text.txt")

    ls_body = {"model": "claude-haiku-4-5", "messages": [{"role": "user", "content": "ls"}]}
    touch_body = {
        "model": "claude-haiku-4-5",
        "messages": [{"role": "user", "content": "touch text.txt"}],
    }
    rm_body = {
        "model": "claude-haiku-4-5",
        "messages": [{"role": "user", "content": "rm text.txt"}],
    }

    client.post("/v1/chat/completions", json=touch_body)
    client.post("/v1/chat/completions", json=ls_body)  # ls #1 - cache miss
    client.post("/v1/chat/completions", json=rm_body)
    client.post("/v1/chat/completions", json=ls_body)  # ls #2 - must NOT reuse ls #1's cache

    assert get_calls() == 4
