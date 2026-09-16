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
"""Shared fixtures: a fake WebSocket/XMPP server so tests don't touch the network.

None of these tests talk to a real Jitsi server - they drive
:class:`inspect_jitsi.xmpp.JitsiXmppConnection` (and friends) against a
scripted sequence of canned XMPP stanzas, recorded from real traffic against
a docker-jitsi-meet deployment (see `inspect_jitsi/xmpp/connection.py`).
"""

from __future__ import annotations

import asyncio
from typing import Self

import pytest

# A representative docker-jitsi-meet setup: public hostname differs from the
# internal XMPP/MUC domains, just like a real deployment.
WS_DOMAIN = "meet.example.com"
XMPP_DOMAIN = "meet.jitsi"
MUC_DOMAIN = "muc.meet.jitsi"
ROOM = "testroom"
ROOM_JID = f"{ROOM}@{MUC_DOMAIN}"
CONFERENCE_URL = f"https://{WS_DOMAIN}/{ROOM}"

CONFIG_JS = f"""
config.hosts = {{}};
config.hosts.domain = '{XMPP_DOMAIN}';
config.hosts.muc = '{MUC_DOMAIN}';
"""


def stream_open(from_domain: str = XMPP_DOMAIN) -> str:
    return f"<open xmlns='urn:ietf:params:xml:ns:xmpp-framing' id='s1' version='1.0' from='{from_domain}'/>"


def stream_features_mechanisms() -> str:
    return (
        "<stream:features xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>"
        "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>"
        "<mechanism>ANONYMOUS</mechanism>"
        "</mechanisms></stream:features>"
    )


def stream_features_mechanisms_unbound_prefix() -> str:
    """Same as `stream_features_mechanisms`, but missing `xmlns:stream` -
    some real deployments send it this way over the WebSocket framing,
    which has no enclosing `<stream:stream>` to inherit the binding from."""
    return (
        "<stream:features xmlns='jabber:client'>"
        "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>"
        "<mechanism>ANONYMOUS</mechanism>"
        "</mechanisms></stream:features>"
    )


def stream_features_no_anonymous() -> str:
    return (
        "<stream:features xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>"
        "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>"
        "<mechanism>PLAIN</mechanism>"
        "</mechanisms></stream:features>"
    )


def sasl_success() -> str:
    return "<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>"


def sasl_failure() -> str:
    return (
        "<failure xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>"
        "<not-allowed/><text>token required</text></failure>"
    )


def stream_features_bind() -> str:
    return (
        "<stream:features xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>"
        "<bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'><required/></bind>"
        "</stream:features>"
    )


def bind_result() -> str:
    return (
        "<iq xmlns='jabber:client' type='result' id='bind1'>"
        "<bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
        f"<jid>probe@{XMPP_DOMAIN}/res1</jid></bind></iq>"
    )


def handshake_script(*, offer_anonymous: bool = True) -> list[str]:
    """The stream-open/SASL/bind exchange every successful open() goes through."""
    if not offer_anonymous:
        return [stream_open(), stream_features_no_anonymous()]
    return [
        stream_open(),
        stream_features_mechanisms(),
        sasl_success(),
        stream_open(),
        stream_features_bind(),
        bind_result(),
    ]


def occupant_presence(nick: str, *, room_jid: str = ROOM_JID) -> str:
    return (
        f"<presence xmlns='jabber:client' from='{room_jid}/{nick}'>"
        "<x xmlns='http://jabber.org/protocol/muc#user'>"
        "<item affiliation='member' role='participant'/></x></presence>"
    )


def focus_presence(*, room_jid: str = ROOM_JID) -> str:
    """jicofo's control-plane pseudo-participant - never a human."""
    return occupant_presence("focus", room_jid=room_jid)


def self_presence(nick: str, *, room_jid: str = ROOM_JID) -> str:
    return (
        f"<presence xmlns='jabber:client' from='{room_jid}/{nick}'>"
        "<x xmlns='http://jabber.org/protocol/muc#user'>"
        "<status code='110'/>"
        "<item affiliation='none' role='participant'/></x></presence>"
    )


def error_presence(nick: str, *, room_jid: str = ROOM_JID) -> str:
    return (
        f"<presence xmlns='jabber:client' type='error' from='{room_jid}/{nick}'>"
        "<error type='auth'><forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/></error>"
        "</presence>"
    )


