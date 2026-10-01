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
"""Checks of every claim made about `inspect-jitsi monitor` (see the docs page).

A scripted fake server that is fed stanzas one at a time lets these tests say
exactly what is printed (and what is *not* printed) after each event.
"""
# ruff: noqa: SLF001, S311  - white-box checks of private state, seeded randomness

from __future__ import annotations

import asyncio
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Self

import pytest
from websockets.exceptions import ConnectionClosedError

from inspect_jitsi import monitor_room
from inspect_jitsi.test.conftest import (
    CONFERENCE_URL,
    MUC_DOMAIN,
    ROOM_JID,
    XMPP_DOMAIN,
    FakeConnect,
    FakeWebSocket,
    RefusedConnect,
    error_presence,
    focus_presence,
    forbidden_disco_error,
    handshake_script,
    join_script,
    room_creation_restricted_presence,
    room_not_found_disco_error,
    sasl_failure,
    self_presence,
    stream_features_mechanisms,
    stream_open,
    unavailable_presence,
)
from inspect_jitsi.xmpp import JitsiConnectionError, JitsiXmppConnection
from inspect_jitsi.xmpp import monitor as monitor_module
from inspect_jitsi.xmpp.monitor import _state, monitor_conference

NICK = "probe"
END = object()
DROPPED = ConnectionClosedError(None, None)


class ControlledWS(FakeWebSocket):
    """A fake WebSocket: the handshake/join `script` first, then whatever the
    test `push()`es later (an exception instance is raised by `recv()`)."""

    def __init__(self, script: list = (), *, handshake: bool = True) -> None:
        super().__init__([*(handshake_script() if handshake else ()), *script])
        self.queue: asyncio.Queue = asyncio.Queue()

    def push(self, *items: object) -> None:
        for item in items:
            self.queue.put_nowait(item)

    async def recv(self) -> str:
        if self._script:
            return await super().recv()
        item = await self.queue.get()
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture
def server(monkeypatch: pytest.MonkeyPatch):
    """`server.add(*join_stanzas)` queues one connection; once they are used
    up, connecting is refused. `server.connects` counts the attempts."""
    import inspect_jitsi.xmpp.connection as connection_module

    class Server:
        def __init__(self) -> None:
            self.queue: list[ControlledWS] = []
            self.connects = 0  # joins, not counting existence checks

        def add(self, *script: object, exists: bool = True) -> ControlledWS:
            """Queue an existence check (answering `exists`), then, if the
            room exists, a connection joining it with `script`."""
            reply = forbidden_disco_error() if exists else room_not_found_disco_error()
            check = ControlledWS([reply])
            check.is_check = True
            self.queue.append(check)
            ws = ControlledWS(list(script))
            if exists:
                self.queue.append(ws)
            return ws

    srv = Server()

    def connect(*_args, **_kwargs) -> FakeConnect:
        if not srv.queue:
            return RefusedConnect()
        ws = srv.queue.pop(0)
        if not getattr(ws, "is_check", False):
            srv.connects += 1
        return FakeConnect(ws)

    monkeypatch.setattr(connection_module.websockets, "connect", connect)
    monkeypatch.setattr(monitor_module, "_INITIAL_RETRY_DELAY", 0.005)
    monkeypatch.setattr(monitor_module, "_MAX_RETRY_DELAY", 0.01)
    return srv


class Feed:
    """Pulls states from `monitor_conference` one at a time, without ever
    cancelling the generator when nothing arrives in time."""

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("timeout", 5)
        kwargs.setdefault("connect_timeout", 1)
        kwargs.setdefault("stay", True)  # most tests start in an empty room
        self.agen = monitor_conference(
            CONFERENCE_URL,
            nick=NICK,
            anonymous_domain=XMPP_DOMAIN,
            muc_domain=MUC_DOMAIN,
            **kwargs,
        )
        self.task: asyncio.Future | None = None

    async def next(self, timeout: float = 1) -> dict | object:
        """The next state, END if the monitor finished; TimeoutError if none."""
        if self.task is None:
            self.task = asyncio.ensure_future(anext(self.agen))
        done, _ = await asyncio.wait([self.task], timeout=timeout)
        if not done:
            raise TimeoutError
        task, self.task = self.task, None
        try:
            return task.result()
        except StopAsyncIteration:
            return END

    async def quiet(self, timeout: float = 0.02) -> None:
        with pytest.raises(TimeoutError):
            await self.next(timeout)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self.task is not None and not self.task.done():
            self.task.cancel()
            await asyncio.wait([self.task])
        await self.agen.aclose()


