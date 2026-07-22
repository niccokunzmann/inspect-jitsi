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
"""Command line entry point: ``inspect-jitsi <conference-url>``."""

from __future__ import annotations

import json
import sys

from inspect_jitsi.room_count import diagnose_jitsi_access, get_participant_count


def main(argv: list[str] | None = None) -> int:
    """Print the participant count for a Jitsi conference URL."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: inspect-jitsi <jitsi-conference-url>", file=sys.stderr)
        return 1

    url = args[0]
    try:
        print(get_participant_count(url))
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to get participant count: {exc}", file=sys.stderr)
        print("Running diagnostics...", file=sys.stderr)
        print(json.dumps(diagnose_jitsi_access(url), indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
