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
"""Tests for `parse_conference_url`."""

from __future__ import annotations

import pytest

from inspect_jitsi.xmpp.connection import parse_conference_url


@pytest.mark.parametrize(
    ("url", "expected_domain", "expected_room"),
    [
        ("https://meet.example.com/SomeRoom", "meet.example.com", "SomeRoom"),
        ("http://meet.example.com/SomeRoom", "meet.example.com", "SomeRoom"),
        ("meet.example.com/SomeRoom", "meet.example.com", "SomeRoom"),
        ("https://meet.example.com/SomeRoom/", "meet.example.com", "SomeRoom"),
        ("https://meet.example.com/SomeRoom?jwt=abc", "meet.example.com", "SomeRoom"),
    ],
)
def test_parses_domain_and_room(url: str, expected_domain: str, expected_room: str) -> None:
    domain, room = parse_conference_url(url)
    assert domain == expected_domain
    assert room == expected_room


@pytest.mark.parametrize("url", ["https://meet.example.com/", "https://meet.example.com", ""])
def test_raises_without_a_room(url: str) -> None:
    with pytest.raises(ValueError, match="Could not parse"):
        parse_conference_url(url)
