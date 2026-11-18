"""Native planting occupations, own resource snapshots and explicit local timing.

Seed requirement/surface authorization come from installed data and caller.
Duration comes from PostgreSQL local policy, not an official duration formula.
"""

import struct
import threading
import uuid
from psycopg.types.json import Jsonb
import secrets
from . import planting
from .inventory_items import _lease


class Plantings:
    def __init__(
        self,
        store,
        *,
        open_test_policy=False,
        growth_seconds=30,
        location_context=None,
    ):
        self.store = store
        self.location_context = location_context
        self.open_test_policy = bool(open_test_policy)
        self.growth_seconds = growth_seconds
        self.pending = {}
        self.cells = {}
        self.lock = threading.RLock()
        # Growth owns durable resource rows, not socket occupation dictionaries.
        # Its SQL work must not delay movement cancelling an empty occupation.
        self.growth_lock = threading.Lock()
        self.publisher_lock = threading.Lock()
        if type(growth_seconds) not in (int, float) or growth_seconds <= 0:
            raise ValueError("Invalid local planting growth delay")

    def _begin_prepared(self, account, generation, character, prepared):
        with self.lock:
            current = prepared["character"]
            cid = current["id"]
            old = self.pending.get(cid)
            if old and old["generation"] != generation:
                self.cancel(cid, old["generation"], _skip_intents=True)
            request = prepared["request"]
            key = (
                current["map_id"],
                current["instance_id"],
                request["x"],
                request["y"],
            )
            if cid in self.pending or key in self.cells:
                raise ValueError("Planting occupation/cell busy")
            with self.store.connection() as db:
                if db.execute(
                    "SELECT 1 FROM planted_resources WHERE map_id=%s AND instance_id=%s AND x=%s AND y=%s",
                    key,
                ).fetchone():
                    raise ValueError("Owned resource already occupies this cell")
                for row in db.execute(
                    "SELECT resource FROM planting_growth_outbox WHERE published=FALSE"
                ):
                    resource = row["resource"]
                    if (
                        resource["map_id"],
                        resource["instance_id"],
                        resource["x"],
                        resource["y"],
                    ) == key:
                        raise ValueError("Growth publication still reserves this cell")
            if 1 not in prepared["definition"]["stages"]:
                raise ValueError("Native resource has no initial planting stage")
            with self.store.connection() as db:
                policy = db.execute(
                    "SELECT value FROM settings WHERE name='planting_duration_ms'"
                ).fetchone()
            duration = None if policy is None else policy["value"]
            if type(duration) is not int or not 1 <= duration <= 300000:
                raise ValueError("Invalid PostgreSQL planting duration")
            # Freeze the server-owned context before accepting the occupation.
            # The client result never supplies a probability or a random draw.
            from .planting_probability import succeeds

            probability = prepared["probability"]
            succeeds(probability, 0.0)
            if duration != prepared["duration_ms"]:
                raise ValueError("Planting duration changed during preparation")
            from wakfu_server.profession_consumable_modifiers import (
                modifiers,
                duration_ms,
            )
            from wakfu_server.native_world_context import is_battleground

            with self.store.connection() as db:
                speed = modifiers(
                    self.store,
                    db,
                    cid,
                    prepared["seed"]["profession_id"],
                    generation=generation,
                    is_battleground=is_battleground(current["map_id"]),
                )["plant_speed"]
            duration = duration_ms(duration, speed)
            ticket = dict(
                prepared=prepared,
                account=account,
                generation=generation,
                started=self.store.clock(),
                token=uuid.uuid4().hex,
                cell=key,
                probability=probability,
                duration_ms=duration,
            )
            self.pending[cid] = ticket
            self.cells[key] = cid
            # Native aNq:5 AnimMetier-PlanterBouture-Debut,47 AnimReproduction-Debut.
            animation = 47 if prepared["definition"]["monster_resource"] else 5
            return planting.start_packet(
                mun=1,
                hvY=2,
                actor_id=cid,
                profession_id=prepared["seed"]["profession_id"],
                duration=duration,
                egY=animation,
                x=request["x"],
                y=request["y"],
            )

    def begin_prepared(
        self, account, generation, character, body, prepared, authorize_cell, *, db=None
    ):
        """Accept service computation only after fresh world ownership checks."""
        from contextlib import nullcontext
        from .profession_store import stored_level

        request = planting.decode(body)
        if not isinstance(prepared, dict) or request != prepared.get("request"):
            raise ValueError("Planting prepared request differs")
        origin = prepared.get("character", {})
        if any(
            origin.get(key) != character.get(key)
            for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Planting origin changed during preparation")
        seed = planting.SEEDS.get(prepared.get("seed", {}).get("item_reference"))
        if seed is None or seed != prepared["seed"]:
            raise ValueError("Planting prepared seed differs from native catalog")
        definition = planting.RESOURCES.get(seed["resource_reference"])
        if definition is None or definition != prepared.get("definition"):
            raise ValueError("Planting prepared resource differs from native catalog")
        with self.lock, (
            self.store.connection() if db is None else nullcontext(db)
        ) as current_db:
            _lease(self.store, current_db, account, generation, character["id"])
            item = current_db.execute(
                "SELECT reference,quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
                (request["item_uid"], character["id"]),
            ).fetchone()
            if (
                item is None
                or item["reference"] != seed["item_reference"]
                or item["quantity"] < 1
            ):
                raise ValueError("Seed no longer owned")
            from wakfu_server.incarnam_planting import authorize_if_tutorial

            authorize_if_tutorial(current_db, character, seed, definition)
            level = stored_level(current_db, account, seed["profession_id"])
            if level is None or (
                not self.open_test_policy and level < seed["minimum_level"]
            ):
                raise ValueError("Profession unlearned or below seed requirement")
            z = authorize_cell(character, request, seed, definition)
            if type(z) is not int or z != prepared.get("z"):
                raise ValueError("Planting prepared surface changed")
            return self._begin_prepared(account, generation, character, prepared)

    def cancel(self, character_id, generation=None, *, _skip_intents=False):
        intents = getattr(self, "ecology_intents", None)
        if intents is not None and not _skip_intents:
            intents.cancel(character_id, generation)
        with self.lock:
            ticket = self.pending.get(character_id)
            if ticket is None or (
                generation is not None and ticket["generation"] != generation
            ):
                return False
            self.pending.pop(character_id)
            self.cells.pop(ticket["cell"], None)
            return True

    def complete(self, account, generation, character, body):
        if len(body) != 3:
            raise ValueError("Invalid planting occupation result")
        result, kind = struct.unpack(">Bh", body)
        if kind != 2 or result not in (2, 3):
            raise ValueError("Not a native planting occupation result")
        with self.lock:
            cid = character["id"]
            ticket = self.pending.get(cid)
            if ticket is None:
                return dict(applied=False, packets=[])
            if (account, generation) != (ticket["account"], ticket["generation"]):
                raise ValueError("Foreign planting occupation")
            if result == 3:
                self.cancel(cid, generation)
                return dict(applied=False, packets=[])
            if (
                self.store.clock() - ticket["started"] + 0.05
                < ticket["duration_ms"] / 1000
            ):
                raise ValueError("Planting completed before native occupation duration")
            finished = planting.complete(
                self.store,
                account,
                generation,
                ticket["prepared"],
                operation_id=ticket["token"],
                stage=1,
                creation_time=int(self.store.clock() * 1000),
                result_prefix=(cid, ticket["prepared"]["request"]["action_id"]),
                probability=ticket["probability"],
                location_context=self.location_context,
            )
            self.cancel(cid, generation)
            finished["applied"] = not finished["duplicate"]
            return finished

    def snapshots(self, map_id, instance_id, *, position=None, chunks=None):
        """Replay native resource appearances only into loaded nearby partitions.

        Explicit chunks follow the same accepted animation checkpoints as
        native interactive hydration. Position still binds the owning scene;
        it must not narrow those checkpoints to the immediate path endpoint.
        Omitting both selectors retains the complete-map API for offline callers.
        Presentation filtering does not change persisted resources or growth.
        """
        from .world_scene_sync import chunk, neighborhood

        visible_chunks = None
        if position is not None:
            if (
                position["map_id"] != map_id
                or position.get("instance_id", 0) != instance_id
            ):
                raise ValueError("Resource snapshot position belongs to another scene")
            visible_chunks = neighborhood(chunk(position))
        if chunks is not None:
            if (
                type(map_id) is not int
                or not 0 < map_id < 1 << 31
                or type(instance_id) is not int
                or not 0 <= instance_id < 1 << 63
            ):
                raise ValueError("Resource snapshot chunks belong to an invalid scene")
            if not isinstance(chunks, (tuple, list, set, frozenset)) or any(
                not isinstance(selected, tuple)
                or len(selected) != 2
                or any(type(axis) is not int for axis in selected)
                for selected in chunks
            ):
                raise ValueError(
                    "Resource snapshot chunks require native integer partition pairs"
                )
            visible_chunks = frozenset(chunks)
        if visible_chunks is not None and not visible_chunks:
            return []
        # Select only requested partitions before transferring rows from SQL.
        # Rust still validates/filter-encodes the whole compact batch once.
        predicate = ""
        parameters = [map_id, instance_id]
        if visible_chunks is not None:
            bounds = []
            for cx, cy in sorted(visible_chunks):
                bounds.append("(x >= %s AND x < %s AND y >= %s AND y < %s)")
                parameters.extend((cx * 18, cx * 18 + 18, cy * 18, cy * 18 + 18))
            predicate = " AND (" + " OR ".join(bounds) + ")"
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT resource_reference,x,y,z,stage FROM planted_resources "
                    "WHERE map_id=%s AND instance_id=%s"
                    + predicate
                    + " ORDER BY resource_uid",
                    tuple(parameters),
                )
            )
        from .scene_wire_native import resource_packets

        return resource_packets(rows, visible_chunks)

    def apply_growth_candidates(
        self,
        candidates,
        *,
        prepared_members=None,
        random_draw=lambda: secrets.randbelow(1 << 53) / (1 << 53),
    ):
        """Apply bounded prepared candidates after authoritative row comparison."""
        applied = []
        capacity_skipped = []
        with self.growth_lock, self.store.connection() as db:
            for resource, definition, transition in candidates:
                from .resource_domains import is_fixed_resource

                if is_fixed_resource(resource["resource_reference"]):
                    continue
                if definition["monster_resource"]:
                    map_id, instance_id = resource["map_id"], resource["instance_id"]
                    db.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                        (f"monster-population:{map_id}:{instance_id}",),
                    )
                current = db.execute(
                    "SELECT * FROM planted_resources WHERE resource_uid=%s FOR UPDATE",
                    (resource["resource_uid"],),
                ).fetchone()
                if current is None or dict(current) != resource:
                    continue
                # Every growth producer, including delayed Ecology proposals,
                # shares this authority after the live resource row is locked.
                from wakfu_server import dungeon_resource_obstacles

                if dungeon_resource_obstacles.owns(db, resource["resource_uid"]):
                    continue
                from wakfu_server import quest_resource_slots

                if quest_resource_slots.owns(db, resource["resource_uid"]):
                    continue
                if db.execute(
                    "SELECT 1 FROM resource_harvest_occupations "
                    "WHERE resource_uid=%s AND expires_at>%s",
                    (resource["resource_uid"], self.store.now()),
                ).fetchone():
                    continue
                if definition["monster_resource"]:
                    # Serialize every producer against the same map population
                    # budget. The resource row and reservation are committed in
                    # this transaction while the advisory lock remains held.
                    from .monster_population_capacity import has_capacity, snapshot
                    from .monster_reproduction import validate_policy

                    setting = db.execute(
                        "SELECT value FROM settings WHERE name='monster_reproduction'"
                    ).fetchone()
                    if setting is None:
                        raise ValueError("Monster population policy is missing")
                    policy = validate_policy(setting["value"])
                    counts = snapshot(db, map_id, instance_id)
                    if not has_capacity(
                        counts,
                        add_members=1,
                        add_groups=1,
                        max_members=policy["max_zone_members"],
                        max_groups=policy["max_zone_groups"],
                    ):
                        capacity_skipped.append(resource["resource_uid"])
                        continue
                    member = (prepared_members or {}).get(resource["resource_uid"])
                    if member is None:
                        raise ValueError("Prepared native monster member is required")
                    from .npc_actor_identity import allocate_block

                    member = dict(member, id=-allocate_block(db, 1))
                    group_id = -member["id"]
                    group = dict(
                        key=[resource["map_id"], resource["instance_id"], group_id],
                        members=[member],
                    )
                    db.execute(
                        "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,%s) ON CONFLICT(resource_uid) DO NOTHING",
                        (
                            resource["resource_uid"],
                            Jsonb(resource),
                            Jsonb(group),
                        ),
                    )
                    db.execute(
                        "DELETE FROM planted_resources WHERE resource_uid=%s",
                        (resource["resource_uid"],),
                    )
                    applied.append(resource["resource_uid"])
                elif transition is not None:
                    policy = db.execute(
                        "SELECT to_stage,delay_ms,probability FROM resource_growth_transitions "
                        "WHERE resource_reference=%s AND from_stage=%s FOR SHARE",
                        (resource["resource_reference"], resource["stage"]),
                    ).fetchone()
                    if (
                        policy is None
                        or (
                            policy["to_stage"],
                            policy["delay_ms"],
                            policy["probability"],
                        )
                        != transition
                    ):
                        continue
                    next_stage, delay_ms, probability = transition
                    if probability < 1:
                        from .planting_probability import succeeds

                        draw = random_draw()
                        accepted = succeeds(probability, draw)
                        inserted = db.execute(
                            "INSERT INTO resource_growth_decisions VALUES(%s,%s,%s,%s,%s,%s) "
                            "ON CONFLICT DO NOTHING RETURNING resource_uid",
                            (
                                resource["resource_uid"],
                                resource["stage"],
                                next_stage,
                                probability,
                                draw,
                                accepted,
                            ),
                        ).fetchone()
                        if inserted is None or not accepted:
                            continue
                    entered_at = resource["creation_time"] + delay_ms
                    db.execute(
                        "UPDATE planted_resources SET stage=%s,creation_time=%s WHERE resource_uid=%s",
                        (next_stage, entered_at, resource["resource_uid"]),
                    )
                    db.execute(
                        "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,NULL) "
                        "ON CONFLICT(resource_uid) DO UPDATE SET resource=EXCLUDED.resource,group_payload=NULL,published=FALSE",
                        (
                            resource["resource_uid"],
                            Jsonb(
                                dict(
                                    resource, stage=next_stage, creation_time=entered_at
                                )
                            ),
                        ),
                    )
                    applied.append(resource["resource_uid"])
        return {"applied": applied, "capacity_skipped": capacity_skipped}

    def publish_growth(
        self, groups, *, publish, resource_uid=None, resource_uids=None, limit=None
    ):
        from .combat_monster_world import spawn_group

        if resource_uid is not None and resource_uids is not None:
            raise ValueError("Choose one growth resource filter")
        if resource_uids is not None:
            resource_uids = tuple(dict.fromkeys(resource_uids))
            if not resource_uids:
                return []
        published = []
        with self.publisher_lock:
            with self.store.connection() as db:
                rows = [
                    dict(row)
                    for row in db.execute(
                        "SELECT * FROM planting_growth_outbox WHERE published=FALSE "
                        + ("AND resource_uid=%s " if resource_uid is not None else "")
                        + (
                            "AND resource_uid=ANY(%s) "
                            if resource_uids is not None
                            else ""
                        )
                        + "ORDER BY resource_uid"
                        + (" LIMIT %s" if limit is not None else ""),
                        (() if resource_uid is None else (resource_uid,))
                        + (() if resource_uids is None else (list(resource_uids),))
                        + (() if limit is None else (limit,)),
                    )
                ]
            for row in rows:
                resource = row["resource"]
                group = row["group_payload"] if row["group_payload"] else None
                ecology = None
                if group:
                    from .monster_birth_ecology import activate

                    with self.store.connection() as db:
                        ecology = activate(db, groups, row["resource_uid"])
                    packets = [state_packet(resource, 0)]
                    if ecology["status"] == "available":
                        packets.append(
                            (
                                12608,
                                spawn_group(
                                    ecology["members"], group_id=group["key"][2]
                                ),
                            )
                        )
                else:
                    packets = [
                        (
                            planting.resource_packet(resource)
                            if (
                                resource.get("mining_spawn")
                                or resource.get("fishing_spawn")
                                or resource.get("flora_spawn")
                                or resource.get("quest_resource_spawn")
                            )
                            else state_packet(resource, resource["stage"])
                        )
                    ]
                delivery = dict(
                    map_id=resource["map_id"],
                    instance_id=resource["instance_id"],
                    resource_uid=resource["resource_uid"],
                    packets=packets,
                )
                if ecology is not None:
                    delivery["ecology"] = ecology
                # The durable event remains pending if world delivery fails.
                # A crash after delivery can replay the exact state packet.
                publish(delivery)
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE planting_growth_outbox SET published=TRUE WHERE resource_uid=%s "
                        "AND resource=%s AND group_payload IS NOT DISTINCT FROM %s",
                        (
                            row["resource_uid"],
                            Jsonb(resource),
                            Jsonb(group) if group else None,
                        ),
                    )
                published.append(delivery)
        return published


def state_packet(resource, stage):
    # cAx12782 -> cFJ updates an existing resource stage. Stage0 disables
    # harvesting; this packet alone does not prove spatial actor removal.
    # The separate Fg.aAw callback can mark temporary actors for removal,
    # but its connection to this state update is not established.
    return 12782, struct.pack(
        ">iihhqi",
        resource["x"],
        resource["y"],
        resource["z"],
        stage,
        # cFJ stores kEB as ownerAccountId, which cWn compares with the
        # player's account. Public resources remain public after growth.
        0,
        0,
    )
