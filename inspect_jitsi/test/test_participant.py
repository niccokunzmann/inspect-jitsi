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
"""Tests for `Participant.from_presence`, parsing a MUC presence stanza."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from inspect_jitsi.xmpp.participant import Participant

# A real presence stanza (anonymized), captured live from a docker-jitsi-meet
# deployment - see the connection module docstring for background.
REAL_PRESENCE = """
<presence xmlns="jabber:client" from="test@muc.meet.jitsi/486133d8">
    <stats-id>Mariane-Gpa</stats-id>
    <SourceInfo>{}</SourceInfo>
    <nick xmlns="http://jabber.org/protocol/nick">Nicco Kunzmann</nick>
    <occupant-id xmlns="urn:xmpp:occupant-id:0" id="vauNPqXDtqVuAIkJqE23tnwMIV8TyNcxp7J25IRY+Po=" />
    <x xmlns="http://jabber.org/protocol/muc#user">
        <item jid="486133d8-00c7-4027-81e3-7c849fb76996@meet.jitsi/rA7_DRbuFeiN"
              affiliation="owner" role="moderator" />
    </x>
</presence>
"""

MINIMAL_PRESENCE = """
<presence xmlns="jabber:client" from="test@muc.meet.jitsi/some-nick">
    <x xmlns="http://jabber.org/protocol/muc#user">
        <item affiliation="none" role="participant" />
    </x>
</presence>
"""


def test_parses_all_known_fields() -> None:
    participant = Participant.from_presence(ET.fromstring(REAL_PRESENCE))

    assert participant.jid == "test@muc.meet.jitsi/486133d8"
    assert participant.nick == "486133d8"
    assert participant.name == "Nicco Kunzmann"
    assert participant.role == "moderator"
    assert participant.affiliation == "owner"
    assert participant.real_jid == "486133d8-00c7-4027-81e3-7c849fb76996@meet.jitsi/rA7_DRbuFeiN"
    assert participant.occupant_id == "vauNPqXDtqVuAIkJqE23tnwMIV8TyNcxp7J25IRY+Po="


def test_missing_optional_fields_are_none() -> None:
    participant = Participant.from_presence(ET.fromstring(MINIMAL_PRESENCE))

    assert participant.jid == "test@muc.meet.jitsi/some-nick"
    assert participant.nick == "some-nick"
    assert participant.name is None
    assert participant.real_jid is None
    assert participant.occupant_id is None
    assert participant.role == "participant"
    assert participant.affiliation == "none"
