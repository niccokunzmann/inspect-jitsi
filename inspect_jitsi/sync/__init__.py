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
"""Synchronous, one-shot convenience functions built on :mod:`inspect_jitsi.xmpp`."""

from __future__ import annotations

from inspect_jitsi.sync.count import get_participant_count
from inspect_jitsi.sync.created import is_room_created
from inspect_jitsi.sync.diagnose import diagnose_jitsi_access
from inspect_jitsi.sync.participants import get_participants

__all__ = [
    "diagnose_jitsi_access",
    "get_participant_count",
    "get_participants",
    "is_room_created",
]
