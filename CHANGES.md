# Changelog

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
