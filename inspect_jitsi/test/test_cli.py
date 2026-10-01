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
import re

import pytest

typer = pytest.importorskip("typer")
from typer.testing import CliRunner  # noqa: E402

from inspect_jitsi import cli  # noqa: E402
from inspect_jitsi.xmpp.diagnosis import DiagnosisResult  # noqa: E402
from inspect_jitsi.xmpp.participant import Participant  # noqa: E402

runner = CliRunner()


def test_count_prints_the_participant_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "get_participant_count", lambda url, name, avatar_url: 3)

    result = runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "3"


def test_count_defaults_to_inspect_jitsi_name(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str, avatar_url: str | None) -> int:
        seen["name"] = name
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)

    runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert seen["name"] == "inspect-jitsi"


def test_count_accepts_name_option(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str, avatar_url: str | None) -> int:
        seen["name"] = name
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)

    runner.invoke(
        cli.app, ["count", "--name", "Alice", "https://meet.example.com/room"]
    )

    assert seen["name"] == "Alice"


def test_count_accepts_name_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str, avatar_url: str | None) -> int:
        seen["name"] = name
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)
    monkeypatch.setenv("INSPECT_JITSI_NAME", "FromEnv")

    runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert seen["name"] == "FromEnv"


def test_count_reports_failure_and_runs_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_get_participant_count(
        _url: str, name: str, avatar_url: str | None
    ) -> int:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "get_participant_count", failing_get_participant_count)
    monkeypatch.setattr(
        cli,
        "diagnose_jitsi_access",
        lambda url: DiagnosisResult(ws_domain=url),
    )

    result = runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert result.exit_code == 1
    assert "boom" in result.output


def test_participants_prints_indented_json(monkeypatch: pytest.MonkeyPatch) -> None:
    people = [Participant(jid="room@muc.example.com/alice", nick="alice", name="Alice")]
    monkeypatch.setattr(cli, "get_participants", lambda url, name, avatar_url: people)

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
            "email": None,
            "avatar_url": None,
        }
    ]
    assert result.stdout.count("\n") > 1  # indented, not a single compact line


def test_participants_accepts_name_option(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participants(
        _url: str, name: str, avatar_url: str | None
    ) -> list[Participant]:
        seen["name"] = name
        return []

    monkeypatch.setattr(cli, "get_participants", fake_get_participants)

    runner.invoke(
        cli.app, ["participants", "--name", "Bob", "https://meet.example.com/room"]
    )

    assert seen["name"] == "Bob"


def test_participants_reports_failure_and_runs_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_get_participants(
        _url: str, name: str, avatar_url: str | None
    ) -> list[Participant]:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "get_participants", failing_get_participants)
    monkeypatch.setattr(
        cli,
        "diagnose_jitsi_access",
        lambda url: DiagnosisResult(ws_domain=url),
    )

    result = runner.invoke(cli.app, ["participants", "https://meet.example.com/room"])

    assert result.exit_code == 1
    assert "boom" in result.output


def test_diagnose_prints_json_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "diagnose_jitsi_access",
        lambda url: DiagnosisResult(ws_domain=url, anonymous_login_ok=True),
    )

    result = runner.invoke(cli.app, ["diagnose", "https://meet.example.com/room"])

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["ws_domain"] == "https://meet.example.com/room"
    assert report["anonymous_login_ok"] is True


def test_created_exits_0_when_the_room_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: True)

    result = runner.invoke(cli.app, ["created", "https://meet.example.com/room"])

    assert result.exit_code == 0
    assert result.output == ""


def test_created_exits_1_when_the_room_does_not_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: False)

    result = runner.invoke(cli.app, ["created", "https://meet.example.com/room"])

    assert result.exit_code == 1
    assert result.output == ""


def test_created_exits_2_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_is_room_created(_url: str) -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "is_room_created", failing_is_room_created)

    result = runner.invoke(cli.app, ["created", "https://meet.example.com/room"])

    assert result.exit_code == 2
    assert "boom" in result.output


def test_created_json_prints_true_and_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: True)

    result = runner.invoke(
        cli.app, ["created", "--json", "https://meet.example.com/room"]
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "true"


def test_created_json_prints_false_and_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "is_room_created", lambda url: False)

    result = runner.invoke(
        cli.app, ["created", "--json", "https://meet.example.com/room"]
    )

    assert result.exit_code == 1
    assert result.stdout.strip() == "false"


def test_created_json_reports_error_and_exits_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_is_room_created(_url: str) -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "is_room_created", failing_is_room_created)

    result = runner.invoke(
        cli.app, ["created", "--json", "https://meet.example.com/room"]
    )

    assert result.exit_code == 2
    assert json.loads(result.output)["error"] == "boom"


