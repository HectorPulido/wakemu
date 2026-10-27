"""Reconcile native exterior retries from actual loaded, selected World owners."""
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass

from wakfu_server.native_entry_authority import capture


_FIELDS = ("map_id", "instance_id", "x", "y", "z", "direction")


def _census(db, character_id):
    party = db.execute(
        "SELECT p.id,p.leader_id,p.revision FROM player_parties p "
        "JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
        (character_id,),
    ).fetchone()
    ids = (
        [character_id]
        if party is None
        else [
            row["character_id"]
            for row in db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                (party["id"],),
            ).fetchall()
        ]
    )
    rows = db.execute(
        "SELECT c.*,s.generation,s.character_id AS selected_character_id,s.expires_at "
        "FROM characters c LEFT JOIN sessions s ON s.account_id=c.account_id "
        "WHERE c.id=ANY(%s) AND c.deleted_at IS NULL ORDER BY c.id",
        (ids,),
    ).fetchall()
    accounts = sorted({row["account_id"] for row in rows})
    slots = db.execute(
        "SELECT h.account_id,h.slot,h.character_id,r.leader_id FROM account_hero_slots h "
        "JOIN account_hero_rosters r USING(account_id) WHERE h.account_id=ANY(%s) "
        "ORDER BY h.account_id,h.slot",
        (accounts,),
    ).fetchall()
    identities = tuple(sorted(set(ids) | {row["character_id"] for row in slots}))
    return party, tuple(rows), tuple(slots), identities


def _runs(db, identities):
    return tuple(
        db.execute(
            "SELECT r.* FROM rift_instances r WHERE r.status IN('entered','running') "
            "AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(r.members) member "
            "WHERE member::bigint=ANY(%s)) ORDER BY r.instance_id",
            (list(identities),),
        ).fetchall()
    )


@dataclass
class ExteriorEntryRecovery:
    store: object
    proof: object
    party: object
    slots: tuple
    selected: object
    source: object
    combat: object = None
    retired_instances: set = None
    combat_result: object = None

    def __post_init__(self):
        self.retired_instances = set()

    def bind(self, selected, source):
        if selected != self.selected or source != self.source:
            raise ValueError("Native exterior portal changed during recovery")

    def external_mains(self, db, party, rows):
        """Validate the same census and cancel old custody before moving any row."""
        self.proof.require_live()
        current_party, current, slots, identities = _census(
            db, self.proof.requester.character_id
        )
        if (
            party != self.party
            or current_party != self.party
            or slots != self.slots
            or identities != self.proof.character_ids
            or {row["id"] for row in rows}
            != {owner.character_id for owner in self.proof.owners}
            or any(
                row["leader_id"]
                not in {owner.character_id for owner in self.proof.owners}
                for row in slots
            )
        ):
            raise ValueError("Native exterior party or hero census changed")
        owners = {owner.character_id: owner for owner in self.proof.owners}
        if any(
            row["account_id"] != owners[row["id"]].account_id
            or row["generation"] != owners[row["id"]].generation
            or row["selected_character_id"] != row["id"]
            or row["expires_at"] is None
            or row["expires_at"] <= self.store.now()
            for row in current
        ):
            raise ValueError("Native exterior selected owner changed")
        old_runs = _runs(db, identities)
        if any(not set(run["members"]).issubset(identities) for run in old_runs):
            raise ValueError(
                "A retained rift includes a member outside this loaded company"
            )
        if self.combat is not None:
            self.combat_result = self.combat.commit(db)
        for old in old_runs:
            run = db.execute(
                "SELECT * FROM rift_instances WHERE instance_id=%s FOR UPDATE",
                (old["instance_id"],),
            ).fetchone()
            if not set(run["members"]).issubset(identities):
                raise ValueError(
                    "Retained rift membership changed during exterior recovery"
                )
            if run["status"] == "entered" and run["fight_id"] is None:
                from wakfu_server.rift_runtime import close_entered

                close_entered(
                    db,
                    run["instance_id"],
                    next(
                        identity
                        for identity in identities
                        if identity in run["members"]
                    ),
                )
            elif run["status"] != "closed":
                raise ValueError("A retained rift still has an unrecovered encounter")
            self.retired_instances.add(run["instance_id"])
        self._depart_dungeons(db, identities)
        points = {
            point[0]: dict(zip(_FIELDS, point[1:]))
            for point in self.proof.owner_positions
        }
        refreshed = {
            row["id"]: row
            for row in db.execute(
                "SELECT id,hp,max_hp,hp_damage,health_dead,hp_zero_valid FROM characters WHERE id=ANY(%s)",
                (list(identities),),
            ).fetchall()
        }
        return [dict(row, **refreshed[row["id"]], **points[row["id"]]) for row in rows]

    def before_commit(self, db):
        self.proof.require_live()
        party, rows, slots, identities = _census(db, self.proof.requester.character_id)
        if (
            party != self.party
            or slots != self.slots
            or identities != self.proof.character_ids
        ):
            raise ValueError("Native exterior census changed before admission commit")
        expected = {
            (owner.account_id, owner.generation, owner.character_id)
            for owner in self.proof.owners
        }
        actual = {
            (row["account_id"], row["generation"], row["selected_character_id"])
            for row in rows
        }
        if actual != expected:
            raise ValueError(
                "Native exterior selected leases changed before admission commit"
            )

    def _depart_dungeons(self, db, identities):
        runs = db.execute(
            "SELECT DISTINCT d.* FROM dungeon_instances d JOIN dungeon_instance_members m "
            "ON m.instance_id=d.instance_id WHERE m.character_id=ANY(%s) AND m.status='active' "
            "ORDER BY d.instance_id",
            (list(identities),),
        ).fetchall()
        for run in runs:
            db.execute(
                "SELECT instance_id FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
                (run["instance_id"],),
            ).fetchone()
            members = db.execute(
                "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s "
                "AND status='active' ORDER BY character_id FOR UPDATE",
                (run["instance_id"],),
            ).fetchall()
            if not {row["character_id"] for row in members}.issubset(identities):
                raise ValueError(
                    "An active dungeon includes a member outside this loaded company"
                )
            db.execute(
                "UPDATE dungeon_instance_members SET status='returned',ended_at=%s "
                "WHERE instance_id=%s AND status='active'",
                (self.store.now(), run["instance_id"]),
            )
            db.execute(
                "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
                "WHERE instance_id=%s AND status='pending'",
                (self.store.now(), run["instance_id"]),
            )
            db.execute(
                "UPDATE dungeon_instances SET status='closed',ended_at=%s,revision=revision+1 "
                "WHERE instance_id=%s AND status IN('active','completed')",
                (self.store.now(), run["instance_id"]),
            )
            self.retired_instances.add(run["instance_id"])
        if runs:
            from wakfu_server.dungeon_modulation_health import reconcile

            reconcile(self.store, db, identities)


