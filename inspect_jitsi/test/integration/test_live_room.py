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
"""Tests replaying real traffic recorded while the room had one occupant.

Every stanza below was captured verbatim from https://meet.hosted.quelltext.eu/test
while it had exactly one person (Nicco Kunzmann) in it - see
`inspect_jitsi/test/integration/conftest.py` for how this is mocked, and
`test_empty_room.py` for the same room recorded while empty.
"""

from __future__ import annotations

from inspect_jitsi.sync import diagnose_jitsi_access, get_participant_count, get_participants
from inspect_jitsi.test.integration.conftest import (
    CONFERENCE_URL,
    NICK,
    REAL_HANDSHAKE,
    REAL_SASL_SUCCESS,
    REAL_STREAM_FEATURES_MECHANISMS,
    REAL_STREAM_OPEN,
)
from inspect_jitsi.xmpp import JitsiConference, Participant
from inspect_jitsi.xmpp.diagnosis import DiagnosisResult

# The one real occupant's presence, captured verbatim.
NICCO_KUNZMANN_PRESENCE = (
    "<presence xmlns='jabber:client' from='test@muc.meet.jitsi/486133d8'>"
    "<stats-id>Mariane-Gpa</stats-id>"
    "<c hash='sha-1' node='https://jitsi.org/jitsi-meet' ver='+mpajJhafj8jFogLBKsPbQfMgzU=' "
    "xmlns='http://jabber.org/protocol/caps'/>"
    "<SourceInfo>{}</SourceInfo>"
    "<jitsi_participant_codecList>vp8,h264,av1,vp9</jitsi_participant_codecList>"
    "<nick xmlns='http://jabber.org/protocol/nick'>Nicco Kunzmann</nick>"
    "<occupant-id xmlns='urn:xmpp:occupant-id:0' id='vauNPqXDtqVuAIkJqE23tnwMIV8TyNcxp7J25IRY+Po='/>"
    "<x xmlns='http://jabber.org/protocol/muc#user'>"
    "<item jid='486133d8-00c7-4027-81e3-7c849fb76996@meet.jitsi/rA7_DRbuFeiN' "
    "affiliation='owner' role='moderator'/></x></presence>"
)

# jicofo's own control-plane presence, captured verbatim - not a human, must be filtered out.
FOCUS_PRESENCE = (
    "<presence xmlns='jabber:client' id='TC6A8-191' xml:lang='en-US' from='test@muc.meet.jitsi/focus'>"
    "<priority>0</priority>"
    "<etherpad xmlns='http://jitsi.org/jitmeet/etherpad'>test</etherpad>"
    "<versions xmlns='http://jitsi.org/jitmeet'><component name='focus'>1.0.1153</component></versions>"
    "<conference-properties xmlns='http://jitsi.org/protocol/focus'>"
    "<property value='true' key='support-terminate-restart'/></conference-properties>"
    "<c hash='sha-1' node='http://jitsi.org/jicofo' ver='Lg0vhCNhxjoeKJi2/hukdsizNWA=' "
    "xmlns='http://jabber.org/protocol/caps'/>"
    "<occupant-id xmlns='urn:xmpp:occupant-id:0' id='kIazu8UjrgnTjEVFXzbAMOZDV04qZQgoTv+iwa5xMOc='/>"
    "<x xmlns='http://jabber.org/protocol/muc#user'>"
    "<item jid='focus@auth.meet.jitsi/focus' affiliation='owner' role='moderator'/></x></presence>"
)


def self_presence(nick: str) -> str:
    """Our own probe's presence (status code 110), shaped like the real capture."""
    return (
        f"<presence xmlns='jabber:client' from='test@muc.meet.jitsi/{nick}'>"
        "<occupant-id xmlns='urn:xmpp:occupant-id:0' id='nsfr14i3Fxj3qO56ONpev5CpRYJvFdAiACdcbWirhbs='/>"
        "<x xmlns='http://jabber.org/protocol/muc#user'>"
        "<status code='100'/>"
        "<item jid='1dce9ca1-1d4c-4e2c-933f-0b5cb50fb359@meet.jitsi/KNl_r2B3m_PW' "
        "affiliation='none' role='participant'/>"
        "<status code='110'/></x></presence>"
    )


def test_diagnose_reports_anonymous_login_ok(real_config_js, fake_server) -> None:
    fake_server([REAL_STREAM_OPEN, REAL_STREAM_FEATURES_MECHANISMS, REAL_SASL_SUCCESS])

    result = diagnose_jitsi_access(CONFERENCE_URL)

    assert isinstance(result, DiagnosisResult)
    assert result.config_js_reachable is True
    assert result.discovered_hosts == {
        "domain": "meet.jitsi",
        "muc": "muc.meet.jitsi",
        "anonymousdomain": None,
    }
    assert result.domain_recognized is True
    assert result.sasl_mechanisms == ["ANONYMOUS"]
    assert result.anonymous_login_ok is True
    assert result.error is None


def test_get_participant_count_matches_the_one_person_in_the_room(
    real_config_js, fake_server
) -> None:
    fake_server([*REAL_HANDSHAKE, NICCO_KUNZMANN_PRESENCE, FOCUS_PRESENCE, self_presence(NICK)])

    assert get_participant_count(CONFERENCE_URL, NICK) == 1


def test_get_participants_reports_nicco_kunzmann(real_config_js, fake_server) -> None:
    fake_server([*REAL_HANDSHAKE, NICCO_KUNZMANN_PRESENCE, FOCUS_PRESENCE, self_presence(NICK)])

    people = get_participants(CONFERENCE_URL, NICK)

    assert len(people) == 1
    person = people[0]
    assert isinstance(person, Participant)
    assert person.jid == "test@muc.meet.jitsi/486133d8"
    assert person.name == "Nicco Kunzmann"
    assert person.role == "moderator"
    assert person.affiliation == "owner"
    assert person.occupant_id == "vauNPqXDtqVuAIkJqE23tnwMIV8TyNcxp7J25IRY+Po="


async def test_jitsi_conference_context_manager_replaying_real_traffic(
    real_config_js, fake_server
) -> None:
    fake_server([*REAL_HANDSHAKE, NICCO_KUNZMANN_PRESENCE, FOCUS_PRESENCE, self_presence(NICK)])

    async with JitsiConference(CONFERENCE_URL, NICK) as conference:
        people = await conference.get_participants()

        assert len(people) == 1
        assert people[0].name == "Nicco Kunzmann"


async def test_is_created_true_while_occupied(real_config_js, fake_server) -> None:
    """disco#info on an occupied room is `forbidden`, not `item-not-found` -
    see test_empty_room.py for the room-doesn't-exist case."""
    forbidden_disco_error = (
        "<iq xmlns='jabber:client' id='disco1' type='error' from='test@muc.meet.jitsi'>"
        "<error type='auth'><forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/></error></iq>"
    )
    fake_server([*REAL_HANDSHAKE, forbidden_disco_error])

    conference = JitsiConference(CONFERENCE_URL)
    assert await conference.is_created() is True
