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
# ruff: noqa: S311  - seeded randomness for fuzzing
"""Everything that goes into the XML we send must be escaped, whatever it is."""

from __future__ import annotations

import ast
import random
from pathlib import Path

import defusedxml.ElementTree as DefusedET
import pytest

from inspect_jitsi.test.conftest import (
    MUC_DOMAIN,
    XMPP_DOMAIN,
    handshake_script,
    join_script,
)
from inspect_jitsi.xmpp import JitsiConference, JitsiXmppConnection, stanza

NS_CLIENT = "{jabber:client}"


def chars(*codepoints: int) -> str:
    """Spelled with code points, so no formatter or editor can alter them."""
    return "".join(map(chr, codepoints))


HOSTILE = [
    "",
    " ",
    "plain",
    'quote"',
    "apos'",
    '"><evil/>',
    "' onload='x",
    "</nick><evil/>",
    "</presence><presence to='victim'/>",
    "<![CDATA[x]]>",
    "]]>",
    "&amp;",
    "&#0;",
    "&#x1;",
    "&x;",
    "&",
    "<",
    ">",
    "<?xml version='1.0'?>",
    "<!DOCTYPE d [<!ENTITY x 'y'>]>",
    "line\nbreak",
    "tab\tand\rcarriage",
    "crlf\r\nhere",
    chars(0x00) + "nul",
    chars(0x01, 0x02, 0x08, 0x0B, 0x0C, 0x0E, 0x1F),
    chars(0x7F, 0x80, 0x85, 0x9F),
    # lone surrogates, as Python uses for undecodable command line bytes
    chars(0xD800),
    chars(0xDC80),
    chars(0xDBFF, 0xDFFF),  # two lone halves in the wrong order
    chars(0xFFFE, 0xFFFF),
    chars(0xFFFD),
    "emoji " + chars(0x1F600) + " and " + chars(0x10FFFF),
    chars(0x202E) + "right-to-left" + chars(0x202C),
    chars(0x2028, 0x2029),
    "a@b/c:d",
    "x" * 100_000,
]


def _allowed(character: str) -> bool:
    """The XML 1.0 `Char` production."""
    code = ord(character)
    return (
        code in (0x9, 0xA, 0xD)
        or 0x20 <= code <= 0xD7FF
        or 0xE000 <= code <= 0xFFFD
        or 0x10000 <= code <= 0x10FFFF
    )


def cleaned(value: str) -> str:
    """What a value must look like after sending: only forbidden characters
    are replaced (by U+FFFD), nothing else is touched."""
    return "".join(c if _allowed(c) else chars(0xFFFD) for c in value)


def as_text(value: str) -> str:
    """`cleaned`, and line breaks the way a parser reads them in element text."""
    return cleaned(value).replace("\r\n", "\n").replace("\r", "\n")


def parse(xml: str):
    """Parse like the receiving side would: strictly and safely."""
    xml.encode("utf-8")  # must be sendable at all (no lone surrogates)
    return DefusedET.fromstring(xml)  # raises unless one well-formed document


def only_children(element, *tags: str) -> None:
    assert [child.tag for child in element] == list(tags)


