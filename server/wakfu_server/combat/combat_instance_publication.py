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


class PartyPublicationLease(PublicationLease):
    """A checkpoint remains valid only while every owner publication is live."""

    def __init__(self, leases, owner_bindings=()):
        self.leases = leases
        self.owner_bindings = owner_bindings

    @property
    def current(self):
        values = tuple(lease.current for lease in self.leases)
        return None if any(value is None for value in values) else values


class InstancePublicationTracker:
    def __init__(self):
        self.connection_nonce = uuid.uuid4().hex
        self.lease = PublicationLease()
        self.scope = None
        self.published = None
        self.sequence = 0

    def __deepcopy__(self, memo):
        # Connection authority is a service, not mutable encounter state.
        return self

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
        self.lease.owner_bindings = ((self, scope),)
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


def bind_party_encounter(
    fight, *, publications, npc_ids, player_ids=None, inactive_player_ids=()
):
    """Bind an exact cohort from each owner's completed transport publication.

    Each pair is an actual InstancePublicationTracker and its authenticated
    scope. No owner inherits another connection's publication or session lease.
    """
    fight.native_instance_publication_required = True
    fight.native_instance_publication_receipt = None
    fight.native_instance_publication_lease = None
    if not isinstance(publications, tuple) or not publications:
        raise ValueError("Actual participating owner publications required")
    if type(npc_ids) is not tuple or len(set(npc_ids)) != len(npc_ids):
        raise ValueError("Exact serialized NPC identities required")
    trackers, scopes, contexts, receipts = [], [], [], []
    for entry in publications:
        if type(entry) is not tuple or len(entry) != 2:
            raise ValueError("Actual publication tracker and scope required")
        tracker, scope = entry
        if not isinstance(tracker, InstancePublicationTracker) or scope is None:
            raise ValueError("Actual authenticated publication tracker required")
        # A party reader never owns another connection's scope transition.
        # Reject a stale candidate without revoking its newer live session.
        if tracker.scope != scope:
            raise ValueError("Owner publication scope changed during roster binding")
        context, receipt = tracker.published, tracker.lease.current
        if context is None or receipt is None:
            return False
        if receipt[1] != scope or receipt[3] != context.sha256:
            raise ValueError("Owner publication changed during roster binding")
        trackers.append(tracker)
        scopes.append(scope)
        contexts.append(context)
        receipts.append(receipt)
    leaders = tuple(scope[2] for scope in scopes)
    explicit_players = player_ids is not None
    player_ids = leaders if player_ids is None else player_ids
    if (
        type(inactive_player_ids) is not tuple
        or len(set(inactive_player_ids)) != len(inactive_player_ids)
        or not set(inactive_player_ids) <= set(player_ids)
        or any(
            not getattr(fight.actors[identity], "pve_withdrawn", False)
            for identity in inactive_player_ids
        )
    ):
        raise ValueError("Inactive publication players require actual PvE withdrawal")
    active_players = set(player_ids) - set(inactive_player_ids)
    if (
        type(player_ids) is not tuple
        or len(set(player_ids)) != len(player_ids)
        or len(set(leaders)) != len(leaders)
        or not set(leaders) <= active_players
        or len({id(tracker) for tracker in trackers}) != len(trackers)
        or set(player_ids) & set(npc_ids)
        or set(player_ids) | set(npc_ids) != set(fight.actors)
    ):
        raise ValueError("Incomplete or duplicated placement owner identity binding")
    if explicit_players:
        accounts = {scope[0] for scope in scopes}
        if (
            len(accounts) != len(scopes)
            or any(
                getattr(fight.actors[identity], "owner_id", None) not in accounts
                for identity in active_players
            )
            or any(
                getattr(fight.actors[identity], "owner_id", None) in accounts
                for identity in inactive_player_ids
            )
            or any(fight.actors[scope[2]].owner_id != scope[0] for scope in scopes)
        ):
            raise ValueError(
                "Controlled roster disagrees with authenticated owner publications"
            )
    # The native adapter validates unanimous instance and GN before mutation.
    bind_fight_npc_snapshots(
        fight,
        native_actor_classes={identity: "bje" for identity in npc_ids},
        actor_instance_ids={identity: scopes[0][4] for identity in npc_ids},
        published_contexts=tuple(contexts),
    )
    for identity in player_ids:
        fight.native_instance_difficulty_snapshots[
            identity
        ] = InstanceDifficultySnapshot(identity, None, "fBg.drG.Optional.empty")
    lease = PartyPublicationLease(
        tuple(tracker.lease for tracker in trackers), publications
    )
    expected = tuple(receipts)
    if lease.current != expected:
        raise ValueError("Owner publication changed during roster binding")
    # Retain the exact source identity, even if a connection updates just after
    # this check. require_current_publication will then reject that old receipt.
    fight.native_instance_publication_receipt = expected
    fight.native_instance_publication_lease = lease
    return True


