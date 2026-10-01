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
"""Turning a local image file into a `data:` URI, for disclosure as an avatar.

XMPP presence has no notion of a local file - the only thing a client can
disclose is a URL (see `inspect_jitsi.xmpp.stanza.join_presence`), which
every other occupant's Jitsi client loads as an ``<img src="...">``. A
``data:`` URI embeds the image directly in that URL, so no web server is
needed to host it - at the cost of that image being broadcast, in full, to
every occupant on every join (and resent on every reconnect), rather than
fetched once.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

__all__ = ["MAX_AVATAR_FILE_SIZE", "avatar_data_uri"]

MAX_AVATAR_FILE_SIZE = 64 * 1024
"""Conservative cap on the source file's size.

Presence carrying it is broadcast to every occupant already in the room
when this one joins, and to the whole room again on every subsequent change
(including a reconnect) - unlike an ordinary avatar URL, which a browser
fetches once and caches, this one travels over XMPP in full each time. XMPP
servers also commonly cap stanza size well below this already.
"""

# Sniffed as a fallback when the file extension doesn't say (or lies) -
# magic bytes for the image types a Jitsi/browser client can actually
# render as an <img>.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"RIFF", "image/webp"),  # only if also "WEBP" at offset 8 - checked below
)


def _sniff_mime_type(data: bytes) -> str | None:
    for signature, sniffed in _SIGNATURES:
        if data.startswith(signature):
            if sniffed == "image/webp" and data[8:12] != b"WEBP":
                continue
            return sniffed
    stripped = data.lstrip(b"\x00\t\n\r ").removeprefix(b"\xef\xbb\xbf")
    if stripped.startswith((b"<?xml", b"<svg")):
        return "image/svg+xml"
    return None


def _guess_mime_type(path: Path, data: bytes) -> str | None:
    # Content first - so a mislabeled extension (`cat.jpg` that is actually a
    # PNG) doesn't get sent as the wrong type - and only once there is some
    # content to sniff at all, so an empty file isn't waved through by its
    # extension alone. The extension is still a fallback for a file this
    # sniffs doesn't recognize; none of this decodes the image, so a
    # genuinely corrupt (but non-empty, correctly-named) file can still get
    # through - the recipient's renderer would just fail to show it.
    sniffed = _sniff_mime_type(data)
    if sniffed is not None:
        return sniffed
    if not data:
        return None
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and guessed.startswith("image/"):
        return guessed
    return None


def avatar_data_uri(path: str | Path) -> str:
    """Read the image at `path` and return it as a `data:` URI.

    Args:
        path: an existing, readable image file - png, jpeg, gif, webp, bmp
            or svg (guessed from the extension and, failing that, from its
            content).

    Returns:
        A ``data:<mime-type>;base64,...`` URI, suitable as `avatar_url` on
        `inspect_jitsi.xmpp.JitsiXmppConnection`, `JitsiConference` or the
        `avatar_url=` parameter elsewhere in this package.

    Raises:
        FileNotFoundError: `path` does not exist, or is not a file.
        ValueError: the file is larger than `MAX_AVATAR_FILE_SIZE`, or does
            not look like a supported image.
    """
    file = Path(path)
    if not file.is_file():
        msg = f"No such image file: {file!r}"
        raise FileNotFoundError(msg)

    size = file.stat().st_size
    if size > MAX_AVATAR_FILE_SIZE:
        msg = (
            f"{file!r} is {size:,} bytes, over the {MAX_AVATAR_FILE_SIZE:,}-byte "
            "limit for an avatar image (it is broadcast to the whole room on "
            "every join/change, not just fetched once) - shrink the image."
        )
        raise ValueError(msg)

    data = file.read_bytes()
    mime_type = _guess_mime_type(file, data)
    if mime_type is None:
        msg = (
            f"{file!r} does not look like a supported image "
            "(png, jpeg, gif, webp, bmp or svg)."
        )
        raise ValueError(msg)

    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