def nicks(state: dict) -> list[str]:
    return [p["nick"] for p in state["participants"]]


def presence(nick: str, *, role: str = "participant", name: str | None = None) -> str:
    nick_element = (
        f"<nick xmlns='http://jabber.org/protocol/nick'>{name}</nick>" if name else ""
    )
    return (
        f"<presence xmlns='jabber:client' from='{ROOM_JID}/{nick}'>"
        "<x xmlns='http://jabber.org/protocol/muc#user'>"
        f"<item affiliation='member' role='{role}'/></x>{nick_element}</presence>"
    )


def without_attempts(state: dict) -> dict:
    return {**state, "status": {**state["status"], "attempts": None}}


# --- what is printed when -------------------------------------------------


async def test_first_state_is_printed_on_connect_with_the_documented_schema(
    server,
) -> None:
    server.add(*join_script(NICK, ("alice",)))

    async with Feed() as feed:
        state = await feed.next()

    assert list(state) == ["room", "participants", "status"]
    assert state["room"] == {
        "name": "testroom",
        "url": CONFERENCE_URL,
        "domain": "meet.example.com",
        "muc_domain": MUC_DOMAIN,
        "jid": ROOM_JID,
    }
    assert state["status"] == {"open": True, "attempts": 0}
    assert nicks(state) == ["alice"]
    assert set(state["participants"][0]) == {
        "jid",
        "nick",
        "name",
        "role",
        "affiliation",
        "real_jid",
        "occupant_id",
        "email",
        "avatar_url",
    }


async def test_empty_room_prints_an_empty_list(server) -> None:
    server.add(*join_script(NICK))

    async with Feed() as feed:
        state = await feed.next()

    assert state["participants"] == []
    assert state["status"]["open"] is True


@pytest.mark.parametrize(
    "stanza",
    [
        presence("alice"),  # identical to what we already know
        "<message xmlns='jabber:client' from='x@y'><body>hi</body></message>",
        "<iq xmlns='jabber:client' type='result' id='x'/>",
        error_presence("alice"),
        focus_presence(),  # focus (re)appearing is not a change
        presence("alice", role="participant"),
    ],
    ids=["same-presence", "message", "iq", "error-presence", "focus", "again"],
)
async def test_nothing_is_printed_when_nothing_changed(server, stanza: str) -> None:
    ws = server.add(*join_script(NICK, ("alice",)))

    async with Feed() as feed:
        await feed.next()
        ws.push(stanza)
        await feed.quiet()
        # ... and the monitor is still alive and reacting afterwards.
        ws.push(presence("bob"))
        assert nicks(await feed.next()) == ["alice", "bob"]


async def test_join_update_and_leave_each_print_exactly_one_line(
    server,
) -> None:
    ws = server.add(*join_script(NICK))

    async with Feed() as feed:
        assert nicks(await feed.next()) == []

        ws.push(presence("a", name="Ann"))
        assert [p["name"] for p in (await feed.next())["participants"]] == ["Ann"]
        await feed.quiet()

        ws.push(presence("a", name="Ann", role="moderator"))
        state = await feed.next()
        assert [p["role"] for p in state["participants"]] == ["moderator"]
        await feed.quiet()

        ws.push(unavailable_presence("a"))
        assert (await feed.next())["participants"] == []
        await feed.quiet()


async def test_the_monitor_itself_and_focus_are_never_listed(
    server,
) -> None:
    ws = server.add(*join_script(NICK, ("alice",)))

    async with Feed() as feed:
        state = await feed.next()
        ws.push(self_presence(NICK))  # our own presence changing
        await feed.quiet()

    assert nicks(state) == ["alice"]


# --- when the room is closed ----------------------------------------------


async def test_room_is_closed_when_focus_leaves(server) -> None:
    ws = server.add(*join_script(NICK, ("alice",)))

    async with Feed() as feed:
        await feed.next()
        ws.push(unavailable_presence("focus"))
        last = await feed.next()
        assert last["status"] == {"open": False, "attempts": 0}
        assert nicks(last) == ["alice"]
        assert await feed.next() is END

    assert any('type="unavailable"' in s for s in ws.sent)  # we left properly
    assert ws.closed


async def test_focus_leaving_is_only_a_close_if_it_was_ever_there(
    server,
) -> None:
    ws = server.add(*join_script(NICK, include_focus=False))

    async with Feed() as feed:
        await feed.next()
        ws.push(unavailable_presence("focus"))
        await feed.quiet()


