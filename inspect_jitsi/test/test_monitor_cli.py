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
"""End-to-end checks of the `inspect-jitsi monitor` command's behaviour:
output streams, exit codes, options and help - through the real command, on
top of a fake XMPP server."""

from __future__ import annotations

import json

import pytest

typer = pytest.importorskip("typer")
from typer.testing import CliRunner  # noqa: E402

from inspect_jitsi import cli  # noqa: E402
from inspect_jitsi.test.conftest import (  # noqa: E402
    CONFERENCE_URL,
    FakeConnect,
    FakeWebSocket,
    RefusedConnect,
    forbidden_disco_error,
    handshake_script,
    join_script,
    occupant_presence,
    room_not_found_disco_error,
    unavailable_presence,
)
from inspect_jitsi.xmpp import monitor as monitor_module  # noqa: E402
from inspect_jitsi.xmpp.connection import DEFAULT_NAME  # noqa: E402

runner = CliRunner()
NICK = "inspect-jitsi-abcdef01"


@pytest.fixture
def fake_deployment(monkeypatch: pytest.MonkeyPatch, fake_config_js):
    """A fake server; `add(*stanzas)` queues one connection (after which
    connecting is refused). Diagnostics are stubbed so nothing hits the network."""
    import inspect_jitsi.xmpp.connection as connection_module

    queue: list[FakeWebSocket] = []

    class FixedUuid:
        hex = "abcdef0123456789"

    def connect(*_args, **_kwargs) -> FakeConnect | RefusedConnect:
        if not queue:
            return RefusedConnect()
        return FakeConnect(queue.pop(0))

    monkeypatch.setattr(connection_module.websockets, "connect", connect)
    monkeypatch.setattr(connection_module.uuid, "uuid4", FixedUuid)
    monkeypatch.setattr(monitor_module, "_INITIAL_RETRY_DELAY", 0.005)
    monkeypatch.setattr(monitor_module, "_MAX_RETRY_DELAY", 0.01)
    monkeypatch.setattr(
        cli,
        "diagnose_jitsi_access",
        lambda _url: type("D", (), {"to_dict": lambda _s: {"diagnosed": True}})(),
    )

    def add(*stanzas: object, exists: bool = True) -> FakeWebSocket:
        """Queue the existence check, then (if it exists) a join."""
        reply = forbidden_disco_error() if exists else room_not_found_disco_error()
        queue.append(FakeWebSocket([*handshake_script(), reply]))
        ws = FakeWebSocket([*handshake_script(), *stanzas])
        if exists:
            queue.append(ws)
        return ws

    return add


def parse_lines(stdout: str) -> list[dict]:
    assert stdout == "" or stdout.endswith("\n")
    lines = stdout.splitlines()
    assert all(line.strip() == line and line for line in lines)  # no blank/padded
    return [json.loads(line) for line in lines]  # every line is JSON, alone


def test_room_closing_prints_json_lines_only_and_exits_0(fake_deployment) -> None:
    ws = fake_deployment(
        *join_script(NICK, ("alice",)),
        occupant_presence("bob"),
        unavailable_presence("focus"),
    )

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 0, result.stderr
    assert result.stderr == ""
    states = parse_lines(result.stdout)
    assert states[-1]["status"] == {"open": False, "attempts": 0}
    assert [p["nick"] for p in states[-1]["participants"]] == ["alice", "bob"]
    assert all(list(s) == ["room", "participants", "status"] for s in states)
    assert any('type="unavailable"' in s for s in ws.sent)  # left the room


def test_default_and_explicit_name_are_disclosed(fake_deployment) -> None:
    ws1 = fake_deployment(*join_script(NICK), unavailable_presence("focus"))
    runner.invoke(cli.app, ["monitor", CONFERENCE_URL])
    ws2 = fake_deployment(*join_script(NICK), unavailable_presence("focus"))
    runner.invoke(cli.app, ["monitor", CONFERENCE_URL, "--name", "Watcher <1>"])

    assert f">{DEFAULT_NAME}</nick>" in "".join(ws1.sent)
    assert ">Watcher &lt;1&gt;</nick>" in "".join(ws2.sent)


def test_name_from_environment(fake_deployment, monkeypatch) -> None:
    monkeypatch.setenv("INSPECT_JITSI_NAME", "FromEnv")
    ws = fake_deployment(*join_script(NICK), unavailable_presence("focus"))

    runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert ">FromEnv</nick>" in "".join(ws.sent)


def test_unreachable_server_exits_1_with_nothing_on_stdout(fake_deployment) -> None:
    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Failed to monitor the room" in result.stderr
    assert '"diagnosed": true' in result.stderr


def test_giving_up_after_the_timeout_exits_1(fake_deployment) -> None:
    from websockets.exceptions import ConnectionClosedError

    fake_deployment(*join_script(NICK, ("alice",)), ConnectionClosedError(None, None))

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL, "--timeout", "0.1"])

    assert result.exit_code == 1
    states = parse_lines(result.stdout)  # what was printed before is still JSON
    attempts = [s["status"]["attempts"] for s in states]
    assert attempts[0] == 0
    assert attempts == list(range(len(attempts)))
    assert all(s["status"]["open"] for s in states)
    assert "could not reconnect within 0.1s" in result.stderr


