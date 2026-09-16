# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Tests for the `inspect-jitsi` CLI (requires the `cli` extra)."""

from __future__ import annotations

import json

import pytest

typer = pytest.importorskip("typer")
from typer.testing import CliRunner  # noqa: E402

from inspect_jitsi import cli  # noqa: E402
from inspect_jitsi.xmpp.diagnosis import DiagnosisResult  # noqa: E402
from inspect_jitsi.xmpp.participant import Participant  # noqa: E402

runner = CliRunner()


def test_count_prints_the_participant_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "get_participant_count", lambda url, name: 3)  # noqa: ARG005

    result = runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "3"


def test_count_defaults_to_inspect_jitsi_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str) -> int:
        seen["name"] = name
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)

    runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert seen["name"] == "inspect-jitsi"


def test_count_accepts_name_option(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str) -> int:
        seen["name"] = name
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)

    runner.invoke(cli.app, ["count", "--name", "Alice", "https://meet.example.com/room"])

    assert seen["name"] == "Alice"


def test_count_accepts_name_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str) -> int:
        seen["name"] = name
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)
    monkeypatch.setenv("INSPECT_JITSI_NAME", "FromEnv")

    runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert seen["name"] == "FromEnv"


def test_count_reports_failure_and_runs_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_get_participant_count(_url: str, name: str) -> int:  # noqa: ARG001
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "get_participant_count", failing_get_participant_count)
    monkeypatch.setattr(
        cli, "diagnose_jitsi_access", lambda url: DiagnosisResult(ws_domain=url)  # noqa: ARG005
    )

    result = runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert result.exit_code == 1
    assert "boom" in result.output


def test_participants_prints_indented_json(monkeypatch: pytest.MonkeyPatch) -> None:
    people = [Participant(jid="room@muc.example.com/alice", nick="alice", name="Alice")]
    monkeypatch.setattr(cli, "get_participants", lambda url, name: people)  # noqa: ARG005

    result = runner.invoke(cli.app, ["participants", "https://meet.example.com/room"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [
        {
            "jid": "room@muc.example.com/alice",
            "nick": "alice",
            "name": "Alice",
            "role": None,
            "affiliation": None,
            "real_jid": None,
            "occupant_id": None,
        }
    ]
    assert result.stdout.count("\n") > 1  # indented, not a single compact line


def test_participants_accepts_name_option(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participants(_url: str, name: str) -> list[Participant]:
        seen["name"] = name
        return []

    monkeypatch.setattr(cli, "get_participants", fake_get_participants)

    runner.invoke(cli.app, ["participants", "--name", "Bob", "https://meet.example.com/room"])

    assert seen["name"] == "Bob"


def test_participants_reports_failure_and_runs_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_get_participants(_url: str, name: str) -> list[Participant]:  # noqa: ARG001
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "get_participants", failing_get_participants)
    monkeypatch.setattr(
        cli, "diagnose_jitsi_access", lambda url: DiagnosisResult(ws_domain=url)  # noqa: ARG005
    )

    result = runner.invoke(cli.app, ["participants", "https://meet.example.com/room"])

    assert result.exit_code == 1
    assert "boom" in result.output


def test_diagnose_prints_json_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "diagnose_jitsi_access",
        lambda url: DiagnosisResult(ws_domain=url, anonymous_login_ok=True),  # noqa: ARG005
    )

    result = runner.invoke(cli.app, ["diagnose", "https://meet.example.com/room"])

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["ws_domain"] == "https://meet.example.com/room"
    assert report["anonymous_login_ok"] is True


def test_created_exits_0_when_the_room_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: True)  # noqa: ARG005

    result = runner.invoke(cli.app, ["created", "https://meet.example.com/room"])

    assert result.exit_code == 0
    assert result.output == ""


def test_created_exits_1_when_the_room_does_not_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: False)  # noqa: ARG005

    result = runner.invoke(cli.app, ["created", "https://meet.example.com/room"])

    assert result.exit_code == 1
    assert result.output == ""


def test_created_exits_2_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_is_room_created(_url: str) -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "is_room_created", failing_is_room_created)

    result = runner.invoke(cli.app, ["created", "https://meet.example.com/room"])

    assert result.exit_code == 2  # noqa: PLR2004
    assert "boom" in result.output


def test_created_json_prints_true_and_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: True)  # noqa: ARG005

    result = runner.invoke(cli.app, ["created", "--json", "https://meet.example.com/room"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "true"


def test_created_json_prints_false_and_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: False)  # noqa: ARG005

    result = runner.invoke(cli.app, ["created", "--json", "https://meet.example.com/room"])

    assert result.exit_code == 1
    assert result.stdout.strip() == "false"


def test_created_json_reports_error_and_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_is_room_created(_url: str) -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "is_room_created", failing_is_room_created)

    result = runner.invoke(cli.app, ["created", "--json", "https://meet.example.com/room"])

    assert result.exit_code == 2  # noqa: PLR2004
    assert json.loads(result.output)["error"] == "boom"