@pytest.mark.parametrize("value", HOSTILE, ids=lambda v: repr(v[:20]))
class TestHostileValues:
    def test_stream_open(self, value: str) -> None:
        root = parse(stanza.stream_open(value))

        assert root.tag == "{urn:ietf:params:xml:ns:xmpp-framing}open"
        assert root.attrib == {"to": cleaned(value), "version": "1.0"}
        only_children(root)

    def test_join_presence(self, value: str) -> None:
        root = parse(stanza.join_presence(value, value))

        assert root.tag == f"{NS_CLIENT}presence"
        assert root.attrib == {"to": cleaned(value)}
        only_children(
            root,
            "{http://jabber.org/protocol/muc}x",
            "{http://jabber.org/protocol/nick}nick",
        )
        nick = root[1]
        assert (nick.text or "") == as_text(value)
        only_children(nick)  # the name never becomes markup

    def test_join_presence_without_name(self, value: str) -> None:
        root = parse(stanza.join_presence(value, None))

        only_children(root, "{http://jabber.org/protocol/muc}x")

    def test_join_presence_with_avatar_url(self, value: str) -> None:
        root = parse(stanza.join_presence(value, None, avatar_url=value))

        # Unnamespaced in the XML sent - but a parser resolves that to the
        # presence's own default namespace (jabber:client), same as for
        # real unnamespaced extensions like <stats-id/>.
        only_children(
            root, "{http://jabber.org/protocol/muc}x", f"{NS_CLIENT}avatar-url"
        )
        avatar = root[1]
        assert (avatar.text or "") == as_text(value)
        only_children(avatar)

    def test_join_presence_with_name_and_avatar_url(self, value: str) -> None:
        root = parse(stanza.join_presence(value, value, avatar_url=value))

        only_children(
            root,
            "{http://jabber.org/protocol/muc}x",
            "{http://jabber.org/protocol/nick}nick",
            f"{NS_CLIENT}avatar-url",
        )

    def test_join_presence_without_avatar_url(self, value: str) -> None:
        root = parse(stanza.join_presence(value, value))

        assert f"{NS_CLIENT}avatar-url" not in [child.tag for child in root]

    def test_leave_presence(self, value: str) -> None:
        root = parse(stanza.leave_presence(value))

        assert root.attrib == {"type": "unavailable", "to": cleaned(value)}
        only_children(root)

    def test_disco_info_query(self, value: str) -> None:
        root = parse(stanza.disco_info_query(value))

        assert root.tag == f"{NS_CLIENT}iq"
        assert root.attrib == {"type": "get", "to": cleaned(value), "id": "disco1"}
        only_children(root, "{http://jabber.org/protocol/disco#info}query")


def test_fixed_stanzas_are_well_formed() -> None:
    assert parse(stanza.sasl_anonymous()).attrib == {"mechanism": "ANONYMOUS"}
    bind = parse(stanza.bind_request())
    assert bind.attrib == {"type": "set", "id": "bind1"}
    only_children(bind, "{urn:ietf:params:xml:ns:xmpp-bind}bind")


@pytest.mark.parametrize("seed", range(20))
def test_random_text_never_breaks_the_structure(seed: int) -> None:
    rng = random.Random(seed)
    pieces = [*HOSTILE[:-1], "<", ">", '"', "'", "&", "]]>", chars(0), chars(0xD800)]
    for _ in range(100):
        value = "".join(
            rng.choice(pieces)
            if rng.random() < 0.5
            else chr(rng.choice([rng.randrange(0x20), rng.randrange(0x110000)]))
            for _ in range(rng.randrange(20))
        )
        root = parse(stanza.join_presence(value, value))
        only_children(
            root,
            "{http://jabber.org/protocol/muc}x",
            "{http://jabber.org/protocol/nick}nick",
        )
        assert root.attrib == {"to": cleaned(value)}
        assert (root[1].text or "") == as_text(value)
        assert parse(stanza.disco_info_query(value)).attrib["to"] == cleaned(value)


# --- through the real connection and conference ---------------------------

EVIL_URL = 'https://meet.example.com/ro"om<x>&y'
EVIL_NICK = "ni\"ck'<evil/>&" + chars(0x00, 0xD800)
EVIL_NAME = '</nick><presence to="victim"/>\n' + chars(0x0B, 0xDC80)


