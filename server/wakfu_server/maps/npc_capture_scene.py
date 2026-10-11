"""Scope native exploration NPCs in reference replay to their original scene."""
import struct


def scope_reference_actors(body, map_id, instance_id, registry_actor_ids=()):
    """Remove players and native format11 NPCs belonging to another scene.

    Format11 POSITION proves native map, but reference captures do not establish
    instance ownership. Such captured actors are only usable in public instance0.
    Other actor formats retain the existing replay behavior, without guessing a
    byte offset for unsupported serializers.
    """
    if len(body) < 2:
        raise ValueError("Malformed native actor replay")
    offset, entries = 2, []
    registry_actor_ids = frozenset(registry_actor_ids)
    for _ in range(body[1]):
        if len(body) - offset < 11:
            raise ValueError("Truncated native actor replay header")
        actor_type, identity, size = struct.unpack_from(">BqH", body, offset)
        start = offset
        offset += 11
        blob = body[offset : offset + size]
        offset += size
        if len(blob) != size:
            raise ValueError("Truncated native actor replay payload")
        if actor_type == 0 or (actor_type == 1 and identity in registry_actor_ids):
            continue
        if actor_type == 1 and blob and blob[0] == 11:
            if len(blob) < 20:
                raise ValueError("Truncated native NPC identity")
            inner_identity = struct.unpack_from(">q", blob, 1)[0]
            if inner_identity != identity:
                raise ValueError("Native NPC envelope identity mismatch")
            name_size = struct.unpack_from(">H", blob, 18)[0]
            position = 20 + name_size + 2
            if len(blob) < position + 18:
                raise ValueError("Truncated native NPC position")
            native_map = struct.unpack_from(">q", blob, position + 10)[0]
            if instance_id != 0 or native_map != map_id:
                continue
        entries.append(body[start:offset])
    if offset != len(body):
        raise ValueError("Native actor replay has trailing bytes")
    return bytes([body[0], len(entries)]) + b"".join(entries)


def filter_reference_actors(body, character, registry_actor_ids=()):
    """Registry identities, including disabled rows, hydrate exclusively there.

    Caller supplies all registry actor IDs, not only the current enabled scene;
    this prevents a captured replay from resurrecting quarantined placements.
    """
    return scope_reference_actors(
        body, character["map_id"], character["instance_id"], registry_actor_ids
    )
