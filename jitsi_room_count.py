"""
Get the number of people currently in a Jitsi Meet room, from just its URL.

Jitsi's prosody deployment locks down disco#info on MUC rooms to occupants
only (confirmed live: a bare disco#info query gets `<error type="auth">
<forbidden/></error>`), so the usual XEP-0045 "peek without joining" trick
does not work here. Instead this briefly joins the room as a real (if
anonymous) occupant over an XMPP connection carried by WebSocket (the same
"wss://<domain>/xmpp-websocket" endpoint the web client uses), reads the
roster of <presence> stanzas the MUC sends back on join, then leaves. This
does mean the room briefly gains (and loses) one occupant - anyone already
in the room may see a transient join/leave notification.

jicofo (the conference focus component) also joins every active Jitsi
conference's MUC as a pseudo-participant nicknamed "focus" - that occupant
is filtered out so the returned count reflects only humans.

No Python XMPP library (slixmpp, aioxmpp, ...) supports the WebSocket
transport Jitsi requires - they're TCP-only, and Jitsi deployments generally
don't expose raw XMPP client-to-server (5222) publicly - so this hand-rolls
the small slice of RFC 6120 (stream/SASL/bind) and RFC 7395 (XMPP over
WebSocket framing) needed to join a MUC room.

Requires: pip install websockets

Deployments (e.g. docker-jitsi-meet) commonly use an *internal* XMPP domain
(typically "meet.jitsi") and MUC component (typically "muc.meet.jitsi") that
are different from the public hostname in the URL - the public web server
proxies the WebSocket through, but the XMPP stream's `to` attribute and the
MUC room JID must use the internal names. `get_participant_count` figures
these out automatically by reading the site's public /config.js (the same
file the browser client itself relies on), rather than guessing.
"""

import asyncio
import re
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import websockets

_NS_FRAMING = "urn:ietf:params:xml:ns:xmpp-framing"
_NS_SASL = "urn:ietf:params:xml:ns:xmpp-sasl"
_NS_BIND = "urn:ietf:params:xml:ns:xmpp-bind"
_NS_MUC = "http://jabber.org/protocol/muc"
_NS_MUC_USER = "http://jabber.org/protocol/muc#user"


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_conference_url(conference_url: str) -> tuple[str, str]:
    if "://" not in conference_url:
        conference_url = f"https://{conference_url}"
    parsed = urlparse(conference_url)
    domain = parsed.netloc
    room = parsed.path.strip("/").split("/")[0]
    if not domain or not room:
        raise ValueError(f"Could not parse a Jitsi domain/room from URL: {conference_url!r}")
    return domain, room


def _eval_js_string_concat(expr: str, variables: dict[str, str]) -> str:
    """Best-effort evaluator for simple JS `'a' + b + 'c'` string concatenations."""
    result = []
    for token in expr.split("+"):
        token = token.strip()
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
            result.append(token[1:-1])
        elif token in variables:
            result.append(variables[token])
    return "".join(result)


def discover_hosts(domain: str, timeout: float = 10) -> dict:
    """
    Read https://<domain>/config.js to find the real XMPP/MUC/anonymous
    domains a Jitsi deployment uses, since these often differ from the
    public hostname (e.g. docker-jitsi-meet defaults to "meet.jitsi"
    internally). Returns a dict with keys "domain", "muc", "anonymousdomain"
    - any of which may be None if not found.
    """
    url = f"https://{domain}/config.js"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")

    variables = {}
    for match in re.finditer(r"var\s+(\w+)\s*=\s*('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\s*;", text):
        name, literal = match.group(1), match.group(2)
        variables[name] = literal[1:-1]

    hosts: dict[str, str | None] = {"domain": None, "muc": None, "anonymousdomain": None}
    for key in hosts:
        match = re.search(rf"hosts\.{key}\s*=\s*([^;]+);", text)
        if match:
            hosts[key] = _eval_js_string_concat(match.group(1), variables) or None
    return hosts


async def _recv_stanza(ws, timeout: float) -> ET.Element:
    async with asyncio.timeout(timeout):
        message = await ws.recv()
    return ET.fromstring(message)


def _is_self_presence(presence: ET.Element) -> bool:
    """True for the occupant's own presence, marked by MUC status code 110."""
    muc_x = presence.find(f"{{{_NS_MUC_USER}}}x")
    if muc_x is None:
        return False
    return any(
        _local(status.tag) == "status" and status.get("code") == "110"
        for status in muc_x
    )


