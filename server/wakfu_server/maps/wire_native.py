"""Borrowed-buffer adapters for the native one-pass packet assembler."""

import struct
from wakfu_server.spatial_native import get_spatial

PATCH = 2


def patch(body, replacements):
    """Replace nonoverlapping original-body spans with owned domain payloads."""
    replacements = sorted(replacements, key=lambda row: (row[0], row[1]))
    if not replacements:
        return body
    return get_spatial().call_binary(
        PATCH,
        buffers=(body, *(row[2] for row in replacements)),
        integers=tuple(value for row in replacements for value in row[:2]),
    )


def entity_record(
    body,
    replacements,
    *,
    expected_name,
    name,
    initial_position,
    position,
    positioned,
    map_id,
    direction,
    template_account,
    account_id,
    template_character,
    character_id,
    wrapper
):
    """Gather one borrowed entity description shared by single and batch calls."""
    replacements = sorted(replacements, key=lambda row: (row[0], row[1]))
    # struct preserves the existing native signed-width identity validation.
    identities = tuple(
        struct.unpack(">q", struct.pack(">q", value))[0]
        for value in (template_account, account_id, template_character, character_id)
    )
    return (
        (
            body,
            *(row[2] for row in replacements),
            expected_name,
            name,
            initial_position,
            position,
        ),
        (
            len(replacements),
            1,
            int(positioned),
            wrapper,
            *identities,
            int(map_id is not None),
            0 if map_id is None else map_id,
            int(direction is not None),
            0 if direction is None else direction,
            *(value for row in replacements for value in row[:2]),
        ),
    )


def assemble(record):
    buffers, integers = record
    return get_spatial().call_binary(4, buffers=buffers, integers=integers)


def roster(records):
    """Assemble all roster rows with the same native entity kernel in one call."""
    return get_spatial().call_binary(
        5,
        buffers=tuple(buffer for buffers, _ in records for buffer in buffers),
        integers=(
            len(records),
            *(number for _, integers in records for number in integers),
        ),
    )
