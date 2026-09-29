"""Endpoint-level test: a repeated identical request should hit the cache
and skip calling Claude the second time. Mocks the Claude call - no live
LLM needed."""
from fastapi.testclient import TestClient

from app import cache
from app.main import app

client = TestClient(app)

REQUEST_BODY = {
    "model": "claude-haiku-4-5",
    "messages": [{"role": "user", "content": "ls -la"}],
}


def setup_function() -> None:
    cache.clear()


def test_repeated_request_only_calls_claude_once(monkeypatch) -> None:
    call_count = 0

    async def fake_get_completion(*args, **kwargs) -> str:
        nonlocal call_count
        call_count += 1
        return "total 0"

    monkeypatch.setattr("app.main.get_completion", fake_get_completion)

    first = client.post("/v1/chat/completions", json=REQUEST_BODY)
    second = client.post("/v1/chat/completions", json=REQUEST_BODY)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["choices"][0]["message"]["content"] == "total 0"
    assert second.json()["choices"][0]["message"]["content"] == "total 0"
    assert call_count == 1
