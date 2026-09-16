============
How it works
============

inspect-jitsi works by joining the room as a participant and inspecting who is there.

Jitsi's prosody deployment locks down ``disco#info`` on MUC rooms to
occupants only (confirmed live: a bare ``disco#info`` query gets
``<error type="auth"><forbidden/></error>``), so the usual XEP-0045 "peek
without joining" trick doesn't work here. Instead, ``JitsiXmppConnection``
briefly joins the room as a real (if anonymous) occupant over an XMPP
connection carried by WebSocket (the same ``wss://<domain>/xmpp-websocket``
endpoint the web client itself uses), reads the roster of ``<presence>``
stanzas the MUC sends back, then leaves - meaning the room briefly gains
(and loses) one occupant, and other participants may see a transient
join/leave notification.

No Python XMPP library (``slixmpp``, ``aioxmpp``, ...) supports the WebSocket
transport Jitsi requires - they're TCP-only, and Jitsi deployments generally
don't expose raw XMPP client-to-server (port 5222) publicly - so
:mod:`inspect_jitsi.xmpp.connection` hand-rolls the small slice of RFC 6120
(stream/SASL/bind) and RFC 7395 (XMPP over WebSocket framing) needed to join
a MUC room.

jicofo (the conference focus component) also joins every active Jitsi
conference's MUC as a pseudo-participant nicknamed ``focus`` - that occupant
is filtered out so participant counts/lists reflect only humans.

Deployments (e.g. docker-jitsi-meet) commonly use an *internal* XMPP domain
(typically ``meet.jitsi``) and MUC component (typically ``muc.meet.jitsi``) that
differ from the public hostname in the URL - the public web server proxies
the WebSocket through, but the XMPP stream's ``to`` attribute and the MUC room
JID must use the internal names. :func:`~inspect_jitsi.xmpp.discover_hosts`
figures these out automatically by reading the site's public ``/config.js``
(the same file the browser client itself relies on), rather than guessing.