def _resume(store, plan, proof, pending_destination, options):
    """Replay a still-owned current-generation hydration, never create a second run."""
    from wakfu_server import rift_entry_adapter

    party, owners, slots, identities, selected, source = plan
    with store.connection() as db:
        run = db.execute(
            "SELECT * FROM rift_instances WHERE instance_id=%s",
            (pending_destination["instance_id"],),
        ).fetchone()
        if run is None or run["status"] != "entered" or run["fight_id"] is not None:
            return None
        rows = rift_entry_adapter._roster(
            db,
            store,
            proof.requester.account_id,
            proof.requester.generation,
            proof.requester.character_id,
            require_leader=False,
            expand=False,
        )
        run = db.execute(
            "SELECT * FROM rift_instances WHERE instance_id=%s FOR UPDATE",
            (pending_destination["instance_id"],),
        ).fetchone()
        if run is None or run["status"] != "entered" or run["fight_id"] is not None:
            return None
        actual_party, actual_owners, actual_slots, actual_ids = _census(
            db, proof.requester.character_id
        )
        if (
            actual_party != party
            or actual_slots != slots
            or actual_ids != identities
            or set(run["members"]) != set(identities)
            or run["catalog"] != selected
        ):
            raise ValueError("Pending native rift company changed")
        if db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=ANY(%s) AND f.status IN('placement','active') LIMIT 1",
            (list(identities),),
        ).fetchone():
            raise ValueError("Pending rift owner belongs to a retained encounter")
        caller = next(row for row in rows if row["id"] == proof.requester.character_id)
        if any(caller[field] != pending_destination[field] for field in _FIELDS[:-1]):
            return None
        from wakfu_server.instance_entry_level import enforced, minimum_level_allowed

        minimum_enforced = enforced(db)
        levels = db.execute(
            "SELECT id,level FROM characters WHERE id=ANY(%s)", (list(identities),)
        ).fetchall()
        if set(row["id"] for row in levels) != set(identities) or any(
            not minimum_level_allowed(
                row["level"], selected["level"], enforce_minimum=minimum_enforced
            )
            for row in levels
        ):
            raise ValueError(
                "Pending rift company no longer satisfies its native level"
            )
        proof.require_live()
        return dict(
            run=run,
            destination=dict(pending_destination),
            members=tuple(rows),
            transport_members=(caller,),
            resumed=True,
        )


