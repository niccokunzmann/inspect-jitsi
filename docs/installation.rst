============
Installation
============

Requires Python 3.11 or newer.

.. tab-set::

    .. tab-item:: pipx (command line tool)

        Install inspect-jitsi as a command line tool using `pipx <https://pipx.pypa.io/>`_.

        .. code-block:: shell

            pipx install "inspect-jitsi[cli]"

    .. tab-item:: pip (library only)

        Install using ``pip`` to use the :doc:`Python API <reference/index>`, not the ``inspect-jitsi`` command:

        .. code-block:: shell

            pip install inspect-jitsi

The ``inspect-jitsi`` command itself requires the ``cli`` extra.

Confirm it is on your ``PATH``:

.. code-block:: shell

    inspect-jitsi --help

See :doc:`how-to/index` for what to do with it next.
