"""Unit tests for app/cache.py - no live LLM needed."""
from app import cache


def setup_function() -> None:
    cache.clear()


def test_miss_returns_none() -> None:
    conversation = [{"role": "user", "content": "ls -la"}]
    assert cache.get(conversation) is None


def test_hit_returns_stored_response() -> None:
    conversation = [{"role": "user", "content": "ls -la"}]
    cache.set(conversation, "total 0")

    assert cache.get(conversation) == "total 0"


def test_different_conversation_is_a_different_key() -> None:
    cache.set([{"role": "user", "content": "ls -la"}], "total 0")

    assert cache.get([{"role": "user", "content": "pwd"}]) is None


def test_same_content_hits_regardless_of_list_construction() -> None:
    """Two separately-built but identical conversations must hit the same
    cache entry - the key is derived from content, not object identity."""
    cache.set([{"role": "user", "content": "whoami"}], "root")

    rebuilt = [dict(role="user", content="whoami")]
    assert cache.get(rebuilt) == "root"


def test_longer_history_is_a_different_key_than_a_prefix_of_it() -> None:
    """A follow-up command changes the conversation Cowrie resends, so it
    must not collide with the cached entry for the shorter history."""
    first_turn = [{"role": "user", "content": "cd /tmp"}]
    cache.set(first_turn, "")

    second_turn = [
        {"role": "user", "content": "cd /tmp"},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "ls"},
    ]
    assert cache.get(second_turn) is None
