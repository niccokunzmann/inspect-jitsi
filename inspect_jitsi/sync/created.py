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
"""`is_room_created`: a one-shot check of whether a Jitsi Meet room exists.

Uses disco#info to the room JID, without joining - see
`inspect_jitsi.xmpp.JitsiConference.is_created` for details.
"""

from __future__ import annotations

import asyncio

from inspect_jitsi.xmpp.conference import JitsiConference

__all__ = ["is_room_created"]


def is_room_created(
    conference_url: str,
    anonymous_domain: str | None = None,
    muc_domain: str | None = None,
    timeout: float = 10,
) -> bool:
    """Return whether a Jitsi Meet room currently exists, without joining it.

    Args:
        conference_url: e.g. "https://meet.example.com/SomeRoomName".
        anonymous_domain: override the XMPP domain used for stream/login.
            Auto-discovered from the site's /config.js if not given.
        muc_domain: override the MUC component domain (e.g. "muc.meet.jitsi"
            or "conference.example.com"). Auto-discovered if not given.
        timeout: seconds to wait for each network step.

    Raises:
        inspect_jitsi.xmpp.JitsiConnectionError: the XMPP connection failed
            or was lost (refused, dropped, timed out, or an unparseable
            server response) - not raised for a room that simply doesn't
            exist, which is reported as `False`.

    """
    conference = JitsiConference(
        conference_url,
        anonymous_domain=anonymous_domain,
        muc_domain=muc_domain,
        timeout=timeout,
    )
    return asyncio.run(conference.is_created())
