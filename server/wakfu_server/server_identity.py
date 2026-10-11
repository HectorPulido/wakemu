"""Live realm display names using the native dispatcher server-list format."""
import struct
import unicodedata
from protocol_codec import Reader


def validate_server_name(value):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 80
        or value != value.strip()
        or len(value.encode("utf-8")) > 255
        or any(unicodedata.category(char).startswith("C") for char in value)
    ):
        raise ValueError(
            "Server name requires 1–80 characters, at most 255 UTF-8 bytes, without control characters or surrounding whitespace"
        )
    return value


def configured_server_name(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='server_name'"
        ).fetchone()
    return validate_server_name("Rubilax" if row is None else row["value"])


def rename_realm(body, name):
    """Replace only realm 10 names; preserve endpoints and opaque realm policies."""
    encoded = validate_server_name(name).encode("utf-8")
    packed = struct.pack(">B", len(encoded)) + encoded
    reader = Reader(body)
    replacements = []
    found = False

    def count():
        value = reader.number("i")
        if value < 0:
            raise ValueError("Negative server-list count")
        return value

    for _ in range(count()):
        realm_id = reader.number("i")
        if reader.number("B"):
            reader.take(4)
        start = reader.pos
        reader.text("B")
        if realm_id == 10:
            replacements.append((start, reader.pos, packed))
            found = True
        for _ in range(reader.number("B")):
            reader.take(1)
            start = reader.pos
            reader.text("B")
            if realm_id == 10:
                replacements.append((start, reader.pos, packed))
        reader.take(4)
        if reader.number("B"):
            reader.take(4)
        reader.text("I")
        reader.take(4 * count())
        reader.take(1 + 4 + 1 + 4 + 1)
    # Validate the entire packet before returning a modified copy.
    for _ in range(count()):
        reader.take(4)
        reader.take(reader.number("i"))
        reader.take(reader.number("i"))
        reader.take(1)
    reader.take(1)
    reader.finish()
    if not found:
        raise ValueError("Local realm is missing from server list")
    for start, end, replacement in reversed(replacements):
        body = body[:start] + replacement + body[end:]
    return body