def unavailable_presence(nick: str, *, room_jid: str = ROOM_JID) -> str:
    return (
        f"<presence xmlns='jabber:client' type='unavailable' from='{room_jid}/{nick}'/>"
    )


def room_creation_restricted_presence(nick: str, *, room_jid: str = ROOM_JID) -> str:
    """Presence error for joining a room that doesn't exist, on a deployment
    that restricts room creation to privileged users (jicofo) - i.e. this
    room is empty, not a genuine failure."""
    muc_domain = room_jid.split("@", 1)[1]
    return (
        f"<presence xmlns='jabber:client' type='error' from='{room_jid}/{nick}'>"
        f"<error type='cancel' by='{muc_domain}'>"
        "<not-allowed xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>"
        "<text xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'>Room creation is restricted</text>"
        "</error></presence>"
    )


def room_not_found_disco_error(*, room_jid: str = ROOM_JID) -> str:
    """disco#info error for a room that doesn't currently exist."""
    muc_domain = room_jid.split("@", 1)[1]
    return (
        f"<iq xmlns='jabber:client' id='disco1' type='error' from='{room_jid}'>"
        f"<error type='cancel' by='{muc_domain}'>"
        "<item-not-found xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>"
        "</error></iq>"
    )


def forbidden_disco_error(*, room_jid: str = ROOM_JID) -> str:
    """disco#info error for a room that exists but restricts disco to occupants."""
    return (
        f"<iq xmlns='jabber:client' id='disco1' type='error' from='{room_jid}'>"
        "<error type='auth'><forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/></error></iq>"
    )


def join_script(
    nick: str, other_occupants: tuple[str, ...] = (), *, include_focus: bool = True
) -> list[str]:
    """Presence stanzas the MUC sends back after a join, ending with self-presence."""
    script = [occupant_presence(other) for other in other_occupants]
    if include_focus:
        script.append(focus_presence())
    script.append(self_presence(nick))
    return script


class FakeWebSocket:
    """A minimal stand-in for a `websockets` connection, fed by a fixed script.

    `recv()` returns the next scripted message, or raises it if it's an
    exception instance (to simulate a dropped connection mid-script); once
    the script is exhausted, it waits forever (so a background reader task
    just idles, like a real quiet connection) until cancelled.
    """

    def __init__(self, script: list[str]) -> None:
        self._script = list(script)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if self._script:
            item = self._script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        await asyncio.Event().wait()  # idle forever, like a quiet real connection
        raise AssertionError  # pragma: no cover - unreachable

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()


class FakeConnect:
    """Mimics `websockets.connect(...)`, usable both as `await ...` and `async with ...`."""

    def __init__(self, ws: FakeWebSocket) -> None:
        self._ws = ws

    def __await__(self):
        async def _get() -> FakeWebSocket:
            return self._ws

        return _get().__await__()

    async def __aenter__(self) -> FakeWebSocket:
        return self._ws

    async def __aexit__(self, *exc_info: object) -> None:
        pass


class FakeConfigJsResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


class FakeConfigJsSession:
    """Mimics `niquests.AsyncSession()` serving a canned /config.js body."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def get(
        self, _url: str, timeout: float | None = None
    ) -> FakeConfigJsResponse:
        return FakeConfigJsResponse(self._text)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass


@pytest.fixture
def fake_config_js(monkeypatch: pytest.MonkeyPatch):
    """Patch `niquests.AsyncSession` to serve a canned /config.js for WS_DOMAIN."""
    import inspect_jitsi.xmpp.connection as connection_module

    monkeypatch.setattr(
        connection_module.niquests,
        "AsyncSession",
        lambda: FakeConfigJsSession(CONFIG_JS),
    )


@pytest.fixture
def fake_server(monkeypatch: pytest.MonkeyPatch):
    """Patch `websockets.connect` everywhere it's used to return a scripted fake.

    Returns a function `use(script)` - call it with the list of stanzas the
    fake server should hand out; it returns the `FakeWebSocket` so the test
    can inspect what was sent.
    """
    import inspect_jitsi.xmpp.conference as conference_module
    import inspect_jitsi.xmpp.connection as connection_module

    def use(script: list[str]) -> FakeWebSocket:
        ws = FakeWebSocket(script)
        fake_connect = lambda *args, **kwargs: FakeConnect(ws)  # noqa: E731
        monkeypatch.setattr(connection_module.websockets, "connect", fake_connect)
        monkeypatch.setattr(conference_module.websockets, "connect", fake_connect)
        return ws

    return use
