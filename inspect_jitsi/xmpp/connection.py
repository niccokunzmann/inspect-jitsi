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
"""A minimal anonymous XMPP/MUC connection to a Jitsi Meet room.

Jitsi's prosody deployment locks down disco#info on MUC rooms to occupants
only (confirmed live: a bare disco#info query gets `<error type="auth">
<forbidden/></error>`), so the usual XEP-0045 "peek without joining" trick
does not work here. Instead, :class:`JitsiXmppConnection` joins the room as
a real (if anonymous) occupant over an XMPP connection carried by WebSocket
(the same "wss://<domain>/xmpp-websocket" endpoint the web client uses), and
reads the roster of <presence> stanzas the MUC sends.

jicofo (the conference focus component) also joins every active Jitsi
conference's MUC as a pseudo-participant nicknamed "focus" - that occupant
is filtered out of the roster so it reflects only humans.

No Python XMPP library (slixmpp, aioxmpp, ...) supports the WebSocket
transport Jitsi requires - they're TCP-only, and Jitsi deployments generally
don't expose raw XMPP client-to-server (5222) publicly - so this hand-rolls
the small slice of RFC 6120 (stream/SASL/bind) and RFC 7395 (XMPP over
WebSocket framing) needed to join a MUC room.
"""

from __future__ import annotations

import asyncio
import re
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import niquests
import websockets
from websockets.exceptions import ConnectionClosed

from inspect_jitsi.xmpp.participant import Participant

__all__ = ["JitsiXmppConnection", "RoomDoesNotExist", "discover_hosts"]

_NS_FRAMING = "urn:ietf:params:xml:ns:xmpp-framing"
_NS_SASL = "urn:ietf:params:xml:ns:xmpp-sasl"
_NS_BIND = "urn:ietf:params:xml:ns:xmpp-bind"
_NS_MUC = "http://jabber.org/protocol/muc"
_NS_MUC_USER = "http://jabber.org/protocol/muc#user"
_NS_DISCO_INFO = "http://jabber.org/protocol/disco#info"

FOCUS_NICK = "focus"
"""MUC nickname jicofo always joins under - not a human participant."""

ROOM_CREATION_RESTRICTED = "not-allowed"
"""XEP-0045 presence error condition for joining a room that doesn't exist
yet, on a deployment where only privileged users (jicofo) may create rooms -
i.e. "this room is empty" (or was destroyed once everyone left), not a
genuine failure.
"""

ROOM_NOT_FOUND = "item-not-found"
"""XEP-0045/XEP-0030 error condition a MUC service returns for disco#info on
a room that doesn't currently exist - as opposed to `forbidden`, which it
returns for one that exists but restricts disco to occupants.
"""


class RoomDoesNotExist(Exception):
    """A Jitsi MUC room doesn't exist (yet) and this deployment won't create it.

    Not raised by `JitsiXmppConnection.open()` itself, which instead treats
    this as an empty room (`room_created` is set to False, with 0
    participants) rather than an error - this is available for callers that
    would rather treat "room doesn't exist" as a hard failure.
    """


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _error_condition(stanza: ET.Element) -> str | None:
    """Return the XMPP stanza-error condition name (e.g. "not-allowed"), if any."""
    error = next((child for child in stanza if _local(child.tag) == "error"), None)
    if error is None:
        return None
    return next(
        (_local(child.tag) for child in error if _local(child.tag) != "text"), None
    )


def parse_conference_url(conference_url: str) -> tuple[str, str]:
    """Split a Jitsi conference URL into (public web domain, room name)."""
    if "://" not in conference_url:
        conference_url = f"https://{conference_url}"
    parsed = urlparse(conference_url)
    domain = parsed.netloc
    room = parsed.path.strip("/").split("/")[0]
    if not domain or not room:
        msg = f"Could not parse a Jitsi domain/room from URL: {conference_url!r}"
        raise ValueError(msg)
    return domain, room


def _eval_js_string_concat(expr: str, variables: dict[str, str]) -> str:
    """Best-effort evaluator for simple JS `'a' + b + 'c'` string concatenations."""
    result = []
    for token in expr.split("+"):
        token = token.strip()
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
            result.append(token[1:-1])
        elif token in variables:
            result.append(variables[token])
    return "".join(result)


def _parse_config_js(text: str) -> dict[str, str | None]:
    variables = {}
    for match in re.finditer(
        r"var\s+(\w+)\s*=\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\s*;", text
    ):
        name, literal = match.group(1), match.group(2)
        variables[name] = literal[1:-1]

    hosts: dict[str, str | None] = {"domain": None, "muc": None, "anonymousdomain": None}
    for key in hosts:
        match = re.search(rf"hosts\.{key}\s*=\s*([^;]+);", text)
        if match:
            hosts[key] = _eval_js_string_concat(match.group(1), variables) or None
    return hosts