@pytest.mark.parametrize("extra", ["", "<status code='307'/>", "<destroy/>"])
async def test_room_is_closed_when_the_server_removes_us(server, extra: str) -> None:
    ws = server.add(*join_script(NICK, ("alice",)))

    async with Feed() as feed:
        await feed.next()
        ws.push(
            f"<presence xmlns='jabber:client' type='unavailable' from='{ROOM_JID}/{NICK}'>"
            f"<x xmlns='http://jabber.org/protocol/muc#user'><status code='110'/>{extra}</x>"
            "</presence>"
        )
        assert (await feed.next())["status"]["open"] is False
        assert await feed.next() is END


async def test_nonexistent_room_is_closed_immediately(server) -> None:
    server.add(room_creation_restricted_presence(NICK))

    async with Feed() as feed:
        state = await feed.next()
        assert state["status"] == {"open": False, "attempts": 0}
        assert await feed.next() is END


# --- reconnecting ---------------------------------------------------------


@pytest.mark.flaky
async def test_reconnect_changes_only_attempts_potential_timeout(server) -> None:
    ws1 = server.add(*join_script(NICK, ("alice", "bob")))
    server.add(*join_script(NICK, ("alice", "bob")))

    async with Feed() as feed:
        before = await feed.next()
        ws1.push(DROPPED)
        after = await feed.next()

        assert after["status"] == {"open": True, "attempts": 1}
        assert without_attempts(after) == without_attempts(before)
        await feed.quiet(0.1)  # reconnected with the same roster: no extra line
        assert server.connects == 2


async def test_reconnect_with_a_different_roster_adds_one_line(server) -> None:
    ws1 = server.add(*join_script(NICK, ("alice", "bob")))
    server.add(*join_script(NICK, ("bob", "carol")))

    async with Feed() as feed:
        await feed.next()
        ws1.push(DROPPED)
        attempt = await feed.next()
        changed = await feed.next()

    assert nicks(attempt) == ["alice", "bob"]
    assert changed["status"] == {"open": True, "attempts": 1}  # attempts unchanged
    assert nicks(changed) == ["bob", "carol"]


@pytest.mark.flaky
async def test_each_failed_attempt_prints_one_line_with_attempts_plus_one_potential_timeout(
    server,
) -> None:
    ws1 = server.add(*join_script(NICK, ("alice",)))

    async with Feed(timeout=0.1) as feed:
        first = await feed.next()
        ws1.push(DROPPED)
        attempts = []
        try:
            while True:
                state = await feed.next()
                assert without_attempts(state) == without_attempts(first)
                attempts.append(state["status"]["attempts"])
        except JitsiConnectionError as exc:
            assert "could not reconnect within" in str(exc)  # noqa: PT017
        else:
            pytest.fail("the monitor never gave up")

    assert len(attempts) >= 3
    assert attempts == list(range(1, len(attempts) + 1))  # never skips, never resets


async def test_attempts_are_cumulative_over_several_outages(
    server,
) -> None:
    ws1 = server.add(*join_script(NICK, ("alice",)))
    ws2 = server.add(*join_script(NICK, ("alice",)))
    server.add(*join_script(NICK, ("alice",)))

    async with Feed() as feed:
        await feed.next()
        ws1.push(DROPPED)
        assert (await feed.next())["status"]["attempts"] == 1
        await feed.quiet(0.05)
        ws2.push(DROPPED)
        assert (await feed.next())["status"]["attempts"] == 2


@pytest.mark.flaky
async def test_success_resets_the_give_up_clock_not_the_attempts_potential_timeout(
    server,
) -> None:
    ws1 = server.add(*join_script(NICK))
    ws2 = server.add(*join_script(NICK))

    async with Feed(timeout=0.3) as feed:
        await feed.next()
        ws1.push(DROPPED)
        await feed.next()
        await asyncio.sleep(0.35)  # longer than the timeout, but we are connected
        ws2.push(presence("x"))
        assert nicks(await feed.next()) == ["x"]


async def test_room_closed_during_the_outage_ends_the_monitor(server) -> None:
    ws1 = server.add(*join_script(NICK, ("alice",)))
    server.add(room_creation_restricted_presence(NICK))

    async with Feed() as feed:
        await feed.next()
        ws1.push(DROPPED)
        assert (await feed.next())["status"] == {"open": True, "attempts": 1}
        final = await feed.next()
        assert final["status"] == {"open": False, "attempts": 1}
        assert await feed.next() is END


