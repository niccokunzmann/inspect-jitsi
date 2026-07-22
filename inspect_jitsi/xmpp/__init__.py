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
"""Low-level anonymous XMPP/MUC connection to a Jitsi Meet room."""

from __future__ import annotations

from inspect_jitsi.xmpp.conference import JitsiConference
from inspect_jitsi.xmpp.connection import JitsiXmppConnection, discover_hosts
from inspect_jitsi.xmpp.diagnosis import DiagnosisResult
from inspect_jitsi.xmpp.participant import Participant

__all__ = [
    "DiagnosisResult",
    "JitsiConference",
    "JitsiXmppConnection",
    "Participant",
    "discover_hosts",
]