def attempt(
    store,
    positions,
    account_id,
    generation,
    character_id,
    body,
    *,
    world,
    combat_registry=None,
    groups=None,
    checkpoint_writer=None,
    options
):
    """Return (handled,result); normal unaffected entries keep their existing path."""
    from wakfu_server import rift_entry_adapter, rift_transition_delivery as delivery
    from wakfu_server.combat_shared import Session

    live = world.live_identity(character_id=character_id)
    if live is None or live[0] != generation or live[1]["account_id"] != account_id:
        return False, None
    with store.connection() as db:
        raw = db.execute(
            "SELECT value FROM settings WHERE name='rift_catalog'"
        ).fetchone()
        if raw is None:
            return False, None
        resolved = rift_entry_adapter.resolve_portal(
            raw["value"], live[1]["map_id"], body
        )
        if resolved is None:
            return False, None
        selected, source = resolved
        party, owners, slots, identities = _census(db, character_id)
        # Only references are inspected here; locked validation happens below.
        retained = db.execute(
            "SELECT 1 FROM rift_instances r WHERE r.status IN('entered','running') "
            "AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(r.members) member "
            "WHERE member::bigint=ANY(%s)) LIMIT 1",
            (list(identities),),
        ).fetchone()
        dungeon = db.execute(
            "SELECT 1 FROM dungeon_instance_members WHERE character_id=ANY(%s) "
            "AND status='active' LIMIT 1",
            (list(identities),),
        ).fetchone()
    accounts = sorted({row["account_id"] for row in owners})
    pending = delivery.pending_snapshot(accounts)
    current = delivery.pending(account_id, generation, character_id)
    stale_scene = any(
        row["id"] == character_id
        and (row["map_id"], row["instance_id"])
        != (live[1]["map_id"], live[1].get("instance_id", 0))
        for row in owners
    )
    if not (retained or dungeon or pending or stale_scene):
        return False, None
    with ExitStack() as barriers:
        for account in accounts:
            barriers.enter_context(positions.account_barrier(account))
        requester = Session(
            account_id,
            character_id,
            generation,
            live[1]["map_id"],
            live[1].get("instance_id", 0),
        )
        if current is not None:
            caller_rows = tuple(row for row in owners if row["id"] == character_id)
            caller_proof = capture(
                requester,
                caller_rows,
                identities,
                world,
                positions,
                source,
                options["source_allowed"],
                allow_world_snapshot=True,
            )
            resumed = _resume(
                store,
                (party, owners, slots, identities, selected, source),
                caller_proof,
                current,
                options,
            )
            if resumed is not None:
                delivery.queue(resumed["transport_members"], resumed["destination"])
                positions.release_committed_transition(
                    account_id,
                    generation,
                    character_id,
                    dict(zip(_FIELDS, caller_proof.owner_positions[0][1:])),
                    resumed["destination"],
                )
                return True, resumed
        proof = capture(
            requester,
            owners,
            identities,
            world,
            positions,
            source,
            options["source_allowed"],
        )
        if combat_registry is None:
            recovery_context = nullcontext(None)
        else:
            from wakfu_server.combat_entry_recovery import prepare

            recovery_context = prepare(
                store,
                combat_registry,
                proof,
                groups=groups,
                checkpoint_writer=checkpoint_writer,
            )
        with recovery_context as combat:
            recovery = ExteriorEntryRecovery(
                store, proof, party, slots, selected, source, combat
            )
            result = rift_entry_adapter.enter(
                store,
                account_id,
                generation,
                character_id,
                source["map_id"],
                body,
                allowed_accounts=set(accounts),
                recovery=recovery,
                **options
            )
            if result is None:
                raise ValueError("Native exterior recovery lost its portal")
            if combat is not None:
                combat.retire()
                result["recovered_fight_id"] = combat.shared.fight.id
            delivery.supersede_recovered_destinations(proof, recovery.retired_instances)
            delivery.queue(result["members"], result["destination"])
            for owner in proof.owners:
                point = next(
                    row for row in proof.owner_positions if row[0] == owner.character_id
                )
                positions.release_committed_transition(
                    owner.account_id,
                    owner.generation,
                    owner.character_id,
                    dict(zip(_FIELDS, point[1:])),
                    result["destination"],
                )
            return True, result


def matches_loaded_source(
    store, world, positions, account_id, generation, character_id, body
):
    """Recognize a real loaded exterior request before inspecting obsolete local FSMs."""
    from wakfu_server import rift_entry_adapter

    live = world.live_identity(character_id=character_id)
    if live is None or live[0] != generation or live[1]["account_id"] != account_id:
        return False
    key = (account_id, generation, character_id)
    with positions.lock:
        entry = positions.entries.get(key)
        current = None if entry is None else dict(entry["current"])
    if (
        current is None
        or not positions.lease_active(*key)
        or any(current[field] != live[1][field] for field in _FIELDS[:-1])
    ):
        return False
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='rift_catalog'"
        ).fetchone()
    return (
        row is not None
        and rift_entry_adapter.resolve_portal(row["value"], current["map_id"], body)
        is not None
    )
