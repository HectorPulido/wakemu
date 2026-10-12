"""Private binding adapter for the actual published native instance context."""
from dataclasses import dataclass
import hashlib
from wakfu_server.maps.proto_dungeon import decode
from .combat_instance_level_group import InstanceDifficultySnapshot


@dataclass(frozen=True)
class PublishedInstanceContext:
    session_actor_id: int
    instance_id: int
    payload: bytes

    def __post_init__(self):
        if type(self.session_actor_id) is not int or type(self.instance_id) is not int:
            raise ValueError("Actual session and instance identity required")
        if type(self.payload) is not bytes:
            raise ValueError("Immutable actually published ProtoDungeon required")
        decode(self.payload)

    @property
    def sha256(self):
        return hashlib.sha256(self.payload).hexdigest()


def npc_snapshot(
    actor_id, *, native_actor_class, actor_instance_id, session_actor_id, published
):
    """bje.drG -> ceG.lYx.GN; caller must supply its published session record.

    This adapter never loads defaults or guesses a context from an NPC species,
    map or difficulty catalog. It has no installation hook in shared Fight.
    """
    if native_actor_class != "bje":
        raise ValueError("Unknown concrete native NPC drG producer")
    if not isinstance(published, PublishedInstanceContext):
        raise ValueError("Missing actual published instance context")
    if (
        type(actor_instance_id) is not int
        or type(session_actor_id) is not int
        or actor_instance_id != published.instance_id
        or session_actor_id != published.session_actor_id
    ):
        raise ValueError("Published context belongs to another session or instance")
    return InstanceDifficultySnapshot(
        actor_id, decode(published.payload)["difficulty_level"], "fBg.drG.fBf.GN"
    )


def bind_fight_npc_snapshots(
    fight, *, native_actor_classes, actor_instance_ids, published_contexts
):
    """Private adapter: bind every NPC using unanimous actual session authority.

    No dictionary is installed until every binding validates. Different client
    session difficulty values must not become one invented encounter context.
    """
    if not isinstance(published_contexts, tuple) or not published_contexts:
        raise ValueError("Actual participating session publications required")
    if any(not isinstance(p, PublishedInstanceContext) for p in published_contexts):
        raise ValueError("Unattested participating session publication")
    contexts = {
        (p.instance_id, decode(p.payload)["difficulty_level"])
        for p in published_contexts
    }
    if len(contexts) != 1:
        raise ValueError("Participating native sessions disagree on instance GN")
    if set(native_actor_classes) != set(actor_instance_ids):
        raise ValueError("Incomplete concrete native actor bindings")
    snapshots = {}
    actual_actors = {a.id for a in fight.actors.values()}
    if not set(native_actor_classes) <= actual_actors:
        raise ValueError("Published NPC binding does not belong to actual Fight")
    p = published_contexts[0]
    for actor_id, class_name in native_actor_classes.items():
        snapshots[actor_id] = npc_snapshot(
            actor_id,
            native_actor_class=class_name,
            actor_instance_id=actor_instance_ids[actor_id],
            session_actor_id=p.session_actor_id,
            published=p,
        )
    fight.native_instance_difficulty_snapshots = snapshots
    return snapshots.copy()


def capture_publication(message_id, payload, *, session_actor_id, instance_id):
    """Capture actual outgoing13974 context or13339 update; no inferred defaults."""
    import struct

    if type(payload) is not bytes:
        raise ValueError("Actual immutable outgoing packet required")
    if message_id == 13974:
        offset = 0
        blocks = []
        for _ in range(4):
            if offset + 2 > len(payload):
                raise ValueError("Truncated native bootstrap block")
            length = struct.unpack_from(">H", payload, offset)[0]
            offset += 2
            if offset + length > len(payload):
                raise ValueError("Truncated native bootstrap payload")
            blocks.append(payload[offset : offset + length])
            offset += length
        if offset != len(payload):
            raise ValueError("Unexpected trailing bootstrap bytes")
        context = blocks[3]
    elif message_id == 13339:
        if len(payload) < 12:
            raise ValueError("Truncated native instance update")
        update_instance, length = struct.unpack_from(">qi", payload)
        if update_instance != instance_id or length < 0 or len(payload) != 12 + length:
            raise ValueError("Wrong native update instance or payload size")
        context = payload[12:]
    else:
        raise ValueError("Packet does not publish native instance context")
    return PublishedInstanceContext(session_actor_id, instance_id, context)
