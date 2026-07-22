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
    monkeypatch.setattr(cli, "get_participant_count", lambda url: 3)  # noqa: ARG005

    result = runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "3"


def test_count_reports_failure_and_runs_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_get_participant_count(_url: str) -> int:
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
    monkeypatch.setattr(cli, "get_participants", lambda url: people)  # noqa: ARG005

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


def test_participants_reports_failure_and_runs_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_get_participants(_url: str) -> list[Participant]:
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
