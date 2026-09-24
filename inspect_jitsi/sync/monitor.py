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
"""`monitor_room`: follow a Jitsi Meet room synchronously until it is closed.

The blocking counterpart of
:func:`inspect_jitsi.xmpp.monitor.monitor_conference`, which it wraps.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from inspect_jitsi.xmpp.monitor import monitor_conference

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["monitor_room"]


def monitor_room(
    conference_url: str,
    nick: str | None = None,
    name: str | None = None,
    anonymous_domain: str | None = None,
    muc_domain: str | None = None,
    timeout: float = 60,
    connect_timeout: float = 10,
    create: bool = False,
    stay: bool = False,
) -> Iterator[dict[str, Any]]:
    """Yield the state of a Jitsi Meet room whenever it changes, until it is closed.

    This is what ``inspect-jitsi monitor`` prints, one dict per JSON line::

        for state in monitor_room("https://meet.example.com/SomeRoomName"):
            print(state["status"], len(state["participants"]))

    Each dict has the keys ``room``, ``participants`` (a list, in the order they
    joined) and
    ``status`` (``open`` and ``attempts``). The first one is yielded once
    connected; the last one has ``status["open"]`` false. Reconnecting after a
    lost connection only increases ``status["attempts"]``.

    Args:
        conference_url: e.g. "https://meet.example.com/SomeRoomName".
        nick: the MUC nickname to join under. Random if not given.
        name: the display name (XEP-0172) to disclose when joining.
            No display name is disclosed if not given.
        anonymous_domain: override the XMPP domain used for stream/login.
            Auto-discovered from the site's /config.js if not given.
        muc_domain: override the MUC component domain. Auto-discovered if
            not given.
        timeout: seconds to keep trying to reconnect after the connection is
            lost, before giving up. 0 disables reconnecting.
        connect_timeout: seconds to wait for each network step.
        create: join the room even if it does not exist, which creates it on
            deployments that let anyone create rooms. Otherwise a room that
            does not exist is reported as closed, without joining it.
        stay: keep monitoring when nobody else is in the room. Otherwise the
            room counts as closed - and the monitor leaves it - as soon as
            the monitor is the only one left in it.

    Raises:
        ValueError: the conference URL cannot be parsed.
        inspect_jitsi.xmpp.JitsiConnectionError: the first connection failed,
            or the connection was lost and could not be re-established
            within ``timeout`` seconds.

    """
    loop = asyncio.new_event_loop()
    states = monitor_conference(
        conference_url,
        nick=nick,
        name=name,
        anonymous_domain=anonymous_domain,
        muc_domain=muc_domain,
        timeout=timeout,
        connect_timeout=connect_timeout,
        create=create,
        stay=stay,
    )
    try:
        while True:
            try:
                yield loop.run_until_complete(anext(states))
            except StopAsyncIteration:
                return
    finally:
        # Leaves the room if the caller stops iterating early.
        loop.run_until_complete(states.aclose())
        loop.close()