def native_roster_bindings(fight):
    """Separate actual ordinary owned PCs from concrete native NPC sources."""
    companion_ids = {
        int(identity) for identity in getattr(fight, "native_companion_sources", {})
    }
    players = tuple(
        identity
        for identity, actor in fight.actors.items()
        if actor.owner_id is not None
        and actor.controlled
        and identity not in companion_ids
        and getattr(actor, "native_summon_source", None) is None
    )
    return players, tuple(
        identity for identity in fight.actors if identity not in players
    )


def refresh_owned_encounter(fight, *, publication=None):
    """Rebind an unpublished admitted roster using actual owner connections.

    Ordinary owned heroes share their owner's session publication, while each
    independent owner contributes its own tracker. Native companions remain
    concrete bje NPCs and receive the unanimous instance GN, never PC empties.
    Encounters without this publication contract preserve their legacy path.
    """
    if not getattr(fight, "native_instance_publication_required", False):
        return False
    if (
        getattr(fight, "native_instance_publication_lease", None) is None
        and getattr(fight, "native_instance_publication_receipt", None) is None
        and not getattr(fight, "native_instance_difficulty_snapshots", None)
    ):
        # Ordinary world entry may never have published a native instance.
        # Preserve that unknown source until an actual condition requests it;
        # admitting heroes must not introduce a blanket publication gate.
        return False
    require_current_publication(fight)
    lease = fight.native_instance_publication_lease
    bindings = getattr(lease, "owner_bindings", ())
    if not bindings:
        raise ValueError(
            "Native encounter has no authenticated owner publication sources"
        )
    if publication is not None:
        if type(publication) is not tuple or len(publication) != 2:
            raise ValueError("Actual joining owner publication required")
        tracker, scope = publication
        if not isinstance(tracker, InstancePublicationTracker):
            raise ValueError("Actual joining connection tracker required")
        if scope is None:
            raise ValueError("Actual joining authenticated scope required")
        if tracker.scope != scope:
            raise ValueError("Joining owner publication scope changed during admission")
        prior = {
            owner_scope[0]: (source, owner_scope) for source, owner_scope in bindings
        }
        if scope[0] in prior and prior[scope[0]] != publication:
            raise ValueError("Owner publication changed during roster admission")
        prior[scope[0]] = publication
        bindings = tuple(prior.values())
    players, npcs = native_roster_bindings(fight)
    if not bind_party_encounter(
        fight,
        publications=bindings,
        npc_ids=npcs,
        player_ids=players,
        inactive_player_ids=withdrawn_player_ids(fight),
    ):
        raise ValueError("Joining owner has no completed native instance publication")
    return True


def withdrawn_player_ids(fight):
    """Retained historical PCs never acquire authority from disconnected peers."""
    players, _npcs = native_roster_bindings(fight)
    return tuple(
        identity
        for identity in players
        if getattr(fight.actors[identity], "pve_withdrawn", False)
    )
