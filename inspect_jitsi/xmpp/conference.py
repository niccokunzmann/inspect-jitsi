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
"""`JitsiConference`: the public, domain-level handle on a Jitsi Meet room.

:class:`~inspect_jitsi.xmpp.connection.JitsiXmppConnection` is the low-level
XMPP/MUC transport (stream negotiation, SASL, presence framing - the RFC
6120/7395/XEP-0045 plumbing). `JitsiConference` wraps one such connection and
is the class user code is expected to reach for.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, Self

import websockets

from inspect_jitsi.xmpp.connection import (
    _NS_DISCO_INFO,
    _NS_FRAMING,
    _NS_SASL,
    _TRANSPORT_ERRORS,
    ROOM_NOT_FOUND,
    JitsiConnectionError,
    JitsiXmppConnection,
    _error_condition,
    _local,
    _open_authenticated_stream,
    _recv_stanza,
    discover_hosts,
    parse_conference_url,
    resolve_domains,
)
from inspect_jitsi.xmpp.diagnosis import DiagnosisResult

if TYPE_CHECKING:
    from inspect_jitsi.xmpp.participant import Participant

__all__ = ["JitsiConference"]


class JitsiConference:
    """A Jitsi Meet conference (room), joined anonymously as an observer.

    Use as an async context manager::

        async with JitsiConference(conference_url, "probe") as conference:
            print(await conference.get_participants())

    or call :meth:`open`/:meth:`close` directly. :meth:`diagnose` and
    :meth:`is_created` can be called standalone, without opening the
    conference, to check what's needed to join at all and whether there's
    anyone to join in the first place.
    """

    def __init__(
        self,
        conference_url: str,
        nick: str | None = None,
        *,
        name: str | None = None,
        anonymous_domain: str | None = None,
        muc_domain: str | None = None,
        timeout: float = 10,
    ) -> None:
        self.conference_url = conference_url
        self.timeout = timeout
        self._anonymous_domain = anonymous_domain
        self._muc_domain = muc_domain
        self._connection = JitsiXmppConnection(
            conference_url,
            nick,
            name=name,
            anonymous_domain=anonymous_domain,
            muc_domain=muc_domain,
            timeout=timeout,
        )

    @property
    def room(self) -> str:
        """The room name, e.g. "SomeRoomName"."""
        return self._connection.room

    @property
    def nick(self) -> str:
        """The MUC nickname this conference is (or will be) joined under."""
        return self._connection.nick

    @property
    def name(self) -> str:
        """The display name (XEP-0172) disclosed when joining."""
        return self._connection.name

    async def open(self) -> None:
        """Connect and join the conference."""
        await self._connection.open()

    async def close(self) -> None:
        """Leave the conference and disconnect."""
        await self._connection.close()

    async def get_participants(self) -> list[Participant]:
        """Return the participants currently known to be in the conference."""
        return await self._connection.get_participants()

    async def is_created(self) -> bool:
        """Return whether this room currently exists, without joining it.

        Jitsi's MUC returns a `forbidden` disco#info error for a room that
        exists (disco is restricted to occupants) but `item-not-found` for
        one that hasn't been created yet (or was destroyed once everyone
        left) - this tells the two apart without joining.

        Raises:
            inspect_jitsi.xmpp.JitsiConnectionError: the XMPP connection
                failed or was lost (refused, dropped, timed out, or an
                unparseable server response) - not raised for a room that simply doesn't
                exist, which is reported as `False`.
        """
        ws_domain, room = parse_conference_url(self.conference_url)
        xmpp_domain, muc_domain = await resolve_domains(
            ws_domain, self._anonymous_domain, self._muc_domain, self.timeout
        )
        room_jid = f"{room.lower()}@{muc_domain}"

        ws_url = f"wss://{ws_domain}/xmpp-websocket"
        connect = websockets.connect(
            ws_url, subprotocols=["xmpp"], open_timeout=self.timeout
        )
        try:
            async with connect as ws:
                await _open_authenticated_stream(ws, xmpp_domain, self.timeout)
                await ws.send(
                    f'<iq xmlns="jabber:client" type="get" to="{room_jid}" id="disco1">'
                    f'<query xmlns="{_NS_DISCO_INFO}"/></iq>'
                )
                stanza = await _recv_stanza(ws, self.timeout)
        except JitsiConnectionError:
            raise
        except _TRANSPORT_ERRORS as exc:
            msg = f"Could not check whether {self.conference_url!r} exists: {exc}"
            raise JitsiConnectionError(msg) from exc

        if stanza.get("type") != "error":
            return True
        return _error_condition(stanza) != ROOM_NOT_FOUND

    async def diagnose(self) -> DiagnosisResult:
        """Probe the server and report what's needed to read this room's occupancy.

        Unlike :meth:`open`, this never joins the room - it checks whether
        /config.js was readable, which internal domains it advertises,
        whether the XMPP domain is actually served over the WebSocket
        endpoint, which SASL mechanisms it offers, and whether anonymous
        login succeeds (i.e. whether a token/JWT is required).
        """
        ws_domain, _ = parse_conference_url(self.conference_url)
        result = DiagnosisResult(ws_domain=ws_domain)

        hosts = {"domain": None, "muc": None, "anonymousdomain": None}
        try:
            hosts = await discover_hosts(ws_domain, timeout=self.timeout)
            result.config_js_reachable = True
            result.discovered_hosts = hosts
        except Exception as exc:  # noqa: BLE001
            result.error = f"config.js: {exc}"

        xmpp_domain = (
            self._anonymous_domain
            or hosts["anonymousdomain"]
            or hosts["domain"]
            or ws_domain
        )
        result.xmpp_domain_tried = xmpp_domain

        try:
            await self._probe_stream(ws_domain, xmpp_domain, result)
        except Exception as exc:  # noqa: BLE001
            if result.error is None:
                result.error = str(exc)

        return result

    async def _probe_stream(
        self, ws_domain: str, xmpp_domain: str, result: DiagnosisResult
    ) -> None:
        ws_url = f"wss://{ws_domain}/xmpp-websocket"
        connect = websockets.connect(
            ws_url, subprotocols=["xmpp"], open_timeout=self.timeout
        )
        async with connect as ws:
            await ws.send(
                f'<open xmlns="{_NS_FRAMING}" to="{xmpp_domain}" version="1.0"/>'
            )
            opened = await _recv_stanza(ws, self.timeout)
            if _local(opened.tag) == "error":
                result.domain_recognized = False
                result.error = ET.tostring(opened, encoding="unicode")
                return
            result.domain_recognized = True

            features = await _recv_stanza(ws, self.timeout)
            result.sasl_mechanisms = [
                m.text
                for m in features.iter()
                if _local(m.tag) == "mechanism" and m.text
            ]

            if "ANONYMOUS" not in result.sasl_mechanisms:
                result.anonymous_login_ok = False
                result.error = "Server does not offer the ANONYMOUS SASL mechanism."
                return

            await ws.send(f'<auth xmlns="{_NS_SASL}" mechanism="ANONYMOUS"/>')
            auth_result = await _recv_stanza(ws, self.timeout)
            if _local(auth_result.tag) == "success":
                result.anonymous_login_ok = True
            else:
                result.anonymous_login_ok = False
                result.error = ET.tostring(auth_result, encoding="unicode")

    async def __aenter__(self) -> Self:
        await self.open()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
