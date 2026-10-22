#!/usr/bin/env python3
"""Analyze Cowrie-style JSON SSH attack logs and export session behavior metrics to CSV."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


RECON_COMMANDS = {
    "whoami",
    "uname",
    "id",
    "hostname",
    "ls",
    "pwd",
    "cat /etc/passwd",
    "cat /etc/shadow",
    "cat /proc/cpuinfo",
    "nproc",
    "vmstat",
    "free",
    "df",
    "ifconfig",
    "ip addr",
    "ps",
}

FILE_SYSTEM_COMMANDS = {
    "mkdir",
    "cd",
    "touch",
    "echo",
    "cat",
    "cp",
    "mv",
    "chmod",
    "rm",
    "chown",
    "wget",
    "curl",
}

PERSISTENCE_COMMANDS = {
    "wget",
    "curl",
    "chmod +x",
    "bash",
    "sh",
    "python",
    "perl",
    "nc",
    "nc -l",
    "cron",
    "systemctl",
}


def parse_ndjson(path: Path) -> list[dict[str, Any]]:
    """Read newline-delimited JSON and return a list of dictionaries."""
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as infile:
        for line_number, raw_line in enumerate(infile, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON line {line_number} in {path}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Expected an object on line {line_number}, got {type(item).__name__}")
            rows.append(item)
    return rows


def load_records(input_path: Path) -> list[dict[str, Any]]:
    if input_path.is_dir():
        records: list[dict[str, Any]] = []
        files = sorted(
            [p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".ndjson"}],
            key=lambda p: p.name.lower(),
        )
        if not files:
            raise ValueError(f"No .json or .ndjson files found in {input_path}")
        for file_path in files:
            records.extend(parse_ndjson(file_path))
        return records
    return parse_ndjson(input_path)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "; ".join(stringify_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def normalize_command(raw: str) -> str:
    command = str(raw or "").strip()
    if not command:
        return ""
    return command.split(" ", 1)[0].lower()


def compute_depth_score(commands: list[str], session_length_seconds: float | None) -> int:
    score = 0
    if commands:
        score += 1
    if len(commands) >= 3:
        score += 1
    if any(normalize_command(cmd) in RECON_COMMANDS for cmd in commands):
        score += 1
    if any(normalize_command(cmd) in FILE_SYSTEM_COMMANDS for cmd in commands):
        score += 1
    if any(normalize_command(cmd) in PERSISTENCE_COMMANDS for cmd in commands):
        score += 1
    if session_length_seconds is not None and session_length_seconds > 300:
        score += 1
    return min(score, 5)


def classify_behavior(commands: list[str], has_login: bool) -> tuple[str, str, str]:
    lower_commands = [str(c).lower() for c in commands]

    if has_login and not commands:
        return ("Credential check", "Login only", "low_engagement")

    if any("wget" in c or "curl" in c for c in lower_commands):
        return ("Download / payload staging", "Attack chain includes retrieval of remote payload", "download_attempt")

    if any("mkdir" in c or "cd" in c or "echo" in c or "chmod" in c for c in lower_commands):
        return ("File system probe", "Attacker is exploring and manipulating the host filesystem", "filesystem_manipulation")

    if any("whoami" in c or "uname" in c or "hostname" in c or "ls" in c or "cat /etc/passwd" in c for c in lower_commands):
        return ("Reconnaissance", "Host information gathering and environment discovery", "reconnaissance")

    if any("asdfqwer" in c or "ignore all previous" in c or "exitr" in c for c in lower_commands):
        return ("Noise / prompt injection", "Low-signal interaction with textual noise or prompt confusion", "noise_or_evasion")

    if has_login:
        return ("Credential abuse", "Authenticated session with follow-up interaction", "credential_abuse")

    return ("Low engagement", "Very light interaction with minimal commands", "low_engagement")


def get_dropoff_point(commands: list[str], final_event: str) -> str:
    if not commands:
        return "No commands issued"
    if final_event.startswith("cowrie.session.closed"):
        return f"Session ended after: {commands[-1]}"
    if commands:
        return f"Last observed command: {commands[-1]}"
    return "No clear drop-off event"


def get_session_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    sessions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        session_id = str(record.get("session") or "unknown")
        sessions[session_id].append(record)

    summaries: list[dict[str, str]] = []
    for session_id, events in sorted(sessions.items(), key=lambda item: (item[0] != "unknown", item[0])):
        ordered_events = sorted(events, key=lambda event: parse_iso_datetime(str(event.get("timestamp") or "")) or datetime.min)

        login_event = next((e for e in ordered_events if e.get("eventid") == "cowrie.login.success"), None)
        connect_event = next((e for e in ordered_events if e.get("eventid") == "cowrie.session.connect"), None)
        close_event = next((e for e in ordered_events if e.get("eventid") == "cowrie.session.closed"), None)
        connect_time = parse_iso_datetime(str(connect_event.get("timestamp") or "")) if connect_event else None
        close_time = parse_iso_datetime(str(close_event.get("timestamp") or "")) if close_event else None

        duration_seconds = 0.0
        if connect_time and close_time:
            duration_seconds = (close_time - connect_time).total_seconds()

        commands: list[str] = []
        for event in ordered_events:
            if event.get("eventid") == "cowrie.command.input":
                value = str(event.get("input") or "").strip()
                if value:
                    commands.append(value)

        unique_commands = len({normalize_command(cmd) for cmd in commands if normalize_command(cmd)})
        command_count = len(commands)
        engagement_score = compute_depth_score(commands, duration_seconds)

        src_ip = next((str(e.get("src_ip") or "") for e in ordered_events if e.get("src_ip")), "")
        username = next((str(e.get("username") or "") for e in ordered_events if e.get("username")), "")
        password = next((str(e.get("password") or "") for e in ordered_events if e.get("password")), "")
        final_event = next((str(e.get("eventid") or "") for e in reversed(ordered_events) if e.get("eventid")), "")
        taxonomy_primary, taxonomy_detail, taxonomy_tag = classify_behavior(commands, bool(login_event))

        summaries.append(
            {
                "session_id": session_id,
                "src_ip": src_ip,
                "username": username,
                "password": password,
                "login_success": "true" if login_event else "false",
                "session_length_seconds": f"{duration_seconds:.2f}",
                "command_count": str(command_count),
                "unique_commands": str(unique_commands),
                "depth_of_engagement": str(engagement_score),
                "taxonomy_primary": taxonomy_primary,
                "taxonomy_detail": taxonomy_detail,
                "taxonomy_tag": taxonomy_tag,
                "dropoff_point": get_dropoff_point(commands, final_event),
                "last_command": commands[-1] if commands else "",
                "first_seen": str(connect_event.get("timestamp") or "") if connect_event else "",
                "last_seen": str(close_event.get("timestamp") or "") if close_event else "",
            }
        )

    return summaries


def build_taxonomy_summary(summaries: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in summaries:
        grouped[row["taxonomy_primary"]].append(row)

    result: list[dict[str, str]] = []
    for taxonomy, rows in sorted(grouped.items()):
        avg_length = sum(float(r["session_length_seconds"]) for r in rows) / len(rows)
        avg_commands = sum(float(r["command_count"]) for r in rows) / len(rows)
        avg_depth = sum(float(r["depth_of_engagement"]) for r in rows) / len(rows)
        session_count = len(rows)
        source_ips = sorted({r["src_ip"] for r in rows if r["src_ip"]})
        common_dropoff = Counter(r["dropoff_point"] for r in rows if r["dropoff_point"]).most_common(1)

        result.append(
            {
                "taxonomy_primary": taxonomy,
                "session_count": str(session_count),
                "avg_session_length_seconds": f"{avg_length:.2f}",
                "avg_command_count": f"{avg_commands:.2f}",
                "avg_depth_of_engagement": f"{avg_depth:.2f}",
                "distinct_source_ips": "; ".join(source_ips),
                "most_common_dropoff": common_dropoff[0][0] if common_dropoff else "",
                "examples": "; ".join(sorted({r["last_command"] for r in rows if r["last_command"]})[:5]),
            }
        )

    return result


def build_attack_pattern_summary(summaries: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in summaries:
        grouped[row["taxonomy_tag"]].append(row)

    result: list[dict[str, str]] = []
    for tag, rows in sorted(grouped.items()):
        sample_commands = sorted({r["last_command"] for r in rows if r["last_command"]})[:5]
        result.append(
            {
                "taxonomy_tag": tag,
                "session_count": str(len(rows)),
                "avg_session_length_seconds": f"{sum(float(r['session_length_seconds']) for r in rows)/len(rows):.2f}",
                "avg_command_count": f"{sum(float(r['command_count']) for r in rows)/len(rows):.2f}",
                "avg_depth_of_engagement": f"{sum(float(r['depth_of_engagement']) for r in rows)/len(rows):.2f}",
                "sample_last_commands": "; ".join(sample_commands),
                "sample_taxonomy_primary": "; ".join(sorted({r['taxonomy_primary'] for r in rows})),
            }
        )
    return result


def write_summary_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "session_id",
        "src_ip",
        "username",
        "password",
        "login_success",
        "session_length_seconds",
        "command_count",
        "unique_commands",
        "depth_of_engagement",
        "taxonomy_primary",
        "taxonomy_detail",
        "taxonomy_tag",
        "dropoff_point",
        "last_command",
        "first_seen",
        "last_seen",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_taxonomy_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "taxonomy_primary",
        "session_count",
        "avg_session_length_seconds",
        "avg_command_count",
        "avg_depth_of_engagement",
        "distinct_source_ips",
        "most_common_dropoff",
        "examples",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_attack_pattern_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = [
        "taxonomy_tag",
        "session_count",
        "avg_session_length_seconds",
        "avg_command_count",
        "avg_depth_of_engagement",
        "sample_last_commands",
        "sample_taxonomy_primary",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_raw_event_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    if not records:
        raise ValueError("No records found in input log.")

    fieldnames: list[str] = []
    for record in records:
        for key in record.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({key: stringify_value(record.get(key, "")) for key in fieldnames})


def resolve_output_paths(output_arg: str) -> tuple[Path, Path, Path, Path]:
    output_path = Path(output_arg).resolve()
    if output_path.suffix.lower() == ".csv":
        return output_path, output_path.with_name("taxonomy_summary.csv"), output_path.with_name("attack_patterns.csv"), output_path.with_name("raw_events.csv")
    output_path.mkdir(parents=True, exist_ok=True)
    return (
        output_path / "session_summary.csv",
        output_path / "taxonomy_summary.csv",
        output_path / "attack_patterns.csv",
        output_path / "raw_events.csv",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Cowrie events into CSV reports for attacker behavior analysis.")
    parser.add_argument("input", nargs="?", default="cowrie_sample_llm.json", help="Input Cowrie NDJSON log file or folder")
    parser.add_argument("-o", "--output", default="cowrie_analysis_output", help="Output directory or summary CSV path")
    parser.add_argument("--raw-output", default=None, help="Optional explicit path for the raw-event CSV")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    session_path, taxonomy_path, attack_path, raw_path = resolve_output_paths(args.output)

    if args.raw_output:
        raw_path = Path(args.raw_output).resolve()

    records = load_records(input_path)
    summaries = get_session_rows(records)

    write_summary_csv(summaries, session_path)
    write_taxonomy_csv(build_taxonomy_summary(summaries), taxonomy_path)
    write_attack_pattern_csv(build_attack_pattern_summary(summaries), attack_path)
    write_raw_event_csv(records, raw_path)

    print(f"Generated session summary: {session_path.name}")
    print(f"Generated taxonomy summary: {taxonomy_path.name}")
    print(f"Generated attack-pattern summary: {attack_path.name}")
    print(f"Generated raw event export: {raw_path.name}")


if __name__ == "__main__":
    main()