async def test_everything_a_connection_sends_is_well_formed(fake_server) -> None:
    room_jid = f"{EVIL_URL.rsplit('/', 1)[1].lower()}@{MUC_DOMAIN}"
    occupant = f"{room_jid}/{EVIL_NICK}"
    ws = fake_server(
        [
            *handshake_script(),
            *join_script("me"),  # (the fake server's own echo is not escaped)
        ]
    )
    conn = JitsiXmppConnection(
        EVIL_URL,
        EVIL_NICK,
        name=EVIL_NAME,
        anonymous_domain=XMPP_DOMAIN,
        muc_domain=MUC_DOMAIN,
        timeout=1,
    )
    await conn.open()
    await conn.close()

    roots = [parse(sent) for sent in ws.sent]
    assert len(roots) == 6  # open, auth, open, bind, join, leave
    join = next(
        r for r in roots if r.tag == f"{NS_CLIENT}presence" and "type" not in r.attrib
    )
    assert join.attrib == {"to": cleaned(occupant)}
    assert join[1].text == as_text(EVIL_NAME)
    only_children(
        join,
        "{http://jabber.org/protocol/muc}x",
        "{http://jabber.org/protocol/nick}nick",
    )
    leave = roots[-1]
    assert leave.attrib == {"type": "unavailable", "to": cleaned(occupant)}


async def test_a_hostile_domain_from_config_js_stays_in_its_attribute(
    fake_server,
) -> None:
    from inspect_jitsi.test.conftest import forbidden_disco_error

    ws = fake_server([*handshake_script(), forbidden_disco_error()])
    evil_domain = 'meet.jitsi"><evil/>'

    conference = JitsiConference(
        "https://meet.example.com/room",
        anonymous_domain=evil_domain,
        muc_domain='muc.<x>"',
        timeout=1,
    )
    assert await conference.is_created() is True

    roots = [parse(sent) for sent in ws.sent]
    assert roots[0].attrib["to"] == evil_domain
    assert roots[-1].attrib["to"] == 'room@muc.<x>"'
    assert all(len(list(root.iter())) <= 3 for root in roots)  # no injected elements


# --- nothing is assembled by hand -----------------------------------------

XMPP_DIR = Path(stanza.__file__).parent


@pytest.mark.parametrize("module", ["connection.py", "conference.py"])
def test_every_send_uses_a_stanza_builder(module: str) -> None:
    """Fails if anyone sends a hand-built (f-)string again."""
    tree = ast.parse((XMPP_DIR / module).read_text())
    sends = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "send"
    ]
    assert sends  # the check is looking at something
    for call in sends:
        (argument,) = call.args
        assert isinstance(argument, ast.Call), ast.unparse(call)
        assert isinstance(argument.func, ast.Name)
        assert argument.func.id in stanza.__all__, ast.unparse(call)


# --- what comes back is treated just as carefully -------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "<presence from='a" + chars(0xD800) + "'/>",
        b"<presence \xff\xfe/>",
        "<a>" + chars(0) + "</a>",
        b"\x80",
    ],
    ids=["lone-surrogate", "invalid-utf8", "nul", "binary"],
)
async def test_unparseable_replies_are_a_connection_error(fake_server, reply) -> None:
    from inspect_jitsi.test.conftest import FakeWebSocket
    from inspect_jitsi.xmpp import JitsiConnectionError
    from inspect_jitsi.xmpp.connection import _recv_stanza

    with pytest.raises(JitsiConnectionError, match="Could not parse"):
        await _recv_stanza(FakeWebSocket([reply]), 1)


def test_line_breaks_are_never_sent_raw_in_the_wrong_form() -> None:
    """Parsers rewrite a raw carriage return in text and drop attribute
    whitespace, so what is sent must already say what it means."""
    sent = stanza.join_presence("room@muc/a\r\n\t b", "x\ry\r\nz")

    assert "\r" not in sent  # no raw CR: text got a line feed, attributes a char ref
    assert "&#13;" in sent  # ... the attribute's CR survives as a reference
    assert "&#10;" in sent  # ... and so does its LF
    assert "&#09;" in sent
    root = parse(sent)
    assert root.attrib["to"] == "room@muc/a\r\n\t b"  # exactly, not normalized
    assert root[1].text == "x\ny\nz"
