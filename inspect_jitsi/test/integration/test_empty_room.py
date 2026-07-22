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
"""Tests replaying real traffic recorded while the room was empty.

Once the one occupant in `test_live_room.py` left, the room was destroyed -
docker-jitsi-meet restricts room creation to jicofo, so joining or querying
an empty https://meet.hosted.quelltext.eu/test now gets rejected rather than
just returning nothing. Both error stanzas below are captured verbatim from
that real, live server:

- Joining (a bare MUC presence) gets `<not-allowed/>` ("Room creation is
  restricted") - `JitsiXmppConnection.open()` must treat this as an empty
  room (0 participants), not raise. This is the exact error that surfaced as
  a bug via `inspect-jitsi participants` before that handling was added.
- `disco#info` (used by `is_created()`) gets `<item-not-found/>`, distinct
  from the `forbidden` an *occupied* room returns (see test_live_room.py) -
  that's how `is_created()` tells "doesn't exist" from "exists but disco is
  occupant-only" apart, without joining.
"""

from __future__ import annotations

from inspect_jitsi.sync import get_participant_count, get_participants, is_room_created
from inspect_jitsi.test.integration.conftest import CONFERENCE_URL, NICK, REAL_HANDSHAKE
from inspect_jitsi.xmpp import JitsiConference, JitsiXmppConnection

# Captured verbatim from a real `inspect-jitsi participants` run against the
# now-empty room (nick anonymized to {nick} - real runs get a random one).
ROOM_CREATION_RESTRICTED_PRESENCE = (
    "<presence xmlns='jabber:client' type='error' "
    "to='f3bc1eca-1ed3-4f72-858c-e7348a6595e9@meet.jitsi/h1r5Cqi63Suo' "
    "from='test@muc.meet.jitsi/{nick}'>"
    "<error type='cancel' by='muc.meet.jitsi'>"
    "<not-allowed xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>"
    "<text xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'>Room creation is restricted</text>"
    "</error></presence>"
)

# Captured verbatim from a live disco#info probe against the same empty room.
ITEM_NOT_FOUND_DISCO_ERROR = (
    "<iq xmlns='jabber:client' id='disco1' "
    "to='7e0414ec-47f2-4878-a5bf-c0fc3903b319@meet.jitsi/UKI9yu0baLAi' "
    "type='error' from='test@muc.meet.jitsi'>"
    "<error type='cancel' by='muc.meet.jitsi'>"
    "<item-not-found xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>"
    "</error></iq>"
)


async def test_open_does_not_raise_and_reports_room_not_created(real_config_js, fake_server) -> None:
    ws = fake_server([*REAL_HANDSHAKE, ROOM_CREATION_RESTRICTED_PRESENCE.format(nick=NICK)])

    conn = JitsiXmppConnection(CONFERENCE_URL, NICK)
    await conn.open()  # must not raise
    try:
        assert conn.room_created is False
        assert await conn.get_participants() == []
        assert await conn.get_participant_count() == 0
    finally:
        await conn.close()

    # We never actually became an occupant, so there's nothing to leave.
    assert not any('type="unavailable"' in s for s in ws.sent)


def test_get_participant_count_is_zero(real_config_js, fake_server) -> None:
    fake_server([*REAL_HANDSHAKE, ROOM_CREATION_RESTRICTED_PRESENCE.format(nick=NICK)])

    assert get_participant_count(CONFERENCE_URL, NICK) == 0


def test_get_participants_is_empty(real_config_js, fake_server) -> None:
    fake_server([*REAL_HANDSHAKE, ROOM_CREATION_RESTRICTED_PRESENCE.format(nick=NICK)])

    assert get_participants(CONFERENCE_URL, NICK) == []


def test_is_room_created_is_false(real_config_js, fake_server) -> None:
    fake_server([*REAL_HANDSHAKE, ITEM_NOT_FOUND_DISCO_ERROR])

    assert is_room_created(CONFERENCE_URL) is False


async def test_jitsi_conference_is_created_is_false(real_config_js, fake_server) -> None:
    fake_server([*REAL_HANDSHAKE, ITEM_NOT_FOUND_DISCO_ERROR])

    conference = JitsiConference(CONFERENCE_URL)
    assert await conference.is_created() is False
