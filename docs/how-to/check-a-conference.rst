==============================================
Check a Jitsi conference from the command line
==============================================

This walks through inspecting a running Jitsi Meet conference with the ``inspect-jitsi`` command, from installation to reading its output. It uses ``https://meet.hosted.quelltext.eu/inspect-jitsi`` as the example room throughout - substitute your own conference's URL everywhere it appears.

1. Install the command
-------------------------

.. code-block:: shell

    pipx install "inspect-jitsi[cli]"

See :doc:`../installation` for other installation methods.

2. Count the participants
----------------------------

.. code-block:: shell

    inspect-jitsi count https://meet.hosted.quelltext.eu/inspect-jitsi

Prints a single number - how many people are already in the room, not counting this check itself:

.. code-block:: text

    2

An empty (or nonexistent) room prints ``0`` rather than failing.

3. List who is in it
------------------------

.. code-block:: shell

    inspect-jitsi participants https://meet.hosted.quelltext.eu/inspect-jitsi

Prints the same roster as indented JSON, one entry per participant:

.. code-block:: json

    [
      {
        "jid": "inspect-jitsi@muc.meet.jitsi/alice",
        "nick": "alice",
        "name": "Alice",
        "role": "participant",
        "affiliation": "none",
        "real_jid": null,
        "occupant_id": "a1b2c3d4"
      }
    ]

``name`` is only present if that participant's own client disclosed a display name (XEP-0172) - it is ``null`` otherwise, even though ``nick`` (the technical MUC nickname) is always known. See :doc:`../reference/index` for what each field means.

4. Check whether the room exists, without joining
------------------------------------------------------

``count``/``participants`` briefly join the room to read its roster (see :doc:`../reference/index` for why), which other participants may notice as a transient join/leave. To check only whether a room currently exists, without joining it at all:

.. code-block:: shell

    inspect-jitsi created https://meet.hosted.quelltext.eu/inspect-jitsi

This prints nothing - it only sets its exit code (``0`` if the room exists, ``1`` if not, ``2`` on failure). Add ``--json`` to also print ``true``/``false``/an error object:

.. code-block:: shell

    inspect-jitsi created --json https://meet.hosted.quelltext.eu/inspect-jitsi

.. code-block:: text

    true

5. Diagnose a failure
-------------------------

If ``count`` or ``participants`` can't reach the room at all - a token being required, an unreachable deployment, disallowed anonymous login - they print an error and automatically fall back to running diagnostics, so you do not need to run this by hand:

.. code-block:: text

    Failed to get participant count: ...
    Running diagnostics...
    {
      "ws_domain": "meet.hosted.quelltext.eu",
      "config_js_reachable": true,
      "discovered_hosts": {"domain": "meet.jitsi", "muc": "muc.meet.jitsi", "anonymousdomain": null},
      "xmpp_domain_tried": "meet.jitsi",
      "domain_recognized": true,
      "sasl_mechanisms": ["ANONYMOUS"],
      "anonymous_login_ok": true,
      "error": null
    }

To run the same report on its own at any time:

.. code-block:: shell

    inspect-jitsi diagnose https://meet.hosted.quelltext.eu/inspect-jitsi

``anonymous_login_ok: false`` most often means the deployment requires a JWT/token to join, which ``inspect-jitsi`` cannot supply.

6. Choose the name inspect-jitsi joins under
------------------------------------------------

``count``/``participants`` disclose a display name to other participants while briefly joined - by default, ``"inspect-jitsi"``, so it is recognizable in the room's participant list rather than showing up as Jitsi's generic "Fellow Jitsier". Override it with ``--name``, or the ``INSPECT_JITSI_NAME`` environment variable for every invocation in a shell session or script:

.. code-block:: shell

    inspect-jitsi count --name "Room Monitor" https://meet.hosted.quelltext.eu/inspect-jitsi
    INSPECT_JITSI_NAME="Room Monitor" inspect-jitsi count https://meet.hosted.quelltext.eu/inspect-jitsi

See :doc:`../reference/cli` for every option, including ``--json`` and the ones this guide didn't cover.
