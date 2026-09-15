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
"""Tools for inspecting a running Jitsi Meet deployment."""

from __future__ import annotations

from inspect_jitsi.sync import (
    diagnose_jitsi_access,
    get_participant_count,
    get_participants,
    is_room_created,
)
from inspect_jitsi.xmpp import (
    DiagnosisResult,
    JitsiConference,
    JitsiConnectionError,
    JitsiXmppConnection,
    Participant,
    discover_hosts,
)

__all__ = [
    "DiagnosisResult",
    "JitsiConference",
    "JitsiConnectionError",
    "JitsiXmppConnection",
    "Participant",
    "diagnose_jitsi_access",
    "discover_hosts",
    "get_participant_count",
    "get_participants",
    "is_room_created",
]
