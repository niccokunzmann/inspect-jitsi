==================
Participant fields
==================

Each entry ``inspect-jitsi participants``/:func:`~inspect_jitsi.get_participants` returns is a :class:`~inspect_jitsi.xmpp.Participant`, one occupant of a room parsed from their MUC presence stanza.

.. list-table::
    :header-rows: 1

    *   -   Field
        -   Meaning
    *   -   ``jid``
        -   The MUC occupant JID, e.g. ``room@muc.example.com/<nick-resource>``.
    *   -   ``nick``
        -   The MUC nickname - the resourcepart of ``jid``.
    *   -   ``name``
        -   Human display name, if the client sent one (XEP-0172 ``<nick/>``) - ``null`` otherwise, even though ``nick`` is always known. See :doc:`../how-to/check-a-conference` for choosing the name inspect-jitsi itself discloses.
    *   -   ``role``
        -   MUC role, e.g. ``"moderator"``, ``"participant"``.
    *   -   ``affiliation``
        -   MUC affiliation, e.g. ``"owner"``, ``"member"``, ``"none"``.
    *   -   ``real_jid``
        -   The occupant's real (non-anonymous, but still internal) JID, if disclosed.
    *   -   ``occupant_id``
        -   Stable per-session anonymous id (XEP occupant-id), if disclosed. Unlike ``jid``/``nick``, this stays the same for one occupant across the conference even where the MUC nick is a random per-join identifier - useful for telling "still the same person" from "someone new".

Every field but ``jid`` and ``nick`` is ``null`` when the occupant's client didn't disclose it - a deployment or client is free to omit any of them. See :class:`~inspect_jitsi.xmpp.Participant` for the authoritative, always up to date reference.
