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
"""`diagnose_jitsi_access`: a one-shot report of what's needed to read a
room's occupancy.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from inspect_jitsi.xmpp.conference import JitsiConference

if TYPE_CHECKING:
    from inspect_jitsi.xmpp.diagnosis import DiagnosisResult

__all__ = ["diagnose_jitsi_access"]


def diagnose_jitsi_access(conference_url: str, timeout: float = 10) -> DiagnosisResult:
    """Probe a Jitsi deployment and report what's needed to read occupant counts.

    See :meth:`inspect_jitsi.xmpp.JitsiConference.diagnose` for details.
    """
    return asyncio.run(JitsiConference(conference_url, timeout=timeout).diagnose())