def test_timeout_zero_does_not_reconnect(fake_deployment) -> None:
    from websockets.exceptions import ConnectionClosedError

    fake_deployment(*join_script(NICK, ("alice",)), ConnectionClosedError(None, None))

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL, "--timeout", "0"])

    assert result.exit_code == 1
    assert [s["status"]["attempts"] for s in parse_lines(result.stdout)] == [0]


def test_reconnect_prints_attempts_and_continues(fake_deployment) -> None:
    from websockets.exceptions import ConnectionClosedError

    fake_deployment(*join_script(NICK, ("alice",)), ConnectionClosedError(None, None))
    fake_deployment(*join_script(NICK, ("alice",)), unavailable_presence("focus"))

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 0
    assert [s["status"] for s in parse_lines(result.stdout)] == [
        {"open": True, "attempts": 0},
        {"open": True, "attempts": 1},
        {"open": False, "attempts": 1},
    ]


@pytest.mark.parametrize(
    "args",
    [
        ["monitor", "https://meet.example.com"],
        ["monitor", "https://meet.example.com/"],
        ["monitor", ""],
        ["monitor", CONFERENCE_URL, "--timeout", "-1"],
        ["monitor", CONFERENCE_URL, "--timeout", "soon"],
        ["monitor"],
    ],
)
def test_bad_input_exits_2_with_nothing_on_stdout(fake_deployment, args) -> None:
    result = runner.invoke(cli.app, args)

    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr != ""


def test_ctrl_c_exits_130_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    async def interrupted(*_args, **_kwargs):
        yield {"status": {"open": True, "attempts": 0}}
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "monitor_conference", interrupted)

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 130
    assert len(parse_lines(result.stdout)) == 1
    assert result.stderr == ""


def test_closed_stdout_exits_130_quietly(monkeypatch: pytest.MonkeyPatch) -> None:
    async def endless(*_args, **_kwargs):
        yield {"a": 1}

    monkeypatch.setattr(cli, "monitor_conference", endless)
    monkeypatch.setattr(
        cli.typer, "echo", lambda *_a, **_k: (_ for _ in ()).throw(BrokenPipeError)
    )

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 130
    assert result.stderr == ""


@pytest.mark.parametrize(
    ("args", "env", "expected"),
    [
        ([], {}, 60),
        (["--timeout", "5"], {}, 5),
        ([], {"INSPECT_JITSI_TIMEOUT": "7.5"}, 7.5),
        (["--timeout", "5"], {"INSPECT_JITSI_TIMEOUT": "7"}, 5),  # flag beats env
        (["--timeout", "0"], {}, 0),
    ],
)
def test_timeout_flag_environment_and_default(
    monkeypatch: pytest.MonkeyPatch, args, env, expected
) -> None:
    seen = {}

    async def fake(_url, *, timeout, **_kwargs):
        seen["timeout"] = timeout
        return
        yield

    monkeypatch.setattr(cli, "monitor_conference", fake)

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL, *args], env=env)

    assert result.exit_code == 0
    assert seen["timeout"] == expected


def test_help_links_to_the_docs_page_and_lists_the_options() -> None:
    result = runner.invoke(cli.app, ["monitor", "--help"])

    assert result.exit_code == 0
    flat = "".join(result.stdout.split())
    assert "how-to/monitor-a-conference.html" in flat
    assert "--name" in result.stdout
    assert "--timeout" in result.stdout
    assert "INSPECT_JITSI_TIMEOUT" in result.stdout
    assert "INSPECT_JITSI_NAME" in result.stdout
    assert "monitor" in runner.invoke(cli.app, ["--help"]).stdout


def test_stdout_is_written_line_by_line_as_things_happen(monkeypatch) -> None:
    """Each state is echoed as soon as it is yielded (not batched until exit),
    so a consumer reading a pipe sees changes live."""
    order: list[str] = []

    async def fake(*_args, **_kwargs):
        order.append("yield 1")
        yield {"n": 1}
        order.append("yield 2")
        yield {"n": 2}

    monkeypatch.setattr(cli, "monitor_conference", fake)
    monkeypatch.setattr(
        cli.typer, "echo", lambda text, **_k: order.append(f"echo {text}")
    )

    runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert order == ["yield 1", 'echo {"n": 1}', "yield 2", 'echo {"n": 2}']


def test_missing_room_prints_one_closed_line_and_exits_0(fake_deployment) -> None:
    fake_deployment(exists=False)

    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 0
    assert result.stderr == ""
    (state,) = parse_lines(result.stdout)
    assert state["status"] == {"open": False, "attempts": 0}
    assert state["participants"] == []


def test_alone_in_the_room_leaves_by_default_and_stays_with_stay(
    fake_deployment,
) -> None:
    ws = fake_deployment(*join_script(NICK))
    result = runner.invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 0
    assert [s["status"]["open"] for s in parse_lines(result.stdout)] == [False]
    assert any('type="unavailable"' in s for s in ws.sent)


def test_stay_and_create_are_passed_on(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = []

    async def fake(_url, **options):
        seen.append(options)
        return
        yield

    monkeypatch.setattr(cli, "monitor_conference", fake)

    runner.invoke(cli.app, ["monitor", CONFERENCE_URL])
    runner.invoke(cli.app, ["monitor", CONFERENCE_URL, "--create", "--stay"])

    assert [(o["create"], o["stay"]) for o in seen] == [(False, False), (True, True)]


def test_help_describes_create_and_stay() -> None:
    out = runner.invoke(cli.app, ["monitor", "--help"]).stdout
    assert "--create" in out
    assert "--stay" in out
