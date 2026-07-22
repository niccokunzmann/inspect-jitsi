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
"""Tests for `JitsiXmppConnection` against a scripted fake XMPP server."""

from __future__ import annotations

import pytest

from inspect_jitsi.test.conftest import (
    CONFERENCE_URL,
    MUC_DOMAIN,
    ROOM_JID,
    XMPP_DOMAIN,
    error_presence,
    handshake_script,
    join_script,
    sasl_failure,
    stream_features_mechanisms,
    stream_open,
)
from inspect_jitsi.xmpp import JitsiXmppConnection

NICK = "probe-test"


def make_connection(**kwargs) -> JitsiXmppConnection:
    return JitsiXmppConnection(
        CONFERENCE_URL,
        NICK,
        anonymous_domain=XMPP_DOMAIN,
        muc_domain=MUC_DOMAIN,
        timeout=1,
        **kwargs,
    )


async def test_ws_property_raises_before_open() -> None:
    conn = make_connection()
    with pytest.raises(ConnectionError):
        conn.ws  # noqa: B018


async def test_close_without_open_is_a_noop() -> None:
    conn = make_connection()
    await conn.close()  # must not raise


async def test_open_counts_only_humans(fake_server) -> None:
    ws = fake_server([*handshake_script(), *join_script(NICK, ("alice",))])

    conn = make_connection()
    await conn.open()
    try:
        participants = await conn.get_participants()
        assert len(participants) == 1
        assert participants[0].jid == f"{ROOM_JID}/alice"
        assert participants[0].nick == "alice"
        assert await conn.get_participant_count() == 1
    finally:
        await conn.close()

    assert any("type=\"unavailable\"" in s for s in ws.sent)
    assert ws.closed


async def test_empty_room_counts_zero(fake_server) -> None:
    fake_server([*handshake_script(), *join_script(NICK)])

    async with make_connection() as conn:
        assert await conn.get_participants() == []
        assert await conn.get_participant_count() == 0


async def test_multiple_humans_are_all_counted(fake_server) -> None:
    fake_server([*handshake_script(), *join_script(NICK, ("alice", "bob"))])

    async with make_connection() as conn:
        participants = await conn.get_participants()
        assert sorted(p.jid for p in participants) == [f"{ROOM_JID}/alice", f"{ROOM_JID}/bob"]
        assert await conn.get_participant_count() == 2  # noqa: PLR2004


async def test_ws_raises_after_close(fake_server) -> None:
    fake_server([*handshake_script(), *join_script(NICK)])

    conn = make_connection()
    await conn.open()
    await conn.close()

    with pytest.raises(ConnectionError):
        conn.ws  # noqa: B018


async def test_join_error_raises_connection_error(fake_server) -> None:
    fake_server([*handshake_script(), error_presence(NICK)])

    conn = make_connection()
    with pytest.raises(ConnectionError, match="Failed to join"):
        await conn.open()


async def test_anonymous_login_rejected_raises_connection_error(fake_server) -> None:
    fake_server([stream_open(), stream_features_mechanisms(), sasl_failure()])

    conn = make_connection()
    with pytest.raises(ConnectionError, match="rejected"):
        await conn.open()
