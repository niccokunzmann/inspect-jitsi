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
"""Building the XML we send, safely.

Everything that goes into a stanza is untrusted: the display name, nickname
and the room come from the person running the tool (a URL or command line
argument can contain anything, including quotes, ``<``, ``&``, newlines,
control characters or bytes that are not valid text at all), and the domains
come from the deployment's own ``/config.js``.

So no stanza is assembled by pasting a value into a string. Each one is built
as an :class:`xml.etree.ElementTree.Element` and serialized, which escapes
``&``, ``<``, ``>``, quotes and line breaks wherever the value ends up. The
one thing `ElementTree` does not do is to reject characters that XML 1.0
forbids (control characters, lone surrogates such as those Python uses for
undecodable command line bytes, U+FFFE/U+FFFF). They can not be sent at all,
not even as character references, so `_clean` replaces them with U+FFFD. Line
breaks in text are sent as a line feed, which is what a parser would make of
a carriage return anyway.

Whatever the input, what comes out is well-formed XML with the value in
exactly the place it was meant for.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

__all__ = [
    "bind_request",
    "disco_info_query",
    "join_presence",
    "leave_presence",
    "sasl_anonymous",
    "stream_open",
]

_NS_CLIENT = "jabber:client"
_NS_FRAMING = "urn:ietf:params:xml:ns:xmpp-framing"
_NS_SASL = "urn:ietf:params:xml:ns:xmpp-sasl"
_NS_BIND = "urn:ietf:params:xml:ns:xmpp-bind"
_NS_MUC = "http://jabber.org/protocol/muc"
_NS_NICK = "http://jabber.org/protocol/nick"
_NS_DISCO_INFO = "http://jabber.org/protocol/disco#info"

_FORBIDDEN_CHARACTERS = re.compile("[^\u0009\u000a\u000d -퟿-�\U00010000-\U0010ffff]")


def _clean(value: object) -> str:
    """Replace characters that can not appear in XML 1.0 with U+FFFD."""
    return _FORBIDDEN_CHARACTERS.sub("�", str(value))


def _element(
    tag: str,
    namespace: str,
    attributes: dict[str, object] | None = None,
    text: object | None = None,
) -> ET.Element:
    # The namespace is written as a plain `xmlns` attribute, which gives the
    # default namespace the XMPP framing wants (no `ns0:` prefixes).
    element = ET.Element(tag, {"xmlns": namespace})
    for key, value in (attributes or {}).items():
        element.set(key, _clean(value))
    if text is not None:
        # A raw carriage return in text is turned into a line feed by every
        # XML parser (only attributes can carry one, as `&#13;`), so say so.
        element.text = _clean(text).replace("\r\n", "\n").replace("\r", "\n")
    return element


def _serialize(element: ET.Element) -> str:
    return ET.tostring(element, encoding="unicode", short_empty_elements=True)


def stream_open(domain: str) -> str:
    """The RFC 7395 `<open/>` that starts (or restarts) a stream to `domain`."""
    return _serialize(_element("open", _NS_FRAMING, {"to": domain, "version": "1.0"}))


def sasl_anonymous() -> str:
    """Ask to authenticate with SASL ANONYMOUS."""
    return _serialize(_element("auth", _NS_SASL, {"mechanism": "ANONYMOUS"}))


def bind_request() -> str:
    """Ask the server to bind a resource."""
    iq = _element("iq", _NS_CLIENT, {"type": "set", "id": "bind1"})
    iq.append(_element("bind", _NS_BIND))
    return _serialize(iq)


def join_presence(occupant_jid: str, name: str | None) -> str:
    """Join a MUC as `occupant_jid`, disclosing `name` (XEP-0172) if given."""
    presence = _element("presence", _NS_CLIENT, {"to": occupant_jid})
    presence.append(_element("x", _NS_MUC))
    if name is not None:
        presence.append(_element("nick", _NS_NICK, text=name))
    return _serialize(presence)


def leave_presence(occupant_jid: str) -> str:
    """Leave the MUC that `occupant_jid` is in."""
    return _serialize(
        _element("presence", _NS_CLIENT, {"type": "unavailable", "to": occupant_jid})
    )


def disco_info_query(room_jid: str) -> str:
    """Ask a room for its disco#info, which tells whether it exists."""
    iq = _element("iq", _NS_CLIENT, {"type": "get", "to": room_jid, "id": "disco1"})
    iq.append(_element("query", _NS_DISCO_INFO))
    return _serialize(iq)
