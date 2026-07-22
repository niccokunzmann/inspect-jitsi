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
"""Tests for the high-level, one-shot `diagnose_jitsi_access`."""

from __future__ import annotations

import json

from inspect_jitsi.sync import diagnose_jitsi_access
from inspect_jitsi.test.conftest import (
    CONFERENCE_URL,
    sasl_failure,
    stream_features_mechanisms,
    stream_open,
)
from inspect_jitsi.xmpp.diagnosis import DiagnosisResult


def test_reports_successful_anonymous_login(fake_config_js, fake_server) -> None:
    fake_server(
        [
            stream_open(),
            stream_features_mechanisms(),
            "<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>",
        ]
    )

    result = diagnose_jitsi_access(CONFERENCE_URL, timeout=1)

    assert isinstance(result, DiagnosisResult)
    assert result.config_js_reachable is True
    assert result.domain_recognized is True
    assert result.sasl_mechanisms == ["ANONYMOUS"]
    assert result.anonymous_login_ok is True
    assert result.error is None


def test_reports_token_required(fake_config_js, fake_server) -> None:
    fake_server([stream_open(), stream_features_mechanisms(), sasl_failure()])

    result = diagnose_jitsi_access(CONFERENCE_URL, timeout=1)

    assert result.anonymous_login_ok is False
    assert "token required" in result.error


def test_to_dict_is_json_serializable(fake_config_js, fake_server) -> None:
    fake_server(
        [
            stream_open(),
            stream_features_mechanisms(),
            "<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>",
        ]
    )

    result = diagnose_jitsi_access(CONFERENCE_URL, timeout=1)

    json.dumps(result.to_dict())  # must not raise
