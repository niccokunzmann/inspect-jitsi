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
"""Tests for `monitor_conference` and the `inspect-jitsi monitor` command."""

from __future__ import annotations

import io
import json

import pytest
from websockets.exceptions import ConnectionClosedError

from inspect_jitsi.test.conftest import (
    CONFERENCE_URL,
    MUC_DOMAIN,
    ROOM_JID,
    XMPP_DOMAIN,
    FakeConnect,
    FakeWebSocket,
    RefusedConnect,
    forbidden_disco_error,
    handshake_script,
    join_script,
    occupant_presence,
    room_creation_restricted_presence,
    unavailable_presence,
)
from inspect_jitsi.xmpp import JitsiConnectionError, monitor_conference

pytest.importorskip("typer")
from typer.testing import CliRunner

from inspect_jitsi import cli

DROPPED = ConnectionClosedError(None, None)


@pytest.fixture
def sessions(monkeypatch: pytest.MonkeyPatch):
    """Hand out one scripted fake WebSocket per connection attempt."""
    import inspect_jitsi.xmpp.connection as connection_module

    queue: list[FakeWebSocket] = []

    def connect(*_args, **_kwargs) -> FakeConnect | RefusedConnect:
        if not queue:
            return RefusedConnect()
        return FakeConnect(queue.pop(0))

    monkeypatch.setattr(connection_module.websockets, "connect", connect)

    def add(*script: object) -> FakeWebSocket:
        # Every join is preceded by a check that the room exists.
        queue.append(FakeWebSocket([*handshake_script(), forbidden_disco_error()]))
        ws = FakeWebSocket([*handshake_script(), *script])
        queue.append(ws)
        return ws

    return add


async def collect(**kwargs) -> list[dict]:
    kwargs.setdefault("stay", True)  # these rooms have nobody else in them
    return [
        state
        async for state in monitor_conference(
            CONFERENCE_URL,
            nick="probe",
            anonymous_domain=XMPP_DOMAIN,
            muc_domain=MUC_DOMAIN,
            connect_timeout=1,
            **kwargs,
        )
    ]


async def test_reports_changes_until_focus_leaves(sessions) -> None:
    sessions(
        *join_script("probe", ("alice",)),
        occupant_presence("bob"),
        unavailable_presence("alice"),
        unavailable_presence("focus"),
    )

    states = await collect()

    # Changes that arrive together are reported as one line.
    assert [[p["nick"] for p in s["participants"]] for s in states] == [
        ["alice"],
        ["bob"],
    ]
    assert [s["status"] for s in states] == [
        {"open": True, "attempts": 0},
        {"open": False, "attempts": 0},
    ]
    assert states[0]["room"]["jid"] == ROOM_JID
    assert states[0].keys() == states[1].keys()


async def test_nonexistent_room_is_closed_immediately(sessions) -> None:
    sessions(room_creation_restricted_presence("probe"))

    states = await collect()

    assert len(states) == 1
    assert states[0]["status"] == {"open": False, "attempts": 0}
    assert states[0]["participants"] == []


async def test_reconnect_only_increases_attempts(sessions) -> None:
    sessions(*join_script("probe", ("alice",)), DROPPED)
    sessions(*join_script("probe", ("alice",)), unavailable_presence("focus"))

    states = await collect(timeout=5)

    assert [s["status"] for s in states] == [
        {"open": True, "attempts": 0},
        {"open": True, "attempts": 1},
        {"open": False, "attempts": 1},
    ]
    assert all([p["nick"] for p in s["participants"]] == ["alice"] for s in states)


async def test_gives_up_after_timeout(sessions) -> None:
    sessions(*join_script("probe"), DROPPED)

    with pytest.raises(JitsiConnectionError, match="could not reconnect"):
        await collect(timeout=0.01)


async def test_no_reconnect_with_zero_timeout(sessions) -> None:
    sessions(*join_script("probe"), DROPPED)

    with pytest.raises(JitsiConnectionError):
        await collect(timeout=0)


