"""Unit tests for app/cache.py - no live LLM needed."""
from app import cache


def setup_function() -> None:
    cache.clear()


def test_miss_returns_none() -> None:
    assert cache.get("root", "/root", "ls -la") is None


def test_hit_returns_stored_response() -> None:
    cache.set("root", "/root", "ls -la", "total 0")

    assert cache.get("root", "/root", "ls -la") == "total 0"


def test_different_command_is_a_different_key() -> None:
    cache.set("root", "/root", "ls -la", "total 0")

    assert cache.get("root", "/root", "pwd") is None


def test_different_cwd_is_a_different_key() -> None:
    """The same command in a different fake directory must not collide -
    otherwise an attacker who cd'd somewhere else would get a cached ls
    listing that belongs to a different directory."""
    cache.set("root", "/root", "ls", "total 0")

    assert cache.get("root", "/tmp", "ls") is None


def test_different_session_is_a_different_key() -> None:
    """Two different attacker sessions must not share cached answers, even
    with the same command and the same cwd."""
    cache.set("root", "/root", "whoami", "root")

    assert cache.get("attacker2", "/root", "whoami") is None