async def test_no_reconnect_when_timeout_is_zero(server) -> None:
    ws1 = server.add(*join_script(NICK))

    async with Feed(timeout=0) as feed:
        await feed.next()
        ws1.push(DROPPED)
        with pytest.raises(JitsiConnectionError, match="Lost the connection"):
            await feed.next()
    assert server.connects == 1


@pytest.mark.parametrize(
    "problem",
    [DROPPED, "<this is not xml", RuntimeError("bug"), OSError("reset")],
    ids=["closed", "garbage", "unexpected-exception", "oserror"],
)
async def test_any_reader_failure_is_a_lost_connection(server, problem) -> None:
    ws1 = server.add(*join_script(NICK))
    server.add(*join_script(NICK))

    async with Feed() as feed:
        await feed.next()
        ws1.push(problem)
        assert (await feed.next())["status"]["attempts"] == 1


@pytest.mark.flaky
async def test_a_quiet_room_is_not_a_timeout_potential_timeout(server) -> None:
    ws = server.add(*join_script(NICK))

    async with Feed(connect_timeout=0.05) as feed:
        await feed.next()
        await feed.quiet(0.3)  # 6x the network timeout with nothing to read
        ws.push(presence("late"))
        state = await feed.next()

    assert nicks(state) == ["late"]
    assert state["status"]["attempts"] == 0
    assert server.connects == 1


async def test_stopping_early_leaves_the_room(server) -> None:
    ws = server.add(*join_script(NICK, ("alice",)))

    async with Feed() as feed:
        await feed.next()

    assert ws.closed
    assert any('type="unavailable"' in s for s in ws.sent)


async def test_cancelling_leaves_the_room(server) -> None:
    ws = server.add(*join_script(NICK))
    feed = Feed()
    await feed.next()
    pending = asyncio.ensure_future(feed.next(10))
    await asyncio.sleep(0.02)
    pending.cancel()
    await asyncio.wait([pending])
    await feed.__aexit__(None, None, None)

    assert ws.closed


# --- failures before there is a first state -------------------------------


async def test_refused_connection_raises_before_any_output(server) -> None:
    async with Feed() as feed:
        with pytest.raises(JitsiConnectionError, match="Could not"):
            await feed.next()


async def test_rejected_login_raises_before_any_output(server) -> None:
    server.add()  # the existence check succeeds ...
    ws = ControlledWS(
        [stream_open(), stream_features_mechanisms(), sasl_failure()], handshake=False
    )
    server.queue[:] = [server.queue[0], ws]  # ... the login is then rejected

    async with Feed() as feed:
        with pytest.raises(JitsiConnectionError, match="rejected"):
            await feed.next()
    assert ws.closed


async def test_join_error_raises_before_any_output(server) -> None:
    ws = server.add(error_presence(NICK))

    async with Feed() as feed:
        with pytest.raises(JitsiConnectionError, match="Failed to join"):
            await feed.next()
    assert ws.closed


async def test_bad_url_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Could not parse"):
        await anext(monitor_conference("https://meet.example.com"))


# --- order ----------------------------------------------------------------


def _handler_connection() -> JitsiXmppConnection:
    conn = JitsiXmppConnection(
        CONFERENCE_URL, NICK, anonymous_domain=XMPP_DOMAIN, muc_domain=MUC_DOMAIN
    )
    conn._muc_domain = MUC_DOMAIN
    conn._occupant_jid = f"{ROOM_JID}/{NICK}"
    return conn


@pytest.mark.parametrize("seed", range(25))
def test_participant_order_is_stable_at_every_step(seed: int) -> None:
    """Model: an ordered list. Join appends, leave removes, update keeps place."""
    rng = random.Random(seed)
    conn = _handler_connection()
    model: list[str] = []
    previous: list[str] = []
    for _ in range(200):
        nick = rng.choice("abcdefgh")
        if rng.random() < 0.4:
            conn._handle_presence(ET.fromstring(unavailable_presence(nick)))
            if nick in model:
                model.remove(nick)
        else:
            role = rng.choice(["participant", "moderator"])
            conn._handle_presence(
                ET.fromstring(presence(nick, role=role, name=rng.choice("XYZ")))
            )
            if nick not in model:
                model.append(nick)
        if rng.random() < 0.1:  # the monitor itself and focus never show up
            conn._handle_presence(ET.fromstring(self_presence(NICK)))
            conn._handle_presence(ET.fromstring(focus_presence()))

        current = nicks(_state({}, conn, 0, is_open=True))
        assert current == model
        # Whoever is in both this and the previous state keeps the relative order.
        assert [n for n in current if n in previous] == [
            n for n in previous if n in current
        ]
        previous = current


