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
"""The result of probing a Jitsi deployment's reachability/auth requirements."""

from __future__ import annotations

from dataclasses import asdict, dataclass

__all__ = ["DiagnosisResult"]


@dataclass
class DiagnosisResult:
    """What's needed to read a Jitsi room's occupancy, as found by `JitsiConference.diagnose()`.

    Example::

        DiagnosisResult(
            ws_domain="meet.example.com",
            config_js_reachable=True,
            discovered_hosts={"domain": "meet.jitsi", "muc": "muc.meet.jitsi", "anonymousdomain": None},
            xmpp_domain_tried="meet.jitsi",
            domain_recognized=True,
            sasl_mechanisms=["ANONYMOUS"],
            anonymous_login_ok=True,
            error=None,
        )

    """

    ws_domain: str
    config_js_reachable: bool = False
    discovered_hosts: dict[str, str | None] | None = None
    xmpp_domain_tried: str | None = None
    domain_recognized: bool | None = None
    sasl_mechanisms: list[str] | None = None
    anonymous_login_ok: bool | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """Return a plain, JSON-serializable dict of this result."""
        return asdict(self)
