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
"""A single occupant of a Jitsi Meet room's MUC."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

__all__ = ["Participant"]

_NS_MUC_USER = "http://jabber.org/protocol/muc#user"
_NS_NICK = "http://jabber.org/protocol/nick"
_NS_OCCUPANT_ID = "urn:xmpp:occupant-id:0"


@dataclass(frozen=True)
class Participant:
    """One occupant of a room, parsed from their MUC presence stanza."""

    jid: str
    """The MUC occupant JID, e.g. "room@muc.example.com/<nick-resource>"."""

    nick: str
    """The MUC nickname - the resourcepart of `jid`."""

    name: str | None = None
    """Human display name, if the client sent one (XEP-0172 <nick/>)."""

    role: str | None = None
    """MUC role, e.g. "moderator", "participant"."""

    affiliation: str | None = None
    """MUC affiliation, e.g. "owner", "member", "none"."""

    real_jid: str | None = None
    """The occupant's real (non-anonymous, but still internal) JID, if disclosed."""

    occupant_id: str | None = None
    """Stable per-session anonymous id (XEP occupant-id), if disclosed.

    Unlike `jid`/`nick`, this stays the same for one occupant across the
    conference even where the MUC nick is a random per-join identifier -
    useful for telling "still the same person" from "someone new".
    """

    @classmethod
    def from_presence(cls, presence: ET.Element) -> Participant:
        """Build a Participant from a MUC <presence/> stanza."""
        from_jid = presence.get("from") or ""
        nick = from_jid.rsplit("/", 1)[-1]

        name = None
        nick_element = presence.find(f"{{{_NS_NICK}}}nick")
        if nick_element is not None and nick_element.text:
            name = nick_element.text

        occupant_id = None
        occupant_id_element = presence.find(f"{{{_NS_OCCUPANT_ID}}}occupant-id")
        if occupant_id_element is not None:
            occupant_id = occupant_id_element.get("id")

        role = affiliation = real_jid = None
        muc_x = presence.find(f"{{{_NS_MUC_USER}}}x")
        if muc_x is not None:
            item = muc_x.find(f"{{{_NS_MUC_USER}}}item")
            if item is not None:
                role = item.get("role")
                affiliation = item.get("affiliation")
                real_jid = item.get("jid")

        return cls(
            jid=from_jid,
            nick=nick,
            name=name,
            role=role,
            affiliation=affiliation,
            real_jid=real_jid,
            occupant_id=occupant_id,
        )

    def to_dict(self) -> dict:
        """Return this participant as a plain, JSON-serializable dict."""
        return asdict(self)

    def to_json(self) -> str:
        """Return this participant as a JSON string."""
        return json.dumps(self.to_dict())
