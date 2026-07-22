# inspect-jitsi

Tools for inspecting a running [Jitsi Meet](https://jitsi.org/) deployment.

## Participant count

```python
from inspect_jitsi import get_participant_count

get_participant_count("https://meet.example.com/SomeRoomName")
```

Or from the command line:

```sh
inspect-jitsi https://meet.example.com/SomeRoomName
```

This briefly joins the room's MUC as an anonymous occupant to read the
participant roster, then leaves - see `inspect_jitsi/room_count.py` for why
that's necessary (Jitsi's prosody config forbids reading room occupancy
without joining) and what it means in practice (a brief join/leave blip
other participants may notice).

If anonymous login is rejected (e.g. by servers like meet.jit.si that now
require a token), `diagnose_jitsi_access` reports what's going on:

```python
from inspect_jitsi import diagnose_jitsi_access

diagnose_jitsi_access("https://meet.example.com/SomeRoomName")
```

## Installing

```sh
pip install -e .
```
