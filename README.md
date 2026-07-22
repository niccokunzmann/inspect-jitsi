# inspect-jitsi

Tools for inspecting a running [Jitsi Meet](https://jitsi.org/) deployment.

## Quick, one-shot functions

```python
from inspect_jitsi import get_participant_count, get_participants, diagnose_jitsi_access

get_participant_count("https://meet.example.com/SomeRoomName")   # -> 2
get_participants("https://meet.example.com/SomeRoomName")        # -> [Participant(...), ...]
diagnose_jitsi_access("https://meet.example.com/SomeRoomName")   # -> DiagnosisResult(...)
```

Or from the command line (requires the `cli` extra, see below):

```sh
inspect-jitsi count https://meet.example.com/SomeRoomName
inspect-jitsi participants https://meet.example.com/SomeRoomName
inspect-jitsi diagnose https://meet.example.com/SomeRoomName
```

Each call briefly opens its own connection, reads what's needed, and closes
again - see "How it works" below for why that's necessary and what it means
in practice.

If anonymous login is rejected (e.g. by servers like meet.jit.si that now
require a token), `diagnose_jitsi_access`/`inspect-jitsi diagnose` reports
what's going on (which SASL mechanisms are offered, whether anonymous login
succeeded, etc).

## Async API

For anything beyond a single one-shot call - e.g. holding a room open and
polling it repeatedly - use `JitsiConference` directly instead of the sync
wrappers above; it's fully `async`/`await`:

```python
import asyncio
from inspect_jitsi import JitsiConference

async def main():
    async with JitsiConference("https://meet.example.com/SomeRoomName") as conference:
        print(await conference.get_participants())

asyncio.run(main())
```

## Package layout

- `inspect_jitsi.xmpp.JitsiXmppConnection` - the low-level anonymous
  XMPP/MUC connection (stream negotiation, SASL, presence parsing).
- `inspect_jitsi.xmpp.JitsiConference` - the public async handle on a room,
  built on top of a `JitsiXmppConnection`. Has `open()`/`close()`,
  `get_participants()`, and `diagnose()`.
- `inspect_jitsi.xmpp.Participant` - one occupant of a room (jid, nick,
  display name, role, affiliation, ...), with `.to_dict()`/`.to_json()`.
- `inspect_jitsi.xmpp.DiagnosisResult` - the result of `diagnose()`, with
  `.to_dict()`.
- `inspect_jitsi.sync` - synchronous, one-shot convenience functions
  (`get_participant_count`, `get_participants`, `diagnose_jitsi_access`)
  built on top of `JitsiConference`.
- `inspect_jitsi.cli` - the `inspect-jitsi` command line tool (`typer`
  based; needs the `cli` extra).

## How it works

Jitsi's prosody deployment locks down `disco#info` on MUC rooms to
occupants only (confirmed live: a bare `disco#info` query gets
`<error type="auth"><forbidden/></error>`), so the usual XEP-0045 "peek
without joining" trick doesn't work here. Instead, `JitsiXmppConnection`
briefly joins the room as a real (if anonymous) occupant over an XMPP
connection carried by WebSocket (the same `wss://<domain>/xmpp-websocket`
endpoint the web client itself uses), reads the roster of `<presence>`
stanzas the MUC sends back, then leaves - meaning the room briefly gains
(and loses) one occupant, and other participants may see a transient
join/leave notification.

No Python XMPP library (`slixmpp`, `aioxmpp`, ...) supports the WebSocket
transport Jitsi requires - they're TCP-only, and Jitsi deployments generally
don't expose raw XMPP client-to-server (port 5222) publicly - so
`inspect_jitsi.xmpp.connection` hand-rolls the small slice of RFC 6120
(stream/SASL/bind) and RFC 7395 (XMPP over WebSocket framing) needed to join
a MUC room.

jicofo (the conference focus component) also joins every active Jitsi
conference's MUC as a pseudo-participant nicknamed `focus` - that occupant
is filtered out so participant counts/lists reflect only humans.

Deployments (e.g. docker-jitsi-meet) commonly use an *internal* XMPP domain
(typically `meet.jitsi`) and MUC component (typically `muc.meet.jitsi`) that
differ from the public hostname in the URL - the public web server proxies
the WebSocket through, but the XMPP stream's `to` attribute and the MUC room
JID must use the internal names. `discover_hosts` figures these out
automatically by reading the site's public `/config.js` (the same file the
browser client itself relies on), rather than guessing.

## Installing

```sh
pip install -e .          # Python API only
pip install -e ".[cli]"   # + the inspect-jitsi command line tool
pip install -e ".[test]"  # + test dependencies (pytest, pytest-asyncio, ...)
```

## Testing

```sh
pytest
```

None of the tests talk to a real Jitsi server - they drive
`JitsiXmppConnection`/`JitsiConference` against a scripted fake WebSocket
server (see `inspect_jitsi/test/conftest.py`), fed canned XMPP stanzas
recorded from real traffic against a docker-jitsi-meet deployment.