async def _open_authenticated_stream(ws, xmpp_domain: str, timeout: float) -> None:
    await ws.send(f'<open xmlns="{_NS_FRAMING}" to="{xmpp_domain}" version="1.0"/>')
    opened = await _recv_stanza(ws, timeout)
    if _local(opened.tag) == "error":
        raise RuntimeError(
            f"Stream error opening to {xmpp_domain!r}: {ET.tostring(opened, encoding='unicode')}"
        )
    await _recv_stanza(ws, timeout)  # <stream:features>

    await ws.send(f'<auth xmlns="{_NS_SASL}" mechanism="ANONYMOUS"/>')
    result = await _recv_stanza(ws, timeout)
    if _local(result.tag) != "success":
        raise RuntimeError(
            f"Anonymous XMPP login to {xmpp_domain!r} was rejected: "
            f"{ET.tostring(result, encoding='unicode')}"
        )

    # Restart the stream post-auth, as required by RFC 6120.
    await ws.send(f'<open xmlns="{_NS_FRAMING}" to="{xmpp_domain}" version="1.0"/>')
    await _recv_stanza(ws, timeout)  # <open>
    await _recv_stanza(ws, timeout)  # <stream:features> (bind, ...)

    # Bind a resource so we have a full JID to send IQs from.
    await ws.send(f'<iq xmlns="jabber:client" type="set" id="bind1"><bind xmlns="{_NS_BIND}"/></iq>')
    await _recv_stanza(ws, timeout)


async def _get_participant_count_async(
    ws_domain: str, xmpp_domain: str, room_jid: str, timeout: float
) -> int:
    ws_url = f"wss://{ws_domain}/xmpp-websocket"
    nick = f"room-count-probe-{uuid.uuid4().hex[:8]}"
    occupant_jid = f"{room_jid}/{nick}"

    async with websockets.connect(
        ws_url, subprotocols=["xmpp"], open_timeout=timeout
    ) as ws:
        await _open_authenticated_stream(ws, xmpp_domain, timeout)

        # Joining a MUC room is just sending presence to <room>/<nick>.
        await ws.send(
            f'<presence xmlns="jabber:client" to="{occupant_jid}">'
            f'<x xmlns="{_NS_MUC}"/></presence>'
        )

        # The MUC replies with one <presence> per current occupant, and our
        # own (marked with status code 110) arrives last - that's the signal
        # the roster is complete.
        occupant_jids: set[str] = set()
        try:
            async with asyncio.timeout(timeout):
                while True:
                    stanza = await _recv_stanza(ws, timeout)
                    if _local(stanza.tag) != "presence":
                        continue

                    if stanza.get("type") == "error":
                        raise RuntimeError(
                            f"Failed to join room {room_jid!r}: "
                            f"{ET.tostring(stanza, encoding='unicode')}"
                        )

                    if stanza.get("type") != "unavailable":
                        from_jid = stanza.get("from")
                        # jicofo joins every active Jitsi conference's MUC as
                        # a control-plane pseudo-participant nicknamed
                        # "focus" (from="room@muc.domain/focus") - not a
                        # human, so it shouldn't count.
                        if from_jid and from_jid.rsplit("/", 1)[-1] != "focus":
                            occupant_jids.add(from_jid)

                    if _is_self_presence(stanza):
                        break
        finally:
            # Leave the room again regardless of how the above went.
            await ws.send(
                f'<presence xmlns="jabber:client" type="unavailable" to="{occupant_jid}"/>'
            )

        occupant_jids.discard(occupant_jid)
        return len(occupant_jids)


