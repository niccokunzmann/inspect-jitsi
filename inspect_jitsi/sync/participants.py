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
"""`get_participants`: a one-shot list of who's in a Jitsi Meet room.

Briefly opens a :class:`~inspect_jitsi.xmpp.JitsiConference`, reads the
participant roster, and closes it again - see that class and the
`inspect_jitsi.xmpp.connection` module docstring for why joining the room is
necessary and what it means in practice (a brief join/leave blip other
participants may notice).
"""

from __future__ import annotations

import asyncio

from inspect_jitsi.xmpp.conference import JitsiConference
from inspect_jitsi.xmpp.participant import Participant

__all__ = ["get_participants"]


async def _get_participants_async(
    conference_url: str,
    nick: str | None,
    anonymous_domain: str | None,
    muc_domain: str | None,
    timeout: float,
) -> list[Participant]:
    async with JitsiConference(
        conference_url,
        nick,
        anonymous_domain=anonymous_domain,
        muc_domain=muc_domain,
        timeout=timeout,
    ) as conference:
        return await conference.get_participants()


def get_participants(
    conference_url: str,
    nick: str | None = None,
    anonymous_domain: str | None = None,
    muc_domain: str | None = None,
    timeout: float = 10,
) -> list[Participant]:
    """Return the participants currently in a Jitsi Meet room.

    Args:
        conference_url: e.g. "https://meet.example.com/SomeRoomName".
        nick: the MUC nickname to join under. Random if not given.
        anonymous_domain: override the XMPP domain used for stream/login.
            Auto-discovered from the site's /config.js if not given.
        muc_domain: override the MUC component domain (e.g. "muc.meet.jitsi"
            or "conference.example.com"). Auto-discovered if not given.
        timeout: seconds to wait for each network step.

    Returns:
        The participants already in the room, not counting this probe
        (empty if the room is empty).

    Raises:
        inspect_jitsi.xmpp.JitsiConnectionError: the XMPP connection failed
            or was lost (refused, dropped, timed out, or an unparseable
            server response).

    """
    return asyncio.run(
        _get_participants_async(conference_url, nick, anonymous_domain, muc_domain, timeout)
    )
