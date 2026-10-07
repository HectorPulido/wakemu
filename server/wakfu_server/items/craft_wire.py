"""Verified ordinary recipe request; no assumed response or artisan contract.

Native com12231 writes table UID i64, recipe ID i32, quantity i32.
This decoder supplies no ownership, profession or ingredient authorization.
The separate artisan request13515 requires its own verified domain rules.
"""
import struct

RESULTS = (
    "NO_ERROR",
    "CHARACTER_CANNOT_USE",
    "UNKNOWN_CRAFT",
    "UNKNOWN_RECIPE",
    "CRAFT_DATA_UNAVAILABLE",
    "ALREADY_LEARNED",
    "UNLEARN_CRAFT",
    "TABLE_TOO_FAR",
    "RECIPE_TABLE_NOT_ALLOWED",
    "RECIPE_CRITERION_UNAVAILABLE",
    "BAD_INGREDIENTS",
    "NO_REQUIRED_ITEM",
    "CRAFT_END_TOO_EARLY",
    "SUCCESS_ROLL_FAILED",
    "FAKE_CRAFT_FAILED",
    "FAILING_SECRET_CRAFT_FAILED",
    "FORCED_CANCEL",
    "NOT_SUBSCRIBER",
    "UNKNOWN",
    "CRAFTSMAN_ABSENT",
    "NOT_IN_DIMENSIONAL_BAG",
    "TOO_MUCH_KAMAS",
    "NOT_ENOUGH_KAMAS",
)


def request(opcode, body):
    if opcode != 12231:
        raise ValueError("Unsupported crafting request mode")
    if not isinstance(body, bytes) or len(body) != 16:
        raise ValueError("Invalid crafting request length")
    table_id, recipe_id, quantity = struct.unpack(">qii", body)
    if table_id <= 0 or recipe_id <= 0 or quantity <= 0:
        raise ValueError("Invalid crafting request identity or quantity")
    return dict(table_id=table_id, recipe_id=recipe_id, quantity=quantity)


def occupation_request(body):
    """Decode native ``conn13382``: station, recipe/mode and offered inputs.

    The packet has no request nonce. The component map is client input and is
    only a claim to compare against an authoritative recipe/inventory view.
    Special native modes are preserved for the authority to accept or reject.
    """
    if not isinstance(body, bytes) or len(body) < 13 or (len(body) - 13) % 6:
        raise ValueError("Invalid crafting occupation request length")
    table_id, recipe_id, mode = struct.unpack_from(">qib", body)
    if table_id <= 0 or recipe_id < 0:
        raise ValueError("Invalid crafting occupation identity")
    components = {}
    for offset in range(13, len(body), 6):
        item_id, quantity = struct.unpack_from(">ih", body, offset)
        if item_id <= 0 or quantity <= 0 or item_id in components:
            raise ValueError("Invalid crafting occupation component")
        components[item_id] = quantity
    return dict(
        table_id=table_id, recipe_id=recipe_id, mode=mode, components=components
    )


def result(status, auxiliary, processed_count):
    """cuu13479: enum byte, signed i32 field, completed-attempt count i16.

    chh ignores the i32 field; its domain meaning is not assumed here. The
    count updates the batch and success counter, not XP. Authoritative XP
    uses the separately verified cux12916 carrier.
    """
    if type(status) is not int or not 0 <= status < len(RESULTS):
        raise ValueError("Invalid native crafting result")
    if type(auxiliary) is not int or not -(2**31) <= auxiliary < 2**31:
        raise ValueError("Invalid native crafting auxiliary field")
    if type(processed_count) is not int or not 0 <= processed_count <= 32767:
        raise ValueError("Invalid crafting processed count")
    return 13479, struct.pack(">Bih", status, auxiliary, processed_count)


def cancellation(body):
    """cro13429 emitted by blQ.dwC: result3, occupation type8.

    No recipe, token or owner identity is carried; the authority must match
    the cancellation to the caller's current owned crafting occupation.
    Other occupation kinds belong to their existing handlers.
    """
    if not isinstance(body, bytes) or len(body) != 3:
        raise ValueError("Invalid crafting cancellation length")
    status, occupation_type = struct.unpack(">Bh", body)
    if status != 3 or occupation_type != 8:
        raise ValueError("Unsupported crafting occupation result")
    return dict(result=status, occupation_type=occupation_type)


def completion_request(body):
    """Decode blQ.dwm's native 13429 completion request (result2/type8)."""
    if not isinstance(body, bytes) or len(body) != 3:
        raise ValueError("Invalid crafting completion length")
    status, occupation_type = struct.unpack(">Bh", body)
    if status != 2 or occupation_type != 8:
        raise ValueError("Unsupported crafting occupation result")
    return dict(result=status, occupation_type=occupation_type)


def occupation_started(table_id, recipe_id, mode, duration_ms, *, extra=0):
    """Encode cuv13989; its final i64 is preserved as an opaque native field."""
    if (
        type(table_id) is not int
        or not 0 < table_id < 2**63
        or type(recipe_id) is not int
        or not 0 <= recipe_id < 2**31
        or type(mode) is not int
        or not -128 <= mode <= 127
        or type(duration_ms) is not int
        or not 1 <= duration_ms < 2**63
        or type(extra) is not int
        or not -(2**63) <= extra < 2**63
    ):
        raise ValueError("Invalid native craft occupation event")
    return 13989, struct.pack(">qibqq", table_id, recipe_id, mode, duration_ms, extra)