def get_participant_count(
    conference_url: str,
    anonymous_domain: str | None = None,
    muc_domain: str | None = None,
    timeout: float = 10,
) -> int:
    """
    Return the number of participants currently in a Jitsi Meet room.

    Briefly joins the room as an anonymous occupant to read the presence
    roster, then leaves - see the module docstring for why this is necessary
    (disco#info without joining is forbidden by Jitsi's MUC config) and its
    side effect (a transient join/leave notification for other occupants).

    Args:
        conference_url: e.g. "https://meet.example.com/SomeRoomName".
        anonymous_domain: override the XMPP domain used for stream/login.
            Auto-discovered from the site's /config.js if not given.
        muc_domain: override the MUC component domain (e.g. "muc.meet.jitsi"
            or "conference.example.com"). Auto-discovered if not given.
        timeout: seconds to wait for each network step.

    Returns:
        Number of people already in the room, not counting this probe
        (0 if the room is empty).
    """
    ws_domain, room = _parse_conference_url(conference_url)

    if anonymous_domain is None or muc_domain is None:
        try:
            hosts = discover_hosts(ws_domain, timeout=timeout)
        except Exception:
            hosts = {"domain": None, "muc": None, "anonymousdomain": None}
        xmpp_domain = hosts["domain"] or ws_domain
        anonymous_domain = anonymous_domain or hosts["anonymousdomain"] or xmpp_domain
        muc_domain = muc_domain or hosts["muc"] or f"conference.{xmpp_domain}"
    else:
        xmpp_domain = anonymous_domain

    room_jid = f"{room.lower()}@{muc_domain}"

    return asyncio.run(
        _get_participant_count_async(ws_domain, anonymous_domain, room_jid, timeout)
    )


def diagnose_jitsi_access(conference_url: str, timeout: float = 10) -> dict:
    """
    Probe a Jitsi deployment and report what's needed to read room occupant
    counts: whether /config.js was readable, which internal domains it
    advertises, whether the XMPP domain is actually served over the
    WebSocket endpoint, which SASL mechanisms it offers, and whether
    anonymous login succeeds (i.e. whether a token/JWT is required).

    Returns a dict, safe to print/json.dumps, e.g.:
        {
            "ws_domain": "meet.example.com",
            "config_js_reachable": True,
            "discovered_hosts": {"domain": "meet.jitsi", "muc": "muc.meet.jitsi", "anonymousdomain": None},
            "xmpp_domain_tried": "meet.jitsi",
            "domain_recognized": True,
            "sasl_mechanisms": ["ANONYMOUS"],
            "anonymous_login_ok": True,
            "error": None,
        }
    """
    ws_domain, _ = _parse_conference_url(conference_url)
    report: dict = {
        "ws_domain": ws_domain,
        "config_js_reachable": False,
        "discovered_hosts": None,
        "xmpp_domain_tried": None,
        "domain_recognized": None,
        "sasl_mechanisms": None,
        "anonymous_login_ok": None,
        "error": None,
    }

    try:
        hosts = discover_hosts(ws_domain, timeout=timeout)
        report["config_js_reachable"] = True
        report["discovered_hosts"] = hosts
        xmpp_domain = hosts["anonymousdomain"] or hosts["domain"] or ws_domain
    except Exception as exc:
        xmpp_domain = ws_domain
        report["error"] = f"config.js: {exc}"

    report["xmpp_domain_tried"] = xmpp_domain

    async def probe():
        ws_url = f"wss://{ws_domain}/xmpp-websocket"
        async with websockets.connect(ws_url, subprotocols=["xmpp"], open_timeout=timeout) as ws:
            await ws.send(f'<open xmlns="{_NS_FRAMING}" to="{xmpp_domain}" version="1.0"/>')
            opened = await _recv_stanza(ws, timeout)
            if _local(opened.tag) == "error":
                report["domain_recognized"] = False
                report["error"] = ET.tostring(opened, encoding="unicode")
                return
            report["domain_recognized"] = True

            features = await _recv_stanza(ws, timeout)
            mechanisms = [
                m.text
                for m in features.iter()
                if _local(m.tag) == "mechanism" and m.text
            ]
            report["sasl_mechanisms"] = mechanisms

            if "ANONYMOUS" not in mechanisms:
                report["anonymous_login_ok"] = False
                report["error"] = "Server does not offer the ANONYMOUS SASL mechanism."
                return

            await ws.send(f'<auth xmlns="{_NS_SASL}" mechanism="ANONYMOUS"/>')
            result = await _recv_stanza(ws, timeout)
            if _local(result.tag) == "success":
                report["anonymous_login_ok"] = True
            else:
                report["anonymous_login_ok"] = False
                report["error"] = ET.tostring(result, encoding="unicode")

    try:
        asyncio.run(probe())
    except Exception as exc:
        if report["error"] is None:
            report["error"] = str(exc)

    return report


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <jitsi-conference-url>")
        sys.exit(1)

    url = sys.argv[1]
    try:
        print(get_participant_count(url))
    except Exception as exc:
        print(f"Failed to get participant count: {exc}", file=sys.stderr)
        print("Running diagnostics...", file=sys.stderr)
        print(json.dumps(diagnose_jitsi_access(url), indent=2), file=sys.stderr)
        sys.exit(1)