@pytest.mark.parametrize("seed", range(5))
async def test_emitted_order_follows_the_model_and_only_real_changes_print(
    server, seed: int
) -> None:
    rng = random.Random(seed)
    ws = server.add(*join_script(NICK))
    known: dict[str, tuple] = {}

    async with Feed() as feed:
        await feed.next()
        for _ in range(60):
            nick = rng.choice("abcd")
            before = list(known.items())
            if rng.random() < 0.4:
                ws.push(unavailable_presence(nick))
                known.pop(nick, None)
            else:
                role = rng.choice(["participant", "moderator"])
                ws.push(presence(nick, role=role))
                known[nick] = role
            if list(known.items()) == before:
                await feed.quiet(0.005)
            else:
                state = await feed.next()
                assert nicks(state) == list(known)
                assert [p["role"] for p in state["participants"]] == list(
                    known.values()
                )


async def test_same_display_name_gives_two_entries_in_join_order(server) -> None:
    ws = server.add(*join_script(NICK))

    async with Feed() as feed:
        await feed.next()
        for nick in ("x", "y", "z"):
            ws.push(presence(nick, name="Sam"))
            state = await feed.next()

    assert nicks(state) == ["x", "y", "z"]
    assert [p["name"] for p in state["participants"]] == ["Sam"] * 3


# --- the blocking API -----------------------------------------------------


def test_monitor_room_raises_like_the_async_api(server) -> None:
    with pytest.raises(JitsiConnectionError):
        next(monitor_room(CONFERENCE_URL, connect_timeout=0.05))


def test_monitor_room_yields_every_state_and_finishes(server) -> None:
    server.add(*join_script(NICK, ("alice",)), unavailable_presence("focus"))

    states = list(
        monitor_room(
            CONFERENCE_URL,
            nick=NICK,
            anonymous_domain=XMPP_DOMAIN,
            muc_domain=MUC_DOMAIN,
            connect_timeout=1,
        )
    )

    assert states[-1]["status"] == {"open": False, "attempts": 0}
    assert all(list(s) == ["room", "participants", "status"] for s in states)


# --- the docs -------------------------------------------------------------

DOCS = Path(__file__).parents[2] / "docs"


@pytest.mark.skipif(not DOCS.exists(), reason="docs are not installed")
def test_docs_example_has_the_real_schema(server) -> None:
    text = (DOCS / "how-to" / "monitor-a-conference.rst").read_text()
    example = json.loads(_first_json_code_block(text))
    server.add(*join_script(NICK, ("alice",)))

    actual = asyncio.run(_first_state())

    assert list(example) == list(actual)
    assert list(example["room"]) == list(actual["room"])
    assert list(example["status"]) == list(actual["status"])
    assert list(example["participants"][0]) == list(actual["participants"][0])


async def _first_state() -> dict:
    async with Feed() as feed:
        return await feed.next()


def _first_json_code_block(text: str) -> str:
    """The body of the first ``.. code-block:: json`` in an rst page.

    It is pretty-printed there (for readability, not because that is what
    the command prints) - this dedents it rather than assuming one line.
    """
    marker = "code-block:: json\n\n"
    start = text.index(marker) + len(marker)
    indent = len(text[start:]) - len(text[start:].lstrip(" "))
    lines = []
    for line in text[start:].split("\n"):
        if line and not line.startswith(" " * indent):
            break
        lines.append(line[indent:])
    return "\n".join(lines)


@pytest.mark.skipif(not DOCS.exists(), reason="docs are not installed")
def test_docs_are_linked_and_list_the_exit_codes() -> None:
    page = (DOCS / "how-to" / "monitor-a-conference.rst").read_text()
    assert "monitor-a-conference" in (DOCS / "how-to" / "index.rst").read_text()
    for code in ("0", "1", "2", "130"):
        assert f"* - ``{code}``" in page
    assert "list-table::" in page


# --- rooms that do not exist, being alone, --create and --stay ------------