def test_cli_prints_one_json_line_per_change(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    async def fake_monitor(url: str, *, name: str, timeout: float, **_options):
        seen.update(url=url, name=name, timeout=timeout)
        yield {"status": {"open": True, "attempts": 0}}
        yield {"status": {"open": False, "attempts": 0}}

    monkeypatch.setattr(cli, "monitor_conference", fake_monitor)

    result = CliRunner().invoke(
        cli.app, ["monitor", CONFERENCE_URL, "--name", "Bot", "--timeout", "5"]
    )

    assert result.exit_code == 0
    assert [
        json.loads(line)["status"]["open"] for line in result.stdout.splitlines()
    ] == [
        True,
        False,
    ]
    assert seen == {"url": CONFERENCE_URL, "name": "Bot", "timeout": 5}


def test_cli_timeout_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}

    async def fake_monitor(_url: str, *, name: str, timeout: float, **_options):
        seen["timeout"] = timeout
        return
        yield

    monkeypatch.setattr(cli, "monitor_conference", fake_monitor)
    monkeypatch.setenv("INSPECT_JITSI_TIMEOUT", "7")

    CliRunner().invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert seen["timeout"] == 7


def test_cli_invalid_url_exits_2() -> None:
    result = CliRunner().invoke(cli.app, ["monitor", "https://meet.example.com"])

    assert result.exit_code == 2


def test_cli_stdout_is_only_json_even_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_monitor(_url: str, **_kwargs):
        yield {"status": {"open": True, "attempts": 0}}
        msg = "gone"
        raise JitsiConnectionError(msg)

    monkeypatch.setattr(cli, "monitor_conference", failing_monitor)
    monkeypatch.setattr(
        cli,
        "diagnose_jitsi_access",
        lambda _url: type("D", (), {"to_dict": lambda _self: {}})(),
    )

    result = CliRunner().invoke(cli.app, ["monitor", CONFERENCE_URL])

    assert result.exit_code == 1
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        {"status": {"open": True, "attempts": 0}}
    ]
    assert "gone" in result.stderr


def test_cli_each_json_is_one_line(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_monitor(_url: str, **_kwargs):
        yield {"participants": [{"name": "multi\nline\rname"}]}
        yield {"participants": []}

    monkeypatch.setattr(cli, "monitor_conference", fake_monitor)

    result = CliRunner().invoke(cli.app, ["monitor", CONFERENCE_URL])

    # Parseable the way `input()`/`readline()` consume it: one document per line.
    stream = io.StringIO(result.stdout)
    first, second = json.loads(stream.readline()), json.loads(stream.readline())
    assert stream.readline() == ""
    assert first["participants"][0]["name"] == "multi\nline\rname"
    assert second["participants"] == []


def test_monitor_room_is_a_blocking_iterator(sessions) -> None:
    from inspect_jitsi import monitor_room

    sessions(
        *join_script("probe", ("alice",)),
        unavailable_presence("focus"),
    )

    states = list(
        monitor_room(
            CONFERENCE_URL,
            nick="probe",
            anonymous_domain=XMPP_DOMAIN,
            muc_domain=MUC_DOMAIN,
            connect_timeout=1,
        )
    )

    assert [s["status"]["open"] for s in states][-1] is False
    assert [p["nick"] for p in states[-1]["participants"]] == ["alice"]


def test_monitor_room_leaves_when_stopped_early(sessions) -> None:
    from inspect_jitsi import monitor_room

    ws = sessions(*join_script("probe", ("alice",)))

    states = monitor_room(
        CONFERENCE_URL,
        nick="probe",
        anonymous_domain=XMPP_DOMAIN,
        muc_domain=MUC_DOMAIN,
        connect_timeout=1,
    )
    assert next(states)["status"]["open"] is True
    states.close()

    assert ws.closed
    assert any('type="unavailable"' in s for s in ws.sent)


async def test_participants_keep_their_order_and_may_share_a_name(sessions) -> None:
    def named(nick: str, name: str) -> str:
        return occupant_presence(nick).replace(
            "</presence>",
            f"<nick xmlns='http://jabber.org/protocol/nick'>{name}</nick></presence>",
        )

    sessions(
        *join_script("probe"),
        named("a", "Sam"),
        named("b", "Sam"),
        named("c", "Kim"),
        unavailable_presence("b"),
        named("a", "Sam"),  # an update must not move "a"
        occupant_presence("b"),  # rejoining goes to the end
        unavailable_presence("focus"),
    )

    states = await collect()

    assert [p["nick"] for p in states[-1]["participants"]] == ["a", "c", "b"]
    assert [p["name"] for p in states[-1]["participants"]] == ["Sam", "Kim", None]
