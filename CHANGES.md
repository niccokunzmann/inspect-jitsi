# Changelog

## 0.3.0

- Add shell completion (bash/zsh/fish/PowerShell), for every command and
  option, out of the box - `inspect-jitsi --install-completion` enables it.
  Requires the new `shellingham` dependency of the `cli` extra.
- Add `avatar_url` to `Participant`: an occupant's custom avatar (shown
  instead of their video when it's off), if their client disclosed one -
  returned by `count`/`participants`/`monitor` and the equivalent Python
  functions, same as every other field. If no custom avatar was disclosed
  but an `email` was (also now a field), `avatar_url` falls back to the
  Gravatar URL Jitsi's own clients compute from it, matching what is
  actually shown in a real Jitsi session.
- Add `--avatar PATH` / `INSPECT_JITSI_AVATAR` (and the matching `avatar_url=`
  parameter) to `count`, `participants` and `monitor`, and to
  `get_participant_count`/`get_participants`/`monitor_room`/
  `monitor_conference`: discloses a local image file as inspect-jitsi's own
  avatar when joining, sent as a `data:` URI since there is no server to host
  it on. `avatar_data_uri` turns a file into that URI on its own.
- The command line discloses the inspect-jitsi logo as its avatar by default;
  pass `--avatar PATH_OR_URL` to use another image or image URL or `--no-avatar` to disclose none.
  The Python API still discloses no avatar unless `avatar_url=` is given.
- Use the logo as the documentation logo and favicon.

## 0.2.0

- Add the `inspect-jitsi monitor` command: it stays connected to a room, prints
  a line of JSON whenever the room, its participants or its status change, and
  exits when the room is closed. It reconnects after a lost connection, see
  `--timeout` / `INSPECT_JITSI_TIMEOUT`. It checks that the room exists before
  joining it (`--create` skips that), and leaves when it is the only one in
  the room (`--stay` keeps it there).
- Add `monitor_room` (blocking iterator) and `monitor_conference` (async
  generator) to monitor a room from Python, as the command does.
- Fix: every XMPP stanza the library sends is now built with
  `xml.etree.ElementTree` instead of by pasting values into strings. A display
  name, nickname, room name or domain containing quotes, `<`, `&`, control
  characters or undecodable bytes can no longer produce malformed XML or
  change the structure of a stanza. Characters XML forbids are sent as U+FFFD.
  A reply that is not valid text is now a `JitsiConnectionError`.
- Fix: the background reader of `JitsiXmppConnection` no longer stops after
  `timeout` seconds of a quiet room.

## 0.1.0

- Fix: XMPP stanzas received from the server are now parsed with
  `defusedxml` instead of the standard library's `xml.etree.ElementTree`
  directly - a conference URL is arbitrary, caller-supplied input, so a
  malicious server could otherwise send a billion-laughs/XXE-style XML bomb
  that got silently expanded instead of rejected.
- Add a new parameter (`name=` on `get_participant_count`/`get_participants`/
  `JitsiConference`/`JitsiXmppConnection`) to set the display name disclosed
  when joining a room.
- The `inspect-jitsi` command joins a conference with the name  "inspect-jitsi" by default.
  Override it with `--name` or the `INSPECT_JITSI_NAME` environment
  variable.

## 0.0.2

- Fix: tolerate `<stream:features>`/`<stream:error>` sent without an
  `xmlns:stream` declaration over the WebSocket framing (some deployments
  omit it, relying on the enclosing `<stream:stream>` that RFC 7395 framing
  doesn't send) - this used to crash callers with a raw
  `xml.etree.ElementTree.ParseError: unbound prefix`.
- Add `JitsiConnectionError`, raised (instead of assorted raw
  `websockets`/stdlib exceptions) whenever the XMPP connection to a Jitsi
  deployment fails or is lost - catch it (or the `ConnectionError` it
  subclasses) instead of guessing at every exception a live session might
  raise.

## 0.0.1

- Initial release
- Add count, created, participants and diagnostics
