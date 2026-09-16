# Changelog

## Unreleased

- Fix: XMPP stanzas received from the server are now parsed with
  `defusedxml` instead of the standard library's `xml.etree.ElementTree`
  directly - a conference URL is arbitrary, caller-supplied input, so a
  malicious server could otherwise send a billion-laughs/XXE-style XML bomb
  that got silently expanded instead of rejected.
- Add a `name` option (CLI `--name`, `INSPECT_JITSI_NAME` environment
  variable, and `name=` on `get_participant_count`/`get_participants`/
  `JitsiConference`/`JitsiXmppConnection`) to set the display name disclosed
  when joining a room - defaults to `"inspect-jitsi"` instead of Jitsi's own
  "Fellow Jitsier" fallback for occupants with no display name.

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
