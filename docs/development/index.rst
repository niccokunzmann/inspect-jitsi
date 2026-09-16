===========
Development
===========

This chapter describes how to set up a local development environment for inspect-jitsi and the ``make`` targets available while working on it.

Setup
-----

inspect-jitsi uses a plain Python virtual environment and a :file:`Makefile` to wrap the common commands.

.. code-block:: shell

    git clone https://github.com/niccokunzmann/inspect-jitsi
    cd inspect-jitsi
    make init

``make init`` creates a virtual environment in :file:`.venv/` and installs inspect-jitsi into it, editable, together with its ``test``, ``cli``, and ``docs`` extras.

Makefile targets
-----------------

.. list-table::
    :header-rows: 1

    *   -   Target
        -   Description
    *   -   ``make init``
        -   Create the virtual environment and install every extra needed for development.
    *   -   ``make dev``
        -   Alias for ``make init``.
    *   -   ``make test``
        -   Run the test suite with ``pytest``.
    *   -   ``make lint``
        -   Check for lint issues with ``ruff`` (same as CI).
    *   -   ``make format``
        -   Format the code base with ``ruff`` and fix auto-fixable lint issues.
    *   -   ``make dist``
        -   Build the sdist and wheel into :file:`dist/`.
    *   -   ``make clean``
        -   Clean the docs build directory.
    *   -   ``make clean-all``
        -   Clean the docs build directory and the virtual environment.
    *   -   ``make html``
        -   Build the documentation as HTML into :file:`docs/_build/html/`.
    *   -   ``make livehtml``
        -   Rebuild the documentation on changes, with live-reload in the browser.
    *   -   ``make linkcheck``
        -   Check the documentation for broken links.

Trying the CLI on your machine
---------------------------------

Activate the virtual environment ``make init`` created, and the ``inspect-jitsi`` command runs against this checkout:

.. code-block:: shell

    source .venv/bin/activate
    inspect-jitsi --help

Since it was installed editable (``pip install -e``), code changes you make take effect immediately, no reinstall needed.

Running the tests
------------------

.. code-block:: shell

    make test

Equivalent to ``.venv/bin/pytest``. The test suite drives :class:`~inspect_jitsi.xmpp.JitsiXmppConnection` (and the higher-level wrappers built on it) against a scripted fake XMPP/WebSocket server, rather than a real Jitsi deployment - see :mod:`inspect_jitsi.test.conftest`.

To check for lint issues without fixing them (e.g. what CI runs):

.. code-block:: shell

    make lint

Building the documentation
----------------------------

This documentation is built with `Sphinx <https://www.sphinx-doc.org/>`_. To build it once as static HTML:

.. code-block:: shell

    make html

The output is written to :file:`docs/_build/html/index.html`.

While editing the documentation, run a live-reloading local server instead - it rebuilds and refreshes your browser automatically as you save changes to any ``.rst`` file or docstring:

.. code-block:: shell

    make livehtml

This serves the documentation at http://127.0.0.1:8000 by default.

To check for broken links across the documentation:

.. code-block:: shell

    make linkcheck

The API reference under :doc:`../reference/index` is generated automatically from docstrings in the source code via ``sphinx.ext.apidoc``, and the CLI reference from the ``inspect-jitsi`` command's own ``--help`` output via ``typer utils docs`` - there's nothing to keep in sync by hand in either case; just document new modules, classes, functions, and CLI options as you write them.

Releasing
---------

Pushing a ``v*`` git tag builds the package and publishes it to `PyPI <https://pypi.org/project/inspect-jitsi/>`_ automatically - see :file:`.github/workflows/tests.yml`.

Create a version variable:

.. code-block:: shell

    export VERSION="v0.0.2"

Edit the :file:`CHANGES.md` at the repository root.
Then commit the changes and check that the `CI build <https://github.com/niccokunzmann/inspect-jitsi/actions?query=branch%3Amain>`_ is running.

.. code-block:: shell

    git add CHANGES.md
    git commit -m"$VERSION"
    git push

Once the `CI build`_ passes, create a tag and push it.

.. code-block:: shell

    git tag "$VERSION"
    git push origin "$VERSION"

Contributing
------------

Pull requests are welcome on `GitHub <https://github.com/niccokunzmann/inspect-jitsi>`_. Please make sure ``make test`` and ``make lint`` pass before opening one - the test suite is what CI runs.
