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

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xml.etree.ElementTree as ET

__all__ = ["Participant"]

_NS_MUC_USER = "http://jabber.org/protocol/muc#user"
_NS_NICK = "http://jabber.org/protocol/nick"
_NS_OCCUPANT_ID = "urn:xmpp:occupant-id:0"

_GRAVATAR_BASE_URL = "https://www.gravatar.com/avatar/"


def _gravatar_url(email: str) -> str:
    """The Gravatar URL Jitsi's own clients compute from a disclosed email.

    `?d=404` matches what Jitsi's web client requests - a 404 from this URL
    means Gravatar has nothing for this address, the same situation in
    which Jitsi's own UI falls back to showing initials instead.
    """
    normalized = email.strip().lower()
    digest = hashlib.md5(normalized.encode()).hexdigest()  # noqa: S324 - Gravatar's own addressing scheme, not a security use
    return f"{_GRAVATAR_BASE_URL}{digest}?d=404"


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

    email: str | None = None
    """Email address, if disclosed - Jitsi's own clients broadcast it in
    plain presence (unnamespaced `<email/>`) to resolve a Gravatar, the same
    way `name` is broadcast to be shown as a display name; this is not new
    exposure, just a readable copy of what every occupant already sees.
    """

    avatar_url: str | None = None
    """The avatar shown instead of this occupant's video when it's off.

    Either an explicit custom avatar - not a standardized XEP: Jitsi's own
    clients send it as a plain, unnamespaced `<avatar-url/>` in presence
    (set via the IFrame API, or by `inspect-jitsi`'s own
    `--avatar`/`avatar_url=`), matched here by tag name alone regardless of
    namespace - or, when only `email` was disclosed instead, the Gravatar
    URL Jitsi's own clients compute from it (see `email`); an explicit
    `<avatar-url/>` wins if both are present, matching Jitsi's own clients.
    Often a `data:` URI with the image embedded rather than a link to
    fetch. Either way, this library does not fetch or decode it - it is
    exactly what that occupant's client disclosed (or, for the Gravatar
    case, what it implied), so treat it as untrusted input.
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

        avatar_url = email = None
        for child in presence:
            # Unnamespaced in real traffic (like `<stats-id/>`), but matched
            # by local name alone rather than relying on that.
            local_name = child.tag.rsplit("}", 1)[-1]
            if local_name == "avatar-url" and child.text:
                avatar_url = child.text
            elif local_name == "email" and child.text:
                email = child.text

        if avatar_url is None and email is not None:
            # No custom avatar was disclosed, but an email was - the same
            # situation in which Jitsi's own clients show a Gravatar.
            avatar_url = _gravatar_url(email)

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
            email=email,
            avatar_url=avatar_url,
        )

    def to_dict(self) -> dict:
        """Return this participant as a plain, JSON-serializable dict."""
        return asdict(self)

    def to_json(self) -> str:
        """Return this participant as a JSON string."""
        return json.dumps(self.to_dict())
