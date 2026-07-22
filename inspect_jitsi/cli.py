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
"""Command line interface: ``inspect-jitsi count|diagnose <conference-url>``.

Requires the "cli" extra: ``pip install inspect-jitsi[cli]``.
"""

from __future__ import annotations

import json

try:
    import typer
except ModuleNotFoundError as exc:
    msg = "The inspect-jitsi CLI requires the 'cli' extra: pip install inspect-jitsi[cli]"
    raise ModuleNotFoundError(msg) from exc

from inspect_jitsi.room_count import diagnose_jitsi_access, get_participant_count

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Tools for inspecting a running Jitsi Meet deployment.",
)


@app.command()
def count(conference_url: str) -> None:
    """Print the number of participants currently in a Jitsi Meet room."""
    try:
        typer.echo(get_participant_count(conference_url))
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Failed to get participant count: {exc}", err=True)
        typer.echo("Running diagnostics...", err=True)
        typer.echo(json.dumps(diagnose_jitsi_access(conference_url), indent=2), err=True)
        raise typer.Exit(1) from exc


@app.command()
def diagnose(conference_url: str) -> None:
    """Print connectivity/auth diagnostics for a Jitsi deployment."""
    typer.echo(json.dumps(diagnose_jitsi_access(conference_url), indent=2))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
