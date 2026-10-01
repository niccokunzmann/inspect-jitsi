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

import hashlib
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

# A real presence stanza (anonymized), captured live from
# meet.hosted.quelltext.eu - a deployment broadcasting an email (to resolve
# a Gravatar) rather than a custom avatar-url.
REAL_PRESENCE_WITH_EMAIL = """
<presence xmlns="jabber:client" from="test@muc.meet.jitsi/25d4f27f">
    <stats-id>Eddie-U1O</stats-id>
    <jitsi_participant_codecList>vp8,vp9,h264,av1</jitsi_participant_codecList>
    <email>test-user@example.com</email>
    <nick xmlns="http://jabber.org/protocol/nick">Test User</nick>
    <SourceInfo>{}</SourceInfo>
    <occupant-id xmlns="urn:xmpp:occupant-id:0" id="x" />
    <x xmlns="http://jabber.org/protocol/muc#user">
        <item affiliation="owner" role="moderator" jid="x@meet.jitsi/y" />
    </x>
</presence>
"""

AVATAR_PRESENCE = """
<presence xmlns="jabber:client" from="test@muc.meet.jitsi/some-nick">
    <avatar-url>https://example.com/avatar.png</avatar-url>
    <x xmlns="http://jabber.org/protocol/muc#user">
        <item affiliation="none" role="participant" />
    </x>
</presence>
"""

EMPTY_AVATAR_PRESENCE = """
<presence xmlns="jabber:client" from="test@muc.meet.jitsi/some-nick">
    <avatar-url></avatar-url>
    <x xmlns="http://jabber.org/protocol/muc#user">
        <item affiliation="none" role="participant" />
    </x>
</presence>
"""

EMPTY_EMAIL_PRESENCE = """
<presence xmlns="jabber:client" from="test@muc.meet.jitsi/some-nick">
    <email></email>
    <x xmlns="http://jabber.org/protocol/muc#user">
        <item affiliation="none" role="participant" />
    </x>
</presence>
"""

AVATAR_AND_EMAIL_PRESENCE = """
<presence xmlns="jabber:client" from="test@muc.meet.jitsi/some-nick">
    <email>test-user@example.com</email>
    <avatar-url>https://example.com/avatar.png</avatar-url>
    <x xmlns="http://jabber.org/protocol/muc#user">
        <item affiliation="none" role="participant" />
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
    assert (
        participant.real_jid
        == "486133d8-00c7-4027-81e3-7c849fb76996@meet.jitsi/rA7_DRbuFeiN"
    )
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
    assert participant.email is None
    assert participant.avatar_url is None


def test_real_presence_has_no_avatar_url_or_email() -> None:
    participant = Participant.from_presence(ET.fromstring(REAL_PRESENCE))
    assert participant.avatar_url is None
    assert participant.email is None


# --- avatar-url --------------------------------------------------------


def test_avatar_url_is_parsed_whatever_its_namespace() -> None:
    for xmlns in ("", ' xmlns="jabber:client"', ' xmlns="some:other:ns"'):
        presence = AVATAR_PRESENCE.replace("<avatar-url>", f"<avatar-url{xmlns}>")
        participant = Participant.from_presence(ET.fromstring(presence))
        assert participant.avatar_url == "https://example.com/avatar.png"


def test_empty_avatar_url_element_is_none() -> None:
    participant = Participant.from_presence(ET.fromstring(EMPTY_AVATAR_PRESENCE))
    assert participant.avatar_url is None


def test_to_dict_includes_avatar_url() -> None:
    participant = Participant.from_presence(ET.fromstring(AVATAR_PRESENCE))
    assert participant.to_dict()["avatar_url"] == "https://example.com/avatar.png"


# --- email, and its Gravatar fallback for avatar_url --------------------


def test_email_only_falls_back_to_a_gravatar_avatar_url() -> None:
    participant = Participant.from_presence(ET.fromstring(REAL_PRESENCE_WITH_EMAIL))

    assert participant.email == "test-user@example.com"
    expected_hash = hashlib.md5(b"test-user@example.com").hexdigest()  # noqa: S324
    assert (
        participant.avatar_url
        == f"https://www.gravatar.com/avatar/{expected_hash}?d=404"
    )


def test_gravatar_hash_ignores_case_and_surrounding_whitespace() -> None:
    presence = REAL_PRESENCE_WITH_EMAIL.replace(
        "test-user@example.com", "  Test-User@Example.com  "
    )
    participant = Participant.from_presence(ET.fromstring(presence))

    expected_hash = hashlib.md5(b"test-user@example.com").hexdigest()  # noqa: S324
    assert (
        participant.avatar_url
        == f"https://www.gravatar.com/avatar/{expected_hash}?d=404"
    )


def test_empty_email_element_is_none_and_no_gravatar_fallback() -> None:
    participant = Participant.from_presence(ET.fromstring(EMPTY_EMAIL_PRESENCE))
    assert participant.email is None
    assert participant.avatar_url is None


def test_explicit_avatar_url_wins_over_the_gravatar_fallback() -> None:
    participant = Participant.from_presence(ET.fromstring(AVATAR_AND_EMAIL_PRESENCE))

    assert participant.email == "test-user@example.com"
    assert participant.avatar_url == "https://example.com/avatar.png"


def test_to_dict_includes_email() -> None:
    participant = Participant.from_presence(ET.fromstring(REAL_PRESENCE_WITH_EMAIL))
    assert participant.to_dict()["email"] == "test-user@example.com"
