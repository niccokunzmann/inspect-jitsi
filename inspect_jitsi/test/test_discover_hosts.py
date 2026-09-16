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
"""Tests for `discover_hosts`, which parses a Jitsi deployment's /config.js."""

from __future__ import annotations

from typing import TYPE_CHECKING

from inspect_jitsi.test.conftest import FakeConfigJsSession
from inspect_jitsi.xmpp import connection as connection_module
from inspect_jitsi.xmpp.connection import discover_hosts

if TYPE_CHECKING:
    import pytest

# A trimmed but realistic docker-jitsi-meet config.js, as served by a real
# deployment: internal domain names differ from the public hostname, and
# hosts.muc is built from a JS string concatenation, not a plain literal.
DOCKER_JITSI_MEET_CONFIG_JS = """
var config = {};
config.hosts = {};
config.hosts.domain = 'meet.jitsi';
var subdomain = '';
config.hosts.muc = 'muc.' + subdomain + 'meet.jitsi';
config.bosh = 'https://meet.example.com/http-bind';
config.websocket = 'wss://meet.example.com/xmpp-websocket';
"""

CONFIG_JS_WITH_ANONYMOUS_DOMAIN = """
config.hosts = {};
config.hosts.domain = 'meet.example.com';
config.hosts.anonymousdomain = 'guest.meet.example.com';
config.hosts.muc = 'conference.meet.example.com';
"""


def _serve(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(
        connection_module.niquests, "AsyncSession", lambda: FakeConfigJsSession(text)
    )


async def test_discovers_docker_jitsi_meet_style_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve(monkeypatch, DOCKER_JITSI_MEET_CONFIG_JS)

    hosts = await discover_hosts("meet.example.com")

    assert hosts == {
        "domain": "meet.jitsi",
        "muc": "muc.meet.jitsi",
        "anonymousdomain": None,
    }


async def test_discovers_explicit_anonymous_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve(monkeypatch, CONFIG_JS_WITH_ANONYMOUS_DOMAIN)

    hosts = await discover_hosts("meet.example.com")

    assert hosts == {
        "domain": "meet.example.com",
        "muc": "conference.meet.example.com",
        "anonymousdomain": "guest.meet.example.com",
    }


async def test_missing_config_js_fields_are_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _serve(monkeypatch, "var config = {};")

    hosts = await discover_hosts("meet.example.com")

    assert hosts == {"domain": None, "muc": None, "anonymousdomain": None}
