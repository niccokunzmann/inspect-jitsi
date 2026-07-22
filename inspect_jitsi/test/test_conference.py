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
"""Tests for `JitsiConference`, the public handle wrapping `JitsiXmppConnection`."""

from __future__ import annotations

from inspect_jitsi.test.conftest import (
    CONFERENCE_URL,
    MUC_DOMAIN,
    ROOM_JID,
    XMPP_DOMAIN,
    forbidden_disco_error,
    handshake_script,
    join_script,
    room_not_found_disco_error,
    sasl_failure,
    stream_features_mechanisms,
    stream_open,
)
from inspect_jitsi.xmpp import JitsiConference
from inspect_jitsi.xmpp.diagnosis import DiagnosisResult

NICK = "probe-test"


def make_conference(**kwargs) -> JitsiConference:
    return JitsiConference(
        CONFERENCE_URL, NICK, anonymous_domain=XMPP_DOMAIN, muc_domain=MUC_DOMAIN, timeout=1, **kwargs
    )


async def test_open_and_get_participants(fake_server) -> None:
    fake_server([*handshake_script(), *join_script(NICK, ("alice",))])

    async with make_conference() as conference:
        participants = await conference.get_participants()
        assert [p.jid for p in participants] == [f"{ROOM_JID}/alice"]


async def test_room_and_nick_properties() -> None:
    conference = make_conference()
    assert conference.room == "testroom"
    assert conference.nick == NICK


async def test_diagnose_does_not_require_open(fake_config_js, fake_server) -> None:
    fake_server(
        [
            stream_open(),
            stream_features_mechanisms(),
            "<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>",
        ]
    )

    conference = make_conference()
    result = await conference.diagnose()

    assert isinstance(result, DiagnosisResult)
    assert result.anonymous_login_ok is True


async def test_diagnose_reports_token_required(fake_config_js, fake_server) -> None:
    fake_server([stream_open(), stream_features_mechanisms(), sasl_failure()])

    conference = make_conference()
    result = await conference.diagnose()

    assert result.anonymous_login_ok is False
    assert "token required" in result.error


async def test_is_created_true_for_an_existing_room(fake_server) -> None:
    fake_server([*handshake_script(), forbidden_disco_error()])

    conference = make_conference()
    assert await conference.is_created() is True


async def test_is_created_false_for_a_room_that_does_not_exist(fake_server) -> None:
    fake_server([*handshake_script(), room_not_found_disco_error()])

    conference = make_conference()
    assert await conference.is_created() is False


async def test_is_created_does_not_join(fake_server) -> None:
    """is_created() only sends disco#info - never a MUC-join presence."""
    ws = fake_server([*handshake_script(), forbidden_disco_error()])

    conference = make_conference()
    await conference.is_created()

    assert not any("<presence" in s and "muc" in s.lower() for s in ws.sent)
