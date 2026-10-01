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

``inspect-jitsi count|participants|diagnose|created|monitor <conference-url>``.
Requires the "cli" extra: ``pip install inspect-jitsi[cli]``.

``count``/``participants`` join the room under a display name, set via
``--name``, the ``INSPECT_JITSI_NAME`` environment variable, or defaulting
to "inspect-jitsi".
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys

try:
    import typer
except ModuleNotFoundError as exc:
    msg = (
        "The inspect-jitsi CLI requires the 'cli' extra: pip install inspect-jitsi[cli]"
    )
    raise ModuleNotFoundError(msg) from exc

from pathlib import Path

from inspect_jitsi.sync import (
    diagnose_jitsi_access,
    get_participant_count,
    get_participants,
    is_room_created,
)
from inspect_jitsi.xmpp.avatar import avatar_data_uri
from inspect_jitsi.xmpp.connection import DEFAULT_NAME, parse_conference_url
from inspect_jitsi.xmpp.monitor import monitor_conference

app = typer.Typer(
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

AvatarOption = typer.Option(
    None,
    "--avatar",
    envvar="INSPECT_JITSI_AVATAR",
    help=(
        "Local image file (png/jpeg/gif/webp/bmp/svg) or http(s):// URL of an "
        "image to disclose as the avatar when joining the room, shown instead "
        "of video (default: the inspect-jitsi logo). A file is sent as a "
        "data: URI, so it is re-sent on every join/reconnect - keep it small."
    ),
)


NoAvatarOption = typer.Option(
    False,
    "--no-avatar",
    help="Disclose no avatar at all, instead of the default inspect-jitsi logo.",
)

DEFAULT_AVATAR = Path(__file__).parent / "logo" / "logo.svg"


def _avatar_url(avatar: str | None, no_avatar: bool) -> str | None:
    if no_avatar:
        if avatar is not None:
            typer.echo("Use either --avatar or --no-avatar, not both.", err=True)
            raise typer.Exit(2)
        return None
    if avatar is None:
        avatar = str(DEFAULT_AVATAR)
    if avatar.lower().startswith(("http://", "https://")):
        return avatar
    try:
        return avatar_data_uri(avatar)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"Invalid --avatar: {exc}", err=True)
        raise typer.Exit(2) from exc


MONITOR_DOCS = (
    "https://inspect-jitsi.readthedocs.io/en/latest/how-to/monitor-a-conference.html"
)


def _fail(action: str, conference_url: str, exc: Exception) -> None:
    typer.echo(f"Failed to {action}: {exc}", err=True)
    typer.echo("Running diagnostics...", err=True)
    typer.echo(
        json.dumps(diagnose_jitsi_access(conference_url).to_dict(), indent=2), err=True
    )
    raise typer.Exit(1) from exc


@app.command()
def count(
    conference_url: str,
    name: str = NameOption,
    avatar: str | None = AvatarOption,
    no_avatar: bool = NoAvatarOption,
) -> None:
    """Print the number of participants currently in a Jitsi Meet room."""
    avatar_url = _avatar_url(avatar, no_avatar)
    try:
        typer.echo(
            get_participant_count(conference_url, name=name, avatar_url=avatar_url)
        )
    except Exception as exc:  # noqa: BLE001
        _fail("get participant count", conference_url, exc)


@app.command()
def participants(
    conference_url: str,
    name: str = NameOption,
    avatar: str | None = AvatarOption,
    no_avatar: bool = NoAvatarOption,
) -> None:
    """Print the participants currently in a Jitsi Meet room, as indented JSON."""
    avatar_url = _avatar_url(avatar, no_avatar)
    try:
        people = get_participants(conference_url, name=name, avatar_url=avatar_url)
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


async def _monitor(
    conference_url: str,
    name: str,
    avatar_url: str | None,
    timeout: float,
    *,
    create: bool,
    stay: bool,
) -> None:
    async for state in monitor_conference(
        conference_url,
        name=name,
        avatar_url=avatar_url,
        timeout=timeout,
        create=create,
        stay=stay,
    ):
        typer.echo(json.dumps(state))


@app.command(
    help=(
        "Follow a room until it is closed, printing a JSON line on every change."
        f"\n\nDocumentation: {MONITOR_DOCS}"
    )
)
def monitor(
    conference_url: str,
    name: str = NameOption,
    avatar: str | None = AvatarOption,
    no_avatar: bool = NoAvatarOption,
    create: bool = typer.Option(
        False,
        "--create",
        help=(
            "Join the room even if it does not exist, which creates it if the "
            "server allows that. By default a missing room is reported as "
            "closed without joining it."
        ),
    ),
    stay: bool = typer.Option(
        False,
        "--stay",
        help=(
            "Stay in the room and keep it open when nobody else is in it. "
            "By default the monitor leaves and reports the room as closed."
        ),
    ),
    timeout: float = typer.Option(
        60,
        "--timeout",
        envvar="INSPECT_JITSI_TIMEOUT",
        min=0,
        help=(
            "Seconds to keep trying to reconnect after the connection is lost. "
            "0 disables reconnecting."
        ),
    ),
) -> None:
    try:
        parse_conference_url(conference_url)
    except ValueError as exc:
        typer.echo(f"Invalid conference URL: {exc}", err=True)
        raise typer.Exit(2) from exc
    avatar_url = _avatar_url(avatar, no_avatar)
    try:
        asyncio.run(
            _monitor(
                conference_url, name, avatar_url, timeout, create=create, stay=stay
            )
        )
    except KeyboardInterrupt:
        raise typer.Exit(130) from None
    except BrokenPipeError:
        # The reader of our output went away. Point stdout at /dev/null so
        # Python's own flush at exit doesn't print another error.
        with contextlib.suppress(OSError, ValueError):
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        raise typer.Exit(130) from None
    except Exception as exc:  # noqa: BLE001
        _fail("monitor the room", conference_url, exc)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
