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
"""Shared, real-traffic fixtures for https://meet.hosted.quelltext.eu/test.

Every stanza and /config.js body below was captured verbatim from that real,
live docker-jitsi-meet deployment - see `inspect_jitsi/xmpp/connection.py`
for background on why a MUC join (not disco#info) is needed to read room
occupancy at all.

Unlike a true integration test, none of these touch the network: the
WebSocket and /config.js calls are mocked (see `fake_server`/`../conftest.py`),
replaying the recorded stanzas so tests are fast and deterministic - while
still exercising the exact shape of real Jitsi traffic rather than synthetic
fixtures.
"""

from __future__ import annotations

import pytest

from inspect_jitsi.test.conftest import FakeConfigJsSession

WS_DOMAIN = "meet.hosted.quelltext.eu"
ROOM = "test"
CONFERENCE_URL = f"https://{WS_DOMAIN}/{ROOM}"
ROOM_JID = f"{ROOM}@muc.meet.jitsi"
NICK = "inspect-jitsi-test-probe"

# The real /config.js this deployment serves (docker-jitsi-meet default: the
# internal domain "meet.jitsi" differs from the public hostname above).
REAL_CONFIG_JS = """
config.hosts.domain = 'meet.jitsi';
var subdomain = '';
config.hosts.muc = 'muc.' + subdomain + 'meet.jitsi';
config.bosh = 'https://meet.hosted.quelltext.eu:443/http-bind';
config.websocket = 'wss://meet.hosted.quelltext.eu:443/xmpp-websocket';
"""

# The stream-open/SASL/bind handshake, captured verbatim.
REAL_STREAM_OPEN = (
    "<open id='bed223f2-d392-484b-a97e-885fc6b97791' "
    "xmlns='urn:ietf:params:xml:ns:xmpp-framing' version='1.0' "
    "xml:lang='en' from='meet.jitsi'/>"
)
REAL_STREAM_FEATURES_MECHANISMS = (
    "<stream:features xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>"
    "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'><mechanism>ANONYMOUS</mechanism></mechanisms>"
    "<limits xmlns='urn:xmpp:stream-limits:0'><max-bytes>262144</max-bytes>"
    "<idle-seconds>840</idle-seconds></limits></stream:features>"
)
REAL_SASL_SUCCESS = "<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>"
REAL_STREAM_FEATURES_BIND = (
    "<stream:features xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>"
    "<bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'><required/></bind>"
    "<session xmlns='urn:ietf:params:xml:ns:xmpp-session'><optional/></session>"
    "<sub xmlns='urn:xmpp:features:pre-approval'/>"
    "<c hash='sha-1' xmlns='http://jabber.org/protocol/caps' node='http://prosody.im' "
    "ver='THdt677prduC0lZSfCaZ/32L7aA='/>"
    "<sm xmlns='urn:xmpp:sm:2'><optional/></sm><sm xmlns='urn:xmpp:sm:3'><optional/></sm>"
    "<ver xmlns='urn:xmpp:features:rosterver'/>"
    "<limits xmlns='urn:xmpp:stream-limits:0'><max-bytes>262144</max-bytes>"
    "<idle-seconds>840</idle-seconds></limits></stream:features>"
)
REAL_BIND_RESULT = (
    "<iq xmlns='jabber:client' id='bind1' type='result'>"
    "<bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
    "<jid>52ccd991-ed4c-4f48-ad08-6ef55f60d79c@meet.jitsi/Sohc8wJ9SAbt</jid></bind></iq>"
)

REAL_HANDSHAKE = [
    REAL_STREAM_OPEN,
    REAL_STREAM_FEATURES_MECHANISMS,
    REAL_SASL_SUCCESS,
    REAL_STREAM_OPEN,
    REAL_STREAM_FEATURES_BIND,
    REAL_BIND_RESULT,
]


@pytest.fixture
def real_config_js(monkeypatch: pytest.MonkeyPatch):
    """Serve the recorded, real /config.js for WS_DOMAIN."""
    import inspect_jitsi.xmpp.connection as connection_module

    monkeypatch.setattr(
        connection_module.niquests,
        "AsyncSession",
        lambda: FakeConfigJsSession(REAL_CONFIG_JS),
    )
