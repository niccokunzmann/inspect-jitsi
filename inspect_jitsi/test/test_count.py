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
"""Tests for the high-level, one-shot `get_participant_count`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inspect_jitsi.sync import get_participant_count
from inspect_jitsi.test.conftest import (
    CONFERENCE_URL,
    MUC_DOMAIN,
    XMPP_DOMAIN,
    handshake_script,
    join_script,
)

if TYPE_CHECKING:
    import pytest

NICK = "probe-test"


def test_get_participant_count(fake_server) -> None:
    fake_server([*handshake_script(), *join_script(NICK, ("alice",))])

    count = get_participant_count(
        CONFERENCE_URL,
        NICK,
        anonymous_domain=XMPP_DOMAIN,
        muc_domain=MUC_DOMAIN,
        timeout=1,
    )

    assert count == 1


def test_get_participant_count_empty_room(fake_server) -> None:
    fake_server([*handshake_script(), *join_script(NICK)])

    count = get_participant_count(
        CONFERENCE_URL,
        NICK,
        anonymous_domain=XMPP_DOMAIN,
        muc_domain=MUC_DOMAIN,
        timeout=1,
    )

    assert count == 0


def test_get_participant_count_discloses_a_custom_display_name(fake_server) -> None:
    ws = fake_server([*handshake_script(), *join_script(NICK)])

    get_participant_count(
        CONFERENCE_URL,
        NICK,
        name="Alice",
        anonymous_domain=XMPP_DOMAIN,
        muc_domain=MUC_DOMAIN,
        timeout=1,
    )

    join_presence = next(s for s in ws.sent if "<x xmlns=" in s)
    assert '<nick xmlns="http://jabber.org/protocol/nick">Alice</nick>' in join_presence


def test_get_participant_count_with_random_nick(
    monkeypatch: pytest.MonkeyPatch, fake_server
) -> None:
    """Without a fixed nick, self-presence is still recognized (by status code, not JID)."""

    class _FixedUUID:
        hex = "deadbeefcafef00d"

    monkeypatch.setattr("inspect_jitsi.xmpp.connection.uuid.uuid4", _FixedUUID)
    random_nick = f"inspect-jitsi-{_FixedUUID.hex[:8]}"

    fake_server([*handshake_script(), *join_script(random_nick, ("alice", "bob"))])

    count = get_participant_count(
        CONFERENCE_URL, anonymous_domain=XMPP_DOMAIN, muc_domain=MUC_DOMAIN, timeout=1
    )

    assert count == 2