async def discover_hosts(domain: str, timeout: float = 10) -> dict[str, str | None]:
    """Read https://<domain>/config.js to find the real XMPP/MUC domains.

    A Jitsi deployment's internal domain names often differ from the public
    hostname (e.g. docker-jitsi-meet defaults to "meet.jitsi" internally).
    Returns a dict with keys "domain", "muc", "anonymousdomain" - any of
    which may be None if not found.
    """
    url = f"https://{domain}/config.js"
    async with niquests.AsyncSession() as session:
        response = await session.get(url, timeout=timeout)
        response.raise_for_status()
        return _parse_config_js(response.text)


async def resolve_domains(
    ws_domain: str,
    anonymous_domain: str | None,
    muc_domain: str | None,
    timeout: float,
) -> tuple[str, str]:
    """Resolve (xmpp_domain_to_authenticate_as, muc_domain) for a deployment.

    Uses the given overrides where provided, otherwise falls back to
    `discover_hosts(ws_domain)` (and finally to guesses), so `ws_domain`
    itself is only used when neither an override nor /config.js gives an
    answer.
    """
    if anonymous_domain is not None and muc_domain is not None:
        return anonymous_domain, muc_domain

    try:
        hosts = await discover_hosts(ws_domain, timeout=timeout)
    except Exception:  # noqa: BLE001
        hosts = {"domain": None, "muc": None, "anonymousdomain": None}

    xmpp_domain = hosts["domain"] or ws_domain
    resolved_anonymous = anonymous_domain or hosts["anonymousdomain"] or xmpp_domain
    resolved_muc = muc_domain or hosts["muc"] or f"conference.{xmpp_domain}"
    return resolved_anonymous, resolved_muc


async def _recv_stanza(ws: websockets.ClientConnection, timeout: float) -> ET.Element:
    async with asyncio.timeout(timeout):
        message = await ws.recv()
    return ET.fromstring(message)


def _is_self_presence(presence: ET.Element) -> bool:
    """True for the occupant's own presence, marked by MUC status code 110."""
    muc_x = presence.find(f"{{{_NS_MUC_USER}}}x")
    if muc_x is None:
        return False
    return any(
        _local(status.tag) == "status" and status.get("code") == "110" for status in muc_x
    )


async def _open_authenticated_stream(
    ws: websockets.ClientConnection, xmpp_domain: str, timeout: float
) -> None:
    await ws.send(f'<open xmlns="{_NS_FRAMING}" to="{xmpp_domain}" version="1.0"/>')
    opened = await _recv_stanza(ws, timeout)
    if _local(opened.tag) == "error":
        msg = f"Stream error opening to {xmpp_domain!r}: {ET.tostring(opened, encoding='unicode')}"
        raise ConnectionError(msg)
    await _recv_stanza(ws, timeout)  # <stream:features>

    await ws.send(f'<auth xmlns="{_NS_SASL}" mechanism="ANONYMOUS"/>')
    result = await _recv_stanza(ws, timeout)
    if _local(result.tag) != "success":
        msg = (
            f"Anonymous XMPP login to {xmpp_domain!r} was rejected: "
            f"{ET.tostring(result, encoding='unicode')}"
        )
        raise ConnectionError(msg)

    # Restart the stream post-auth, as required by RFC 6120.
    await ws.send(f'<open xmlns="{_NS_FRAMING}" to="{xmpp_domain}" version="1.0"/>')
    await _recv_stanza(ws, timeout)  # <open>
    await _recv_stanza(ws, timeout)  # <stream:features> (bind, ...)

    # Bind a resource so we have a full JID to send IQs from.
    await ws.send(f'<iq xmlns="jabber:client" type="set" id="bind1"><bind xmlns="{_NS_BIND}"/></iq>')
    await _recv_stanza(ws, timeout)


