"""Small, payload-free summaries for native combat-effect wire frames."""
import struct


def effect_application_metadata(opcode, body):
    """Extract safe identity fields from an executable 12613 effect packet.

    Return ``None`` for other opcodes. Malformed 12613 bodies return a bounded
    status record instead of raising, so diagnostics can never block delivery.
    The protobuf parser reads only effect identity fields; the body is never
    returned or included in the summary.
    """
    if opcode != 12613:
        return None

    result = {
        "opcode": 12613,
        "fight_id": None,
        "action_id": None,
        "effect_family": None,
        "generic_effect_id": None,
        "execute_flag": None,
        "runner_uid": None,
        "target_uid": None,
        "parse_status": "malformed",
    }
    try:
        if type(body) is not bytes or len(body) < 19:
            return result
        fight_id, action_id = struct.unpack_from(">ii", body, 0)
        execute_flag = body[12]
        effect_family = struct.unpack_from(">i", body, 13)[0]
        protobuf_size = struct.unpack_from(">h", body, 17)[0]
        result.update(
            fight_id=fight_id,
            action_id=action_id,
            effect_family=effect_family,
            execute_flag=execute_flag,
        )
        if (
            protobuf_size < 0
            or len(body) != 19 + protobuf_size
            or execute_flag not in (0, 1)
        ):
            return result

        from .combat_effect_removal import _identity_fields

        identity = _identity_fields(body[19:], integer_fields=(1, 2, 3, 4, 6, 7))
        runner_uid = identity.get(1)
        target_uid = identity.get(7)
        generic_effect_id = identity.get(3)
        if (
            type(runner_uid) is not int
            or type(target_uid) is not int
            or type(generic_effect_id) is not int
        ):
            return result
        result.update(
            runner_uid=runner_uid,
            # Protobuf int64 values use two's-complement varints. The existing
            # identity parser returns their raw bits; restore signed actor IDs
            # so negative NPC IDs correlate with combat logs and fight state.
            target_uid=(
                target_uid if target_uid < (1 << 63) else target_uid - (1 << 64)
            ),
            generic_effect_id=generic_effect_id,
            parse_status="ok",
        )
        return result
    except Exception:
        # This code runs after successful write(), but remains strictly
        # observational even if the parser encounters an unexpected shape.
        return result
