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
"""`monitor_conference`: follow a Jitsi Meet room until it is closed.

An async generator yielding a JSON-serializable state dict - always the same
schema - once when connected and again every time something in it changes::

    {
      "room": {"name": ..., "url": ..., "domain": ..., "muc_domain": ..., "jid": ...},
      "participants": [{...}, ...],
      "status": {"open": true, "attempts": 0},
    }

If the connection drops, it reconnects (for up to ``timeout`` seconds) and
only increases ``status.attempts`` for each attempt. When the room is closed
it yields a last state with ``status.open`` false and returns.
"""

from __future__ import annotations

import asyncio
import copy
from typing import TYPE_CHECKING, Any

from inspect_jitsi.xmpp.conference import JitsiConference
from inspect_jitsi.xmpp.connection import (
    JitsiConnectionError,
    JitsiXmppConnection,
    parse_conference_url,
    resolve_domains,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ["monitor_conference"]

_INITIAL_RETRY_DELAY = 1.0
_MAX_RETRY_DELAY = 10


def _room_info(conference_url: str, muc_domain: str) -> dict:
    ws_domain, room = parse_conference_url(conference_url)
    return {
        "name": room,
        "url": conference_url,
        "domain": ws_domain,
        "muc_domain": muc_domain,
        "jid": f"{room.lower()}@{muc_domain}",
    }


def _state(
    room: dict, conn: JitsiXmppConnection | None, attempts: int, *, is_open: bool
) -> dict:
    participants = [] if conn is None else conn.other_participants()
    return {
        "room": room,
        # In the order they joined; an update keeps a participant's place.
        "participants": [p.to_dict() for p in participants],
        "status": {"open": is_open, "attempts": attempts},
    }


async def monitor_conference(
    conference_url: str,
    *,
    nick: str | None = None,
    name: str | None = None,
    anonymous_domain: str | None = None,
    muc_domain: str | None = None,
    timeout: float = 60,
    connect_timeout: float = 10,
    create: bool = False,
    stay: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Yield the room's state whenever it changes, until the room is closed.

    A room that does not exist is not joined (joining could create it): a
    single state with ``status.open`` false is yielded instead, unless
    ``create`` is set.

    Args:
        conference_url: e.g. "https://meet.example.com/SomeRoomName".
        nick: the MUC nickname to join under. Random if not given.
        name: the display name (XEP-0172) to disclose when joining.
        anonymous_domain: override the XMPP domain. Auto-discovered if not given.
        muc_domain: override the MUC domain. Auto-discovered if not given.
        timeout: seconds to keep trying to reconnect after the connection
            is lost, before giving up. 0 disables reconnecting.
        connect_timeout: seconds to wait for each network step.
        create: join the room even if it does not exist, which creates it on
            deployments that let anyone create rooms. Otherwise the existence
            of the room is checked before every join.
        stay: keep monitoring when nobody else is in the room. Otherwise the
            room counts as closed - and the monitor leaves it - as soon as
            the monitor is the only one left in it.

    Raises:
        ValueError: the conference URL cannot be parsed.
        inspect_jitsi.xmpp.JitsiConnectionError: the first connection failed,
            or the connection was lost and could not be re-established
            within ``timeout`` seconds.
    """

    # Fails early (ValueError) on a bad URL, and settles the domains once.
    ws_domain, _ = parse_conference_url(conference_url)
    anonymous_domain, muc_domain = await resolve_domains(
        ws_domain,
        anonymous_domain,
        muc_domain,
        connect_timeout,
    )
    room = _room_info(conference_url, muc_domain)

    def connect() -> JitsiXmppConnection:
        return JitsiXmppConnection(
            conference_url,
            nick,
            name=name,
            anonymous_domain=anonymous_domain,
            muc_domain=muc_domain,
            timeout=connect_timeout,
        )

    async def room_exists() -> bool:
        # Joining a room that does not exist could create it on deployments
        # that allow it - so look first, without joining.
        if create:
            return True
        return await JitsiConference(
            conference_url,
            anonymous_domain=anonymous_domain,
            muc_domain=muc_domain,
            timeout=connect_timeout,
        ).is_created()

    attempts = 0
    if not await room_exists():
        yield _state(room, None, attempts, is_open=False)
        return

    last: dict = {}
    conn = connect()
    await conn.open()
    try:
        while True:
            # Follow one connection until it ends.
            while True:
                # Alone in the room: nobody is left to monitor, so leave -
                # unless asked to stay.
                is_open = (
                    bool(conn.room_created)
                    and not conn.room_closed
                    and (stay or bool(conn.other_participants()))
                )
                state = _state(room, conn, attempts, is_open=is_open)
                if state != last:
                    last = state
                    yield copy.deepcopy(state)
                    # The room may have changed or closed while the consumer
                    # was busy - look again instead of using a stale state.
                    continue
                if not is_open:
                    return
                if conn.ended.is_set():
                    break
                conn.changed.clear()
                await conn.changed.wait()

            # Connection lost: reconnect, only counting attempts.
            error = conn.error
            await conn.close()
            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            delay = _INITIAL_RETRY_DELAY
            room_gone = False
            while True:
                if loop.time() >= deadline:
                    reason = error or "unknown error"
                    msg = f"Lost the connection to {conference_url!r}: {reason}"
                    if timeout:
                        msg += f" (could not reconnect within {timeout:g}s)"
                    raise JitsiConnectionError(msg)
                attempts += 1
                last["status"]["attempts"] = attempts
                yield copy.deepcopy(last)
                conn = connect()
                try:
                    if await room_exists():
                        await conn.open()
                    else:
                        room_gone = True
                except (JitsiConnectionError, OSError) as exc:
                    error = exc
                    await asyncio.sleep(max(0, min(delay, deadline - loop.time())))
                    delay = min(delay * 2, _MAX_RETRY_DELAY)
                else:
                    break
            if room_gone:
                last["status"]["open"] = False
                last["participants"] = []  # the room is gone, and so is everyone
                yield copy.deepcopy(last)
                return
    finally:
        await conn.close()
