# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Command line interface.

``inspect-jitsi count|participants|diagnose|created <conference-url>``.
Requires the "cli" extra: ``pip install inspect-jitsi[cli]``.

``count``/``participants`` join the room under a display name, set via
``--name``, the ``INSPECT_JITSI_NAME`` environment variable, or defaulting
to "inspect-jitsi".
"""

from __future__ import annotations

import json

try:
    import typer
except ModuleNotFoundError as exc:
    msg = (
        "The inspect-jitsi CLI requires the 'cli' extra: pip install inspect-jitsi[cli]"
    )
    raise ModuleNotFoundError(msg) from exc

from inspect_jitsi.sync import (
    diagnose_jitsi_access,
    get_participant_count,
    get_participants,
    is_room_created,
)
from inspect_jitsi.xmpp.connection import DEFAULT_NAME

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help=(
        "Tools for inspecting a running Jitsi Meet deployment.\n\n"
        "Documentation: https://inspect-jitsi.readthedocs.io/en/latest/\n\n"
        "Source code: https://github.com/niccokunzmann/inspect-jitsi"
    ),
)

NameOption = typer.Option(
    DEFAULT_NAME,
    "--name",
    envvar="INSPECT_JITSI_NAME",
    help="Display name to disclose when joining the room.",
)


def _fail(action: str, conference_url: str, exc: Exception) -> None:
    typer.echo(f"Failed to {action}: {exc}", err=True)
    typer.echo("Running diagnostics...", err=True)
    typer.echo(
        json.dumps(diagnose_jitsi_access(conference_url).to_dict(), indent=2), err=True
    )
    raise typer.Exit(1) from exc


@app.command()
def count(conference_url: str, name: str = NameOption) -> None:
    """Print the number of participants currently in a Jitsi Meet room."""
    try:
        typer.echo(get_participant_count(conference_url, name=name))
    except Exception as exc:  # noqa: BLE001
        _fail("get participant count", conference_url, exc)


@app.command()
def participants(conference_url: str, name: str = NameOption) -> None:
    """Print the participants currently in a Jitsi Meet room, as indented JSON."""
    try:
        people = get_participants(conference_url, name=name)
    except Exception as exc:  # noqa: BLE001
        _fail("get participants", conference_url, exc)
        return
    typer.echo(json.dumps([p.to_dict() for p in people], indent=2))


@app.command()
def diagnose(conference_url: str) -> None:
    """Print connectivity/auth diagnostics for a Jitsi deployment."""
    typer.echo(json.dumps(diagnose_jitsi_access(conference_url).to_dict(), indent=2))


@app.command()
def created(
    conference_url: str,
    json_output: bool = typer.Option(
        False, "--json", help="Print true/false as JSON, in addition to the exit code."
    ),
) -> None:
    """Exit 0 if the room exists, 1 if not. Prints nothing unless --json is given."""
    try:
        exists = is_room_created(conference_url)
    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"error": str(exc)}), err=True)
        else:
            typer.echo(f"Failed to check whether the room exists: {exc}", err=True)
        raise typer.Exit(2) from exc
    if json_output:
        typer.echo(json.dumps(exists))
    raise typer.Exit(0 if exists else 1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
