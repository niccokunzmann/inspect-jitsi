# inspect-jitsi

Tools for inspecting a running [Jitsi Meet](https://jitsi.org/) deployment.

- [Changelog](CHANGED.md)
- [PyPI](https://pypi.org/project/inspect-jitsi/)
- [Source](https://github.com/niccokunzmann/inspect-jitsi)

## Installation

Install the `inspect-jitsi` command with [pipx](https://pipx.pypa.io/latest/index.html):

```sh
pipx install inspect-jitsi[cli]
```

Install as a Python module only:

```sh
pip install inspect-jitsi
```


## Command Line API

The command line requires installing `inspect-jitsi[cli]`.

First, join or leave the room at [meet.hosted.quelltext.eu/inspect-jitsi](https://meet.hosted.quelltext.eu/inspect-jitsi).
Then run the commands:


```sh
inspect-jitsi count https://meet.hosted.quelltext.eu/inspect-jitsi
inspect-jitsi participants https://meet.hosted.quelltext.eu/inspect-jitsi
inspect-jitsi diagnose https://meet.hosted.quelltext.eu/inspect-jitsi
inspect-jitsi created https://meet.hosted.quelltext.eu/inspect-jitsi
```

| Command | Prints | Exit code |
| --- | --- | --- |
| `count <url>` | number of participants | 0, or 1 on failure |
| `participants <url>` | participants as indented JSON | 0, or 1 on failure |
| `diagnose <url>` | connectivity/auth report as indented JSON | 0, or 1 on failure |
| `created <url>` | nothing (use `--json` to print `true`/`false`) | 0 if the room exists, 1 if not, 2 on failure |

`count`/`participants` fall back to running `diagnose` and printing its report
to stderr if they fail, to help explain why (e.g. a token being required).

## Python API (Sync)

```python
from inspect_jitsi import (
    get_participant_count,
    get_participants,
    diagnose_jitsi_access,
    is_room_created,
)

get_participant_count("https://meet.example.com/SomeRoomName")   # -> 2
get_participants("https://meet.example.com/SomeRoomName")        # -> [Participant(...), ...]
diagnose_jitsi_access("https://meet.example.com/SomeRoomName")   # -> DiagnosisResult(...)
is_room_created("https://meet.example.com/SomeRoomName")         # -> True
```

| Function | Returns |
| --- | --- |
| `get_participant_count(url, nick=None, ...)` | `int` |
| `get_participants(url, nick=None, ...)` | `list[Participant]` |
| `diagnose_jitsi_access(url, ...)` | `DiagnosisResult` |
| `is_room_created(url, ...)` | `bool` |

`Participant` and `DiagnosisResult` are dataclasses with `.to_dict()` (and
`Participant` also has `.to_json()`) for easy serialization. `Participant`
carries `jid`, `nick`, `name` (display name, if disclosed), `role`,
`affiliation`, `real_jid`, and `occupant_id`.

## Python API (Async)

For anything beyond a single one-shot call - e.g. holding a room open and
polling it repeatedly - use `JitsiConference` directly instead of the sync
wrappers above; it's fully `async`/`await`:

```python
import asyncio
from inspect_jitsi import JitsiConference

async def main():
    async with JitsiConference("https://meet.example.com/SomeRoomName") as conference:
        print(await conference.is_created())      # -> True, without joining
        print(await conference.get_participants())

asyncio.run(main())
```

## How it works

<details>
<summary>
We try joining the room as a participant and inspect who is there.
</summary>

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

</details>

## Installing

```sh
pip install -e .          # Python API only
pip install -e ".[cli]"   # + the inspect-jitsi command line tool
pip install -e ".[test]"  # + test dependencies
```

## Testing

```sh
pytest
```

## Release

1. Edit the changelog
2. Create a tag and push it.

```sh
git tag v0.0.1
git push origin v0.0.1
```