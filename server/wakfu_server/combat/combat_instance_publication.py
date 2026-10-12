"""Private actual-write capture, session fencing and encounter authority lease."""
import struct
import uuid
from wakfu_server.maps.proto_dungeon import decode
from .combat_instance_context import capture_publication, bind_fight_npc_snapshots
from .combat_instance_level_group import InstanceDifficultySnapshot


class PublicationLease:
    """One live publication identity, shared by copied encounter checkpoints."""

    def __init__(self):
        self.current = None

    def __deepcopy__(self, memo):
        return self


class InstancePublicationTracker:
    def __init__(self):
        self.connection_nonce = uuid.uuid4().hex
        self.lease = PublicationLease()
        self.scope = None
        self.published = None
        self.sequence = 0

    def invalidate(self):
        self.lease.current = None
        self.published = None

    def synchronize(self, scope):
        if scope is not None:
            if (
                type(scope) is not tuple
                or len(scope) != 5
                or any(type(scope[i]) is not int for i in (0, 2, 3, 4))
                or scope[0] <= 0
                or scope[2] <= 0
                or scope[3] <= 0
                or scope[4] < 0
                or type(scope[1]) is not str
                or not scope[1]
            ):
                self.invalidate()
                raise ValueError("Missing authenticated native session scope")
        if scope != self.scope:
            self.invalidate()
            self.scope = scope

    def after_write(self, data, scope):
        """Call under the existing connection write lock AFTER socket success."""
        self.synchronize(scope)
        if scope is None:
            return
        try:
            offset = 0
            while offset < len(data):
                if offset + 6 > len(data):
                    raise ValueError("Truncated actually written frame")
                length, opcode = struct.unpack_from(">IH", data, offset)
                if length < 6 or offset + length > len(data):
                    raise ValueError("Invalid actually written frame size")
                payload = data[offset + 6 : offset + length]
                offset += length
                if opcode not in (13974, 13339):
                    continue
                self.published = capture_publication(
                    opcode, payload, session_actor_id=scope[2], instance_id=scope[4]
                )
                self.sequence += 1
                self.lease.current = (
                    self.connection_nonce,
                    scope,
                    self.sequence,
                    self.published.sha256,
                    decode(self.published.payload)["difficulty_level"],
                )
        except Exception:
            self.invalidate()
            raise

    def bind_encounter(self, fight, scope, *, npc_ids, player_id):
        """Caller supplies actual verified create_placement NPC/PC identities."""
        self.synchronize(scope)
        fight.native_instance_publication_required = True
        if self.published is None or self.lease.current is None:
            return False
        if type(npc_ids) is not tuple or len(set(npc_ids)) != len(npc_ids):
            raise ValueError("Exact serialized NPC identities required")
        if player_id not in fight.actors or set(npc_ids) | {player_id} != set(
            fight.actors
        ):
            raise ValueError("Incomplete placement actor identity binding")
        bind_fight_npc_snapshots(
            fight,
            native_actor_classes={i: "bje" for i in npc_ids},
            actor_instance_ids={i: scope[4] for i in npc_ids},
            published_contexts=(self.published,),
        )
        # Actual ordinary player bjo/biB inherits eGj.drG Optional.empty.
        fight.native_instance_difficulty_snapshots[
            player_id
        ] = InstanceDifficultySnapshot(player_id, None, "fBg.drG.Optional.empty")
        fight.native_instance_publication_receipt = self.lease.current
        fight.native_instance_publication_lease = self.lease
        return True


def require_current_publication(fight):
    if not getattr(fight, "native_instance_publication_required", False):
        raise ValueError("Encounter has no actual native publication binding")
    lease = getattr(fight, "native_instance_publication_lease", None)
    receipt = getattr(fight, "native_instance_publication_receipt", None)
    if (
        not isinstance(lease, PublicationLease)
        or receipt is None
        or lease.current != receipt
    ):
        raise ValueError("Native instance publication expired or replaced")