def test_count_accepts_avatar_option(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    seen = {}
    image = tmp_path / "a.png"
    image.write_bytes(
        bytes.fromhex("89504e470d0a1a0a")
    )  # PNG signature, enough to sniff

    def fake_get_participant_count(_url: str, name: str, avatar_url: str | None) -> int:
        seen["avatar_url"] = avatar_url
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)

    result = runner.invoke(
        cli.app,
        ["count", "--avatar", str(image), "https://meet.example.com/room"],
    )

    assert result.exit_code == 0
    assert seen["avatar_url"] == "data:image/png;base64,iVBORw0KGgo="


def test_count_rejects_a_missing_avatar_file(monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(
        cli.app,
        ["count", "--avatar", "/no/such/file.png", "https://meet.example.com/room"],
    )

    assert result.exit_code == 2
    assert result.stdout == ""


def test_count_rejects_an_unsupported_avatar_file(tmp_path) -> None:
    not_an_image = tmp_path / "notes.txt"
    not_an_image.write_text("hello")

    result = runner.invoke(
        cli.app,
        ["count", "--avatar", str(not_an_image), "https://meet.example.com/room"],
    )

    assert result.exit_code == 2
    assert "does not look like a supported image" in result.stderr


def test_participants_accepts_avatar_option(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    seen = {}
    image = tmp_path / "a.png"
    image.write_bytes(bytes.fromhex("89504e470d0a1a0a"))

    def fake_get_participants(
        _url: str, name: str, avatar_url: str | None
    ) -> list[Participant]:
        seen["avatar_url"] = avatar_url
        return []

    monkeypatch.setattr(cli, "get_participants", fake_get_participants)

    runner.invoke(
        cli.app,
        ["participants", "--avatar", str(image), "https://meet.example.com/room"],
    )

    assert seen["avatar_url"] == "data:image/png;base64,iVBORw0KGgo="


def test_avatar_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    seen = {}
    image = tmp_path / "a.png"
    image.write_bytes(bytes.fromhex("89504e470d0a1a0a"))

    def fake_get_participant_count(_url: str, name: str, avatar_url: str | None) -> int:
        seen["avatar_url"] = avatar_url
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)
    monkeypatch.setenv("INSPECT_JITSI_AVATAR", str(image))

    runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert seen["avatar_url"] == "data:image/png;base64,iVBORw0KGgo="


def test_default_avatar_is_the_logo(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str, avatar_url: str | None) -> int:
        seen["avatar_url"] = avatar_url
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)

    runner.invoke(cli.app, ["count", "https://meet.example.com/room"])

    assert seen["avatar_url"].startswith("data:image/svg+xml;base64,")


def test_no_avatar_option_discloses_no_avatar(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    def fake_get_participant_count(_url: str, name: str, avatar_url: str | None) -> int:
        seen["avatar_url"] = avatar_url
        return 0

    monkeypatch.setattr(cli, "get_participant_count", fake_get_participant_count)

    result = runner.invoke(
        cli.app, ["count", "--no-avatar", "https://meet.example.com/room"]
    )

    assert result.exit_code == 0
    assert seen["avatar_url"] is None


def test_avatar_and_no_avatar_conflict(tmp_path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    result = runner.invoke(
        cli.app,
        [
            "count",
            "--avatar",
            str(image),
            "--no-avatar",
            "https://meet.example.com/room",
        ],
    )
    assert result.exit_code == 2


def test_shell_completion_is_available_on_every_command() -> None:
    """Completion must work out of the box - `add_completion` defaults to
    True, but this pins it down so a future refactor can't flip it back."""
    # CI may force colour, and rich then styles the dashes separately from the
    # option name - compare the text without the escape codes.
    root_help = re.sub(r"\x1b\[[0-9;]*m", "", runner.invoke(cli.app, ["--help"]).stdout)
    assert "--install-completion" in root_help
    assert "--show-completion" in root_help

    for command in ["count", "participants", "diagnose", "created", "monitor"]:
        result = runner.invoke(cli.app, [command, "--help"])
        assert result.exit_code == 0  # a command-level --help still works


@pytest.mark.parametrize("command", ["count", "participants"])
def test_avatar_accepts_a_url(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    seen = {}
    url = "https://example.com/me.png"

    def fake(_url: str, name: str, avatar_url: str | None):
        seen["avatar_url"] = avatar_url
        return 0 if command == "count" else []

    monkeypatch.setattr(
        cli, "get_participant_count" if command == "count" else "get_participants", fake
    )

    result = runner.invoke(
        cli.app, [command, "--avatar", url, "https://meet.example.com/room"]
    )

    assert result.exit_code == 0
    assert seen["avatar_url"] == url


def test_avatar_url_and_file_both_work(tmp_path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(bytes.fromhex("89504e470d0a1a0a"))

    assert cli._avatar_url("http://example.com/a.jpg", False) == (  # noqa: SLF001
        "http://example.com/a.jpg"
    )
    assert cli._avatar_url(str(image), False) == (  # noqa: SLF001
        "data:image/png;base64,iVBORw0KGgo="
    )