class JitsiXmppConnection:
    """An anonymous XMPP/MUC connection, joined to one Jitsi Meet room.

    Connects over the WebSocket endpoint the Jitsi web client itself uses,
    joins the room's MUC under the given nickname, and keeps a live roster
    of the other participants (updated as they join/leave for as long as
    the connection stays open).

    Use as an async context manager::

        async with JitsiXmppConnection(conference_url, "probe") as conn:
            print(await conn.get_participant_count())

    or call :meth:`open`/:meth:`close` directly.
    """

    def __init__(
        self,
        conference_url: str,
        nick: str | None = None,
        *,
        anonymous_domain: str | None = None,
        muc_domain: str | None = None,
        timeout: float = 10,
    ) -> None:
        self.conference_url = conference_url
        self.ws_domain, self.room = parse_conference_url(conference_url)
        self.nick = nick or f"inspect-jitsi-{uuid.uuid4().hex[:8]}"
        self.timeout = timeout
        self._anonymous_domain = anonymous_domain
        self._muc_domain = muc_domain

        self._ws: websockets.ClientConnection | None = None
        self._occupant_jid: str | None = None
        self._participants: dict[str, Participant] = {}
        self._reader_task: asyncio.Task | None = None
        self._joined = asyncio.Event()
        self.room_created: bool | None = None
        """Whether the room existed to join. None before `open()`.

        False means the room didn't exist yet (or was destroyed once
        everyone left) and this deployment restricts room creation to
        privileged users (jicofo) - not a genuine failure, just an empty
        room: `open()` still succeeds, with no participants.
        """

    @property
    def ws(self) -> websockets.ClientConnection:
        """The underlying WebSocket connection.

        None before :meth:`open` is called and after :meth:`close` -
        accessing it in either state is a bug, so it raises instead of
        silently returning None.
        """
        if self._ws is None:
            msg = "Not connected - call open() (or use 'async with') first."
            raise ConnectionError(msg)
        return self._ws

    async def open(self) -> None:
        """Connect, authenticate anonymously, and join the room's MUC.

        If the room doesn't exist yet and this deployment restricts room
        creation to privileged users, this still succeeds - `room_created`
        is set to False and the room is treated as empty (no participants),
        rather than raising.
        """
        self._anonymous_domain, self._muc_domain = await resolve_domains(
            self.ws_domain, self._anonymous_domain, self._muc_domain, self.timeout
        )

        room_jid = f"{self.room.lower()}@{self._muc_domain}"
        self._occupant_jid = f"{room_jid}/{self.nick}"

        ws_url = f"wss://{self.ws_domain}/xmpp-websocket"
        self._ws = await websockets.connect(ws_url, subprotocols=["xmpp"], open_timeout=self.timeout)
        try:
            await _open_authenticated_stream(self.ws, self._anonymous_domain, self.timeout)

            await self.ws.send(
                f'<presence xmlns="jabber:client" to="{self._occupant_jid}">'
                f'<x xmlns="{_NS_MUC}"/></presence>'
            )

            # Read the initial roster inline, so a failure to join (e.g. a
            # <presence type="error">) raises here rather than being lost in
            # a background task. Our own presence, marked with status code
            # 110, arrives last and signals the roster is complete.
            async with asyncio.timeout(self.timeout):
                while not self._joined.is_set():
                    stanza = await _recv_stanza(self.ws, self.timeout)
                    if _local(stanza.tag) != "presence":
                        continue
                    if stanza.get("type") == "error":
                        if _error_condition(stanza) == ROOM_CREATION_RESTRICTED:
                            # The room doesn't exist and we can't create it -
                            # i.e. it's empty. We never actually became an
                            # occupant, so there's nothing to leave on close().
                            self.room_created = False
                            break
                        msg = (
                            f"Failed to join room {self._occupant_jid!r}: "
                            f"{ET.tostring(stanza, encoding='unicode')}"
                        )
                        raise ConnectionError(msg)
                    self._handle_presence(stanza)
                    if _is_self_presence(stanza):
                        self._joined.set()
                        self.room_created = True

            # Keep tracking further roster changes for as long as we stay
            # connected - unless we never actually joined (empty room).
            if self.room_created:
                self._reader_task = asyncio.ensure_future(self._read_loop())
        except BaseException:
            await self.close()
            raise

    async def _read_loop(self) -> None:
        """Continuously update the roster from incoming presence stanzas."""
        try:
            while True:
                stanza = await _recv_stanza(self.ws, self.timeout)
                if _local(stanza.tag) != "presence" or stanza.get("type") == "error":
                    continue
                self._handle_presence(stanza)
        except (asyncio.CancelledError, ConnectionClosed):
            pass

    def _handle_presence(self, stanza: ET.Element) -> None:
        from_jid = stanza.get("from")
        if not from_jid or from_jid.rsplit("/", 1)[-1] == FOCUS_NICK:
            return
        if stanza.get("type") == "unavailable":
            self._participants.pop(from_jid, None)
        else:
            self._participants[from_jid] = Participant.from_presence(stanza)

    async def close(self) -> None:
        """Leave the room (if joined) and close the connection."""
        if self._reader_task is not None:
            self._reader_task.cancel()
            self._reader_task = None

        if self._ws is not None:
            ws, self._ws = self._ws, None
            try:
                # Only send a leave presence if we actually became an
                # occupant - room_created is False (or still None, if we
                # never got as far as sending the join presence at all).
                if self._occupant_jid is not None and self.room_created:
                    await ws.send(
                        f'<presence xmlns="jabber:client" type="unavailable" '
                        f'to="{self._occupant_jid}"/>'
                    )
            except ConnectionClosed:
                pass
            finally:
                await ws.close()

    async def get_participants(self) -> list[Participant]:
        """Return the participants currently known to be in the room."""
        return [p for jid, p in self._participants.items() if jid != self._occupant_jid]

    async def get_participant_count(self) -> int:
        """Return the number of participants currently in the room."""
        return len(await self.get_participants())

    async def __aenter__(self) -> JitsiXmppConnection:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
