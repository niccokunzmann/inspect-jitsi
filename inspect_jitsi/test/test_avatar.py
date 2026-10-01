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
"""Tests for `avatar_data_uri`."""

from __future__ import annotations

import base64

import pytest

from inspect_jitsi.xmpp.avatar import MAX_AVATAR_FILE_SIZE, avatar_data_uri

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000"
    "00907753de0000000c4944415408d76360606060000000050001a5f645400000000049454e44ae426082"
)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 20
GIF_BYTES = b"GIF89a" + b"\x00" * 20
WEBP_BYTES = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 10
BMP_BYTES = b"BM" + b"\x00" * 20
SVG_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
XML_SVG_BYTES = b"<?xml version='1.0'?><svg></svg>"


def test_returns_a_data_uri_with_the_right_mime_type(tmp_path) -> None:
    path = tmp_path / "pic.png"
    path.write_bytes(PNG_BYTES)

    uri = avatar_data_uri(path)

    assert uri == f"data:image/png;base64,{base64.b64encode(PNG_BYTES).decode()}"


def test_accepts_a_string_path_too(tmp_path) -> None:
    path = tmp_path / "pic.png"
    path.write_bytes(PNG_BYTES)

    assert avatar_data_uri(str(path)) == avatar_data_uri(path)


@pytest.mark.parametrize(
    ("name", "data", "mime_type"),
    [
        ("pic.png", PNG_BYTES, "image/png"),
        ("pic.jpg", PNG_BYTES, "image/png"),  # content wins over a lying extension
        ("pic.jpeg", JPEG_BYTES, "image/jpeg"),
        ("pic.gif", GIF_BYTES, "image/gif"),
        ("pic.webp", WEBP_BYTES, "image/webp"),
        ("pic.bmp", BMP_BYTES, "image/bmp"),
        ("pic.svg", SVG_BYTES, "image/svg+xml"),
        ("pic.svg", XML_SVG_BYTES, "image/svg+xml"),
    ]
    + [
        # no extension at all: sniffed from content alone
        (f"noext-{i}", data, mime_type)
        for i, data in enumerate(
            [JPEG_BYTES, GIF_BYTES, WEBP_BYTES, BMP_BYTES, SVG_BYTES]
        )
        for mime_type in [
            {
                JPEG_BYTES: "image/jpeg",
                GIF_BYTES: "image/gif",
                WEBP_BYTES: "image/webp",
                BMP_BYTES: "image/bmp",
                SVG_BYTES: "image/svg+xml",
            }[data]
        ]
    ],
)
def test_mime_type_from_extension_or_content(
    tmp_path, name: str, data: bytes, mime_type: str
) -> None:
    path = tmp_path / name
    path.write_bytes(data)

    uri = avatar_data_uri(path)

    assert uri.startswith(f"data:{mime_type};base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == data


def test_riff_that_is_not_webp_is_rejected(tmp_path) -> None:
    path = tmp_path / "pic.riff"
    path.write_bytes(b"RIFF\x00\x00\x00\x00XXXX" + b"\x00" * 10)

    with pytest.raises(ValueError, match="does not look like"):
        avatar_data_uri(path)


def test_missing_file_raises_file_not_found(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        avatar_data_uri(tmp_path / "nope.png")


def test_a_directory_is_not_a_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        avatar_data_uri(tmp_path)


def test_unsupported_content_is_rejected(tmp_path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("just some text, not an image")

    with pytest.raises(ValueError, match="does not look like a supported image"):
        avatar_data_uri(path)


def test_empty_file_is_rejected(tmp_path) -> None:
    path = tmp_path / "empty.png"
    path.write_bytes(b"")

    with pytest.raises(ValueError, match="does not look like"):
        avatar_data_uri(path)


def test_file_at_the_size_limit_is_accepted(tmp_path) -> None:
    path = tmp_path / "big.png"
    path.write_bytes(PNG_BYTES + b"\x00" * (MAX_AVATAR_FILE_SIZE - len(PNG_BYTES)))

    avatar_data_uri(path)  # must not raise


def test_file_over_the_size_limit_is_rejected(tmp_path) -> None:
    path = tmp_path / "big.png"
    path.write_bytes(PNG_BYTES + b"\x00" * (MAX_AVATAR_FILE_SIZE - len(PNG_BYTES) + 1))

    with pytest.raises(ValueError, match="over the"):
        avatar_data_uri(path)
