"""Server-owned current exterior authority for native instance-entry recovery."""
from dataclasses import dataclass


_POSITION = ("map_id", "instance_id", "x", "y", "z", "direction")
_SCENE_POSITION = _POSITION[:-1]


@dataclass(frozen=True)
class OutsideCompanyProof:
    requester: object
    owners: tuple
    character_ids: tuple
    owner_positions: tuple
    validate_live: object

    def __post_init__(self):
        if (
            not isinstance(self.owners, tuple)
            or not self.owners
            or self.requester not in self.owners
            or len({owner.account_id for owner in self.owners}) != len(self.owners)
            or not isinstance(self.character_ids, tuple)
            or not self.character_ids
            or tuple(sorted(set(self.character_ids))) != self.character_ids
            or any(
                type(identity) is not int or identity <= 0
                for identity in self.character_ids
            )
            or any(
                owner.character_id not in self.character_ids for owner in self.owners
            )
            or not isinstance(self.owner_positions, tuple)
            or len(self.owner_positions) != len(self.owners)
            or not callable(self.validate_live)
        ):
            raise ValueError("Invalid native exterior company authority")
        positions = {}
        for point in self.owner_positions:
            if (
                not isinstance(point, tuple)
                or len(point) != 7
                or any(type(value) is not int for value in point)
                or point[0] in positions
                or not 0 <= point[-1] <= 7
            ):
                raise ValueError("Invalid native exterior owner position")
            positions[point[0]] = point[1:]
        if set(positions) != {owner.character_id for owner in self.owners} or any(
            positions[owner.character_id][:2] != (owner.map_id, owner.instance_id)
            for owner in self.owners
        ):
            raise ValueError("Native exterior owner scope changed")

    def require_live(self):
        if self.validate_live() is not True:
            raise ValueError("Native exterior owner changed during entry recovery")


def _census(store, accounts):
    with store.connection() as db:
        sessions = db.execute(
            "SELECT account_id,generation,character_id,expires_at FROM sessions WHERE account_id=ANY(%s) ORDER BY account_id",
            (accounts,),
        ).fetchall()
        parties = db.execute(
            "SELECT p.id,p.leader_id,p.revision,m.character_id FROM player_parties p "
            "JOIN player_party_members m ON m.party_id=p.id JOIN characters c ON c.id=m.character_id "
            "WHERE c.account_id=ANY(%s) ORDER BY p.id,m.character_id",
            (accounts,),
        ).fetchall()
        rosters = db.execute(
            "SELECT account_id,leader_id,revision FROM account_hero_rosters WHERE account_id=ANY(%s) ORDER BY account_id",
            (accounts,),
        ).fetchall()
        slots = db.execute(
            "SELECT account_id,slot,character_id FROM account_hero_slots WHERE account_id=ANY(%s) ORDER BY account_id,slot",
            (accounts,),
        ).fetchall()
    sessions = tuple(
        dict(
            account_id=row["account_id"],
            generation=row["generation"],
            character_id=row["character_id"],
            active=row["expires_at"] > store.now(),
        )
        for row in sessions
    )
    return sessions, tuple(parties), tuple(rosters), tuple(slots)


def capture(
    requester,
    owner_rows,
    character_ids,
    world,
    positions,
    source,
    source_allowed,
    *,
    allow_world_snapshot=False
):
    """Capture matching loaded World and position-buffer identities under owner fences.

    The caller owns every affected Positions.account_barrier until the entry
    transaction and its post-commit cleanup complete. SQL ownership, selected
    sessions, party/hero census and level are still checked by admission.
    """
    from wakfu_server.combat_shared import Session

    if not callable(source_allowed):
        raise ValueError("Native exterior approach authority is required")
    owners, snapshots, missing_buffers = [], [], set()
    for row in sorted(owner_rows, key=lambda item: item["account_id"]):
        identity = row["id"]
        live = world.live_identity(character_id=identity)
        if (
            live is None
            or live[0] != row["generation"]
            or live[1]["account_id"] != row["account_id"]
        ):
            raise ValueError("Native exterior requires the loaded selected owner")
        key = (row["account_id"], row["generation"], identity)
        with positions.lock:
            entry = positions.entries.get(key)
            current = None if entry is None else dict(entry["current"])
        if current is None and allow_world_snapshot:
            # A committed entry releases its source buffer before native
            # hydration. Only an exact current pending-run resume may use
            # this still-loaded server World snapshot instead.
            current = dict(live[1])
            missing_buffers.add(identity)
        if (
            current is None
            or not positions.lease_active(*key)
            or any(live[1][field] != current[field] for field in _SCENE_POSITION)
            or source_allowed(current, dict(source)) is not True
        ):
            raise ValueError("Native exterior world and buffered position disagree")
        if current["map_id"] != source["map_id"]:
            raise ValueError("Native exterior portal belongs to another map")
        owners.append(
            Session(
                row["account_id"],
                identity,
                row["generation"],
                current["map_id"],
                current["instance_id"],
            )
        )
        snapshots.append((identity,) + tuple(current[field] for field in _POSITION))
    owners, snapshots = tuple(owners), tuple(snapshots)
    accounts = sorted(owner.account_id for owner in owners)
    census = _census(positions.store, accounts)
    if not all(row["active"] for row in census[0]) or {
        (row["account_id"], row["generation"], row["character_id"]) for row in census[0]
    } != {(owner.account_id, owner.generation, owner.character_id) for owner in owners}:
        raise ValueError(
            "Native exterior proof has no matching current selected leases"
        )
    request = next(
        (
            owner
            for owner in owners
            if owner.account_id == requester.account_id
            and owner.character_id == requester.character_id
            and owner.generation == requester.generation
        ),
        None,
    )
    if request is None:
        raise ValueError("Native exterior requester is outside the owned company")

    def validate_live():
        if _census(positions.store, accounts) != census:
            return False
        for owner, point in zip(owners, snapshots):
            live = world.live_identity(character_id=owner.character_id)
            if (
                live is None
                or live[0] != owner.generation
                or live[1]["account_id"] != owner.account_id
                or tuple(live[1][field] for field in _SCENE_POSITION) != point[1:-1]
            ):
                return False
            key = (owner.account_id, owner.generation, owner.character_id)
            with positions.lock:
                entry = positions.entries.get(key)
                current = None if entry is None else entry["current"]
                if current is None:
                    if owner.character_id not in missing_buffers:
                        return False
                elif tuple(current[field] for field in _POSITION) != point[1:]:
                    return False
            if not positions.lease_active(*key):
                return False
        return True

    proof = OutsideCompanyProof(
        request, owners, tuple(sorted(character_ids)), snapshots, validate_live
    )
    proof.require_live()
    return proof
