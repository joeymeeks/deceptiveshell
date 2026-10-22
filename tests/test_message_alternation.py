"""Unit tests for _build_claude_messages's "[no output]" gap-filling -
cowrie only logs an assistant turn when a command's output was non-empty,
so two silent commands in a row show up as two user turns with nothing in
between. Claude's API wants strict alternation."""
from app.main import ChatMessage, _build_claude_messages


def _msg(role: str, content: str) -> ChatMessage:
    return ChatMessage(role=role, content=content)


def test_normal_alternating_history_is_untouched() -> None:
    messages = [
        _msg("user", "ls"),
        _msg("assistant", "file1 file2"),
        _msg("user", "pwd"),
    ]
    assert _build_claude_messages(messages, None) == [
        {"role": "user", "content": "ls"},
        {"role": "assistant", "content": "file1 file2"},
        {"role": "user", "content": "pwd"},
    ]


def test_two_consecutive_user_turns_get_a_placeholder_between_them() -> None:
    messages = [_msg("user", "cd /tmp"), _msg("user", "mkdir foo")]

    result = _build_claude_messages(messages, None)

    assert result == [
        {"role": "user", "content": "cd /tmp"},
        {"role": "assistant", "content": "[no output]"},
        {"role": "user", "content": "mkdir foo"},
    ]


def test_empty_assistant_turn_becomes_no_output_placeholder() -> None:
    messages = [_msg("user", "cd /tmp"), _msg("assistant", ""), _msg("user", "pwd")]

    result = _build_claude_messages(messages, None)

    assert result == [
        {"role": "user", "content": "cd /tmp"},
        {"role": "assistant", "content": "[no output]"},
        {"role": "user", "content": "pwd"},
    ]


def test_leading_assistant_turns_are_dropped() -> None:
    messages = [_msg("assistant", "stray"), _msg("user", "ls")]

    result = _build_claude_messages(messages, None)

    assert result == [{"role": "user", "content": "ls"}]


def test_exec_mode_falls_back_to_system_text_when_no_conversation() -> None:
    result = _build_claude_messages([], "exec mode system text")

    assert result == [{"role": "user", "content": "exec mode system text"}]
