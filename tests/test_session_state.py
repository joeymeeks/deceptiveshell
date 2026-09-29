"""Unit tests for app/session_state.py - no live LLM needed."""
from app import session_state


def setup_function() -> None:
    session_state.clear()


def test_get_session_key_parses_username_from_cowrie_system_text() -> None:
    text = (
        "You are simulating a Linux server accessed via SSH. "
        "The hostname is 'svr04' and username is 'root'. "
        "The current working directory is '/'."
    )
    assert session_state.get_session_key(text) == "root"


def test_get_session_key_falls_back_to_default_with_no_system_text() -> None:
    assert session_state.get_session_key(None) == "default"


def test_get_session_key_falls_back_to_default_when_username_missing() -> None:
    assert session_state.get_session_key("some unrelated text") == "default"


def test_new_session_starts_at_default_cwd_with_no_files() -> None:
    state = session_state.get_state("root")

    assert state.cwd == session_state.DEFAULT_CWD
    assert state.files == set()


def test_cd_absolute_path_updates_cwd() -> None:
    session_state.update_state("root", "cd /tmp")

    assert session_state.get_state("root").cwd == "/tmp"


def test_cd_relative_path_joins_onto_current_cwd() -> None:
    session_state.update_state("root", "cd /home/attacker")
    session_state.update_state("root", "mkdir Documents")
    session_state.update_state("root", "cd Documents")

    assert session_state.get_state("root").cwd == "/home/attacker/Documents"


def test_cd_dotdot_goes_up_a_directory() -> None:
    session_state.update_state("root", "cd /home/attacker/Documents")
    session_state.update_state("root", "cd ..")

    assert session_state.get_state("root").cwd == "/home/attacker"


def test_cd_with_no_args_goes_to_default_cwd() -> None:
    session_state.update_state("root", "cd /tmp")
    session_state.update_state("root", "cd")

    assert session_state.get_state("root").cwd == session_state.DEFAULT_CWD


def test_mkdir_adds_a_path_under_current_cwd() -> None:
    session_state.update_state("root", "mkdir loot")

    assert "/root/loot" in session_state.get_state("root").files


def test_touch_adds_a_path_under_current_cwd() -> None:
    session_state.update_state("root", "touch notes.txt")

    assert "/root/notes.txt" in session_state.get_state("root").files


def test_unrelated_command_does_not_change_state() -> None:
    session_state.update_state("root", "ls -la")

    state = session_state.get_state("root")
    assert state.cwd == session_state.DEFAULT_CWD
    assert state.files == set()


def test_sessions_are_isolated_from_each_other() -> None:
    session_state.update_state("root", "cd /tmp")
    session_state.update_state("attacker2", "cd /var")

    assert session_state.get_state("root").cwd == "/tmp"
    assert session_state.get_state("attacker2").cwd == "/var"


def test_build_state_prompt_reports_no_files_when_empty() -> None:
    prompt = session_state.build_state_prompt("root")

    assert session_state.DEFAULT_CWD in prompt
    assert "No files or directories" in prompt


def test_build_state_prompt_lists_created_files() -> None:
    session_state.update_state("root", "touch notes.txt")

    prompt = session_state.build_state_prompt("root")
    assert "/root/notes.txt" in prompt
