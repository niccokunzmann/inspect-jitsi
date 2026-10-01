=================================================
Monitor a Jitsi conference from the command line
=================================================

``inspect-jitsi monitor`` stays connected to a conference and prints a line of JSON whenever something changes. It exits when the room is closed. See :doc:`../installation` if you haven't installed it yet.

.. code-block:: shell

    inspect-jitsi monitor https://meet.hosted.quelltext.eu/inspect-jitsi

Output
------

The first line is printed as soon as the command has joined the room. Every further line is printed when the information changes. All lines have the same schema, one JSON document per line - spread over several lines and indented below only for readability here; see further down this page for what each field means and what is actually printed:

.. code-block:: json

    {
      "room": {
        "name": "inspect-jitsi",
        "url": "https://meet.hosted.quelltext.eu/inspect-jitsi",
        "domain": "meet.hosted.quelltext.eu",
        "muc_domain": "muc.meet.jitsi",
        "jid": "inspect-jitsi@muc.meet.jitsi"
      },
      "participants": [
        {
          "jid": "inspect-jitsi@muc.meet.jitsi/alice",
          "nick": "alice",
          "name": "Alice",
          "role": "participant",
          "affiliation": "none",
          "real_jid": null,
          "occupant_id": null,
          "email": null,
          "avatar_url": null
        }
      ],
      "status": {
        "open": true,
        "attempts": 0
      }
    }

``room``
    Where the room is. Does not change while monitoring.

``participants``
    Everyone in the room, as a list in the order they joined. A participant who changes keeps their place, one who leaves is removed, and one who joins is added at the end. Several participants can have the same ``name``. The fields are described in :doc:`../reference/participant-fields`. The monitor itself is not listed.

``status.open``
    ``true`` while the room is open. When the room is closed, the last line is printed with ``false`` and the command exits with code 0.

``status.attempts``
    How many times the command had to reconnect. It starts at 0.

When the room is closed
-----------------------

The monitor checks that the room exists before it joins. A room that does not exist is not joined, because joining could create it: one line with ``status.open`` set to ``false`` is printed and the command exits. The same check is made before every reconnect.

Once it is in the room, the room counts as closed when

- the server removes the monitor from the room (the room was destroyed),
- the conference focus (jicofo) leaves the room, or
- the monitor is the only one left in the room. It then leaves the room again, so it does not keep the room alive.

The last line is printed with ``status.open`` set to ``false`` and the command exits with code 0. A participant who briefly disconnects and reconnects while being the last one in the room can make the room look closed for that moment.

``--stay``
    Do not treat being alone in the room as closed. The monitor stays in the room, and so keeps it open, until the room is closed by the server or the focus leaves.

``--create``
    Skip the check and join the room even if it does not exist. A server that lets anyone create rooms creates it then; a server that restricts room creation reports it as closed. Since the monitor is alone in a room it just created, use it together with ``--stay`` to wait there for participants, otherwise the monitor leaves again at once.

.. code-block:: shell

    inspect-jitsi monitor --create --stay https://meet.example.com/room

Reconnecting
------------

If the connection is lost, the command reconnects, waiting a little longer between attempts. Every attempt prints the previous state again with ``status.attempts`` increased by one and nothing else changed. If the participants are different after the connection is back, one more line is printed.

``--timeout SECONDS``
    How long to keep trying to reconnect before giving up. The default is 60. ``0`` disables reconnecting. It can also be set with the ``INSPECT_JITSI_TIMEOUT`` environment variable.

.. code-block:: shell

    INSPECT_JITSI_TIMEOUT=600 inspect-jitsi monitor https://meet.example.com/room

``--name NAME``
    The display name disclosed when joining, the same as for the other commands. It can also be set with ``INSPECT_JITSI_NAME``.

``--no-avatar``
    Disclose no avatar instead of the default inspect-jitsi logo.
``--avatar PATH``
    A local image file (png, jpeg, gif, webp, bmp or svg) or an ``http(s)`` URL of an image to disclose as the monitor's own avatar, the same as for the other commands - see :doc:`check-a-conference`. It can also be set with ``INSPECT_JITSI_AVATAR``. Since the monitor can stay connected for a long time, this is sent once, when it joins, and again on every reconnect.

Exit codes
----------

.. list-table::
    :header-rows: 1
    :widths: 10 90

    * - Code
      - Meaning
    * - ``0``
      - The room was closed.
    * - ``1``
      - The first connection failed, or the connection was lost and could not be restored within ``--timeout``. The error and connection diagnostics are printed to standard error.
    * - ``2``
      - The conference URL is invalid, or an option is invalid.
    * - ``130``
      - The command was interrupted (Ctrl+C) or standard output was closed.

Since the monitor joins the room to observe it, other participants may notice it, see :doc:`../reference/how-it-works`.

Processing the output
---------------------

Each line is a complete JSON document, so tools like ``jq`` can follow it:

.. code-block:: shell

    inspect-jitsi monitor https://meet.example.com/room | jq -c '.participants | length'

Standard output only ever receives these JSON lines, each document on exactly one line (newlines inside values are escaped), so it can be read with ``readline()`` or ``input()``. Errors and diagnostics go to standard error.

Using Python
------------

The command is built on a Python API that yields the same dictionaries the command prints as JSON.

.. code-block:: python

    from inspect_jitsi import monitor_room

    for state in monitor_room("https://meet.example.com/room", timeout=120):
        print(state["status"]["open"], len(state["participants"]))

The loop ends when the room is closed. In asynchronous code, use ``async for state in monitor_conference(url)`` instead. Both accept the same options as the command (``name``, ``avatar_url``, ``timeout``, ``create``, ``stay``) and raise :class:`~inspect_jitsi.xmpp.JitsiConnectionError` when the connection cannot be established or restored. See :func:`~inspect_jitsi.sync.monitor.monitor_room` and :func:`~inspect_jitsi.xmpp.monitor.monitor_conference`.