async def test_missing_room_prints_closed_once_without_joining(server) -> None:
    check = server.add(exists=False)

    async with Feed(stay=False) as feed:
        state = await feed.next()
        assert await feed.next() is END

    assert state["status"] == {"open": False, "attempts": 0}
    assert state["participants"] == []
    assert list(state) == ["room", "participants", "status"]
    assert state["room"]["jid"] == ROOM_JID
    assert server.connects == 0  # never joined
    assert not server.queue  # only the existence check was made
    assert not any("<presence" in s for s in check.sent)


async def test_check_happens_before_the_join_and_only_disco_is_sent(server) -> None:
    server.add(*join_script(NICK, ("alice",)))
    check = server.queue[0]

    async with Feed(stay=False) as feed:
        await feed.next()

    assert any("disco#info" in s and ROOM_JID in s for s in check.sent)
    assert not any("<presence" in s for s in check.sent)


async def test_create_skips_the_check_and_joins(server) -> None:
    ws = ControlledWS(join_script(NICK))  # no existence check is queued at all
    server.queue.append(ws)

    async with Feed(create=True, stay=True) as feed:
        state = await feed.next()

    assert state["status"] == {"open": True, "attempts": 0}
    assert server.connects == 1
    assert any("<presence" in s for s in ws.sent)


@pytest.mark.flaky
async def test_create_skips_the_check_when_reconnecting_too_potential_timeout(
    server,
) -> None:
    ws1 = ControlledWS(join_script(NICK, ("alice",)))
    ws2 = ControlledWS(join_script(NICK, ("alice",)))
    server.queue.extend([ws1, ws2])  # joins only: any check would break the queue

    async with Feed(create=True) as feed:
        await feed.next()
        ws1.push(DROPPED)
        assert (await feed.next())["status"]["attempts"] == 1
        await feed.quiet(0.05)
    assert server.connects == 2


async def test_create_without_stay_leaves_an_empty_room_again(server) -> None:
    ws = ControlledWS(join_script(NICK))
    server.queue.append(ws)

    async with Feed(create=True, stay=False) as feed:
        state = await feed.next()
        assert await feed.next() is END

    assert state["status"]["open"] is False
    assert ws.closed
    assert any('type="unavailable"' in s for s in ws.sent)


async def test_leaves_when_the_last_participant_goes(server) -> None:
    ws = server.add(*join_script(NICK, ("alice", "bob")))

    async with Feed(stay=False) as feed:
        assert (await feed.next())["status"]["open"] is True
        ws.push(unavailable_presence("alice"))
        assert nicks(await feed.next()) == ["bob"]
        ws.push(unavailable_presence("bob"))
        last = await feed.next()
        assert last["status"] == {"open": False, "attempts": 0}
        assert last["participants"] == []
        assert await feed.next() is END

    assert ws.closed
    assert any('type="unavailable"' in s for s in ws.sent)  # we really left


async def test_alone_from_the_start_leaves_immediately(server) -> None:
    ws = server.add(*join_script(NICK))  # only focus is there

    async with Feed(stay=False) as feed:
        state = await feed.next()
        assert await feed.next() is END

    assert state["status"] == {"open": False, "attempts": 0}
    assert ws.closed
    assert any('type="unavailable"' in s for s in ws.sent)


async def test_stay_keeps_the_room_open_when_alone(server) -> None:
    ws = server.add(*join_script(NICK, ("alice",)))

    async with Feed(stay=True) as feed:
        await feed.next()
        ws.push(unavailable_presence("alice"))
        state = await feed.next()
        assert state["status"]["open"] is True
        assert state["participants"] == []
        await feed.quiet(0.1)  # still there, nothing more to say
        assert not ws.closed
        ws.push(presence("carol"))
        assert nicks(await feed.next()) == ["carol"]


async def test_stay_still_ends_when_the_room_is_closed(server) -> None:
    ws = server.add(*join_script(NICK))

    async with Feed(stay=True) as feed:
        await feed.next()
        ws.push(unavailable_presence("focus"))
        assert (await feed.next())["status"]["open"] is False
        assert await feed.next() is END


async def test_room_gone_when_reconnecting_prints_closed_and_no_participants(
    server,
) -> None:
    ws1 = server.add(*join_script(NICK, ("alice",)))
    server.add(exists=False)

    async with Feed() as feed:
        await feed.next()
        ws1.push(DROPPED)
        assert (await feed.next())["status"] == {"open": True, "attempts": 1}
        final = await feed.next()
        assert await feed.next() is END

    assert final["status"] == {"open": False, "attempts": 1}
    assert final["participants"] == []
    assert server.connects == 1  # never rejoined a room that is gone
