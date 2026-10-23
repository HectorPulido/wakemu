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
        probability_context=None,
        location_context=None,
    ):
        self.store = store
        self.location_context = location_context
        if probability_context is not None and not callable(probability_context):
            raise ValueError("Invalid authoritative planting probability resolver")
        self.probability_context = probability_context
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

    def begin(
        self, account, generation, character, body, authorize_cell, *, _prepared=None
    ):
        with self.lock:
            prepared = (
                _prepared
                if _prepared is not None
                else planting.prepare(
                    self.store,
                    account,
                    generation,
                    character,
                    body,
                    authorize_cell=authorize_cell,
                    open_test_policy=self.open_test_policy,
                    location_context=self.location_context,
                )
            )
            current = prepared["character"]
            cid = current["id"]
            old = self.pending.get(cid)
            if old and old["generation"] != generation:
                self.cancel(cid, old["generation"], _skip_intents=_prepared is not None)
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
            probability = None
            if _prepared is not None:
                from .planting_probability import succeeds

                probability = _prepared["probability"]
                succeeds(probability, 0.0)
                if duration != _prepared["duration_ms"]:
                    raise ValueError("Planting duration changed during preparation")
            elif self.probability_context is not None:
                from .planting_probability import succeeds

                probability = self.probability_context(prepared)
                succeeds(probability, 0.0)  # Validate without drawing or mutating.
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
            level = stored_level(current_db, account, seed["profession_id"])
            if level is None or (
                not self.open_test_policy and level < seed["minimum_level"]
            ):
                raise ValueError("Profession unlearned or below seed requirement")
            z = authorize_cell(character, request, seed, definition)
            if type(z) is not int or z != prepared.get("z"):
                raise ValueError("Planting prepared surface changed")
            return self.begin(
                account, generation, character, body, authorize_cell, _prepared=prepared
            )

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

    def snapshots(self, map_id, instance_id, *, position=None):
        """Replay native resource appearances only into loaded nearby partitions.

        Omitting position retains the complete-map API for offline callers.
        Presentation filtering does not change persisted resources or growth.
        """
        visible_chunks = None
        if position is not None:
            from .world_scene_sync import chunk, neighborhood

            if (
                position["map_id"] != map_id
                or position.get("instance_id", 0) != instance_id
            ):
                raise ValueError("Resource snapshot position belongs to another scene")
            visible_chunks = neighborhood(chunk(position))
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT * FROM planted_resources WHERE map_id=%s AND instance_id=%s ORDER BY resource_uid",
                    (map_id, instance_id),
                )
            )
        return [
            planting.resource_packet(dict(row))
            for row in rows
            if visible_chunks is None or chunk(dict(row)) in visible_chunks
        ]

    def mature(
        self,
        groups,
        *,
        publish,
        authorize_spawn=lambda resource: True,
        random_draw=lambda: secrets.randbelow(1 << 53) / (1 << 53),
    ):
        """Database-owned flora transitions and existing monster seed timing.

        SQL outbox survives Redis outages. Caller excludes live players/objects
        and group occupancy before spawn. No lease belongs to a planted world
        resource: it continues growing after its planter logs out.
        """
        from .mining_veins import refill

        # Minerals retain fixed slots and use their own SQL respawn deadlines.
        # Their queued full appearances share only the durable delivery outbox.
        with self.publisher_lock:
            refill(self.store)
            from .fishing_spots import refill as refill_fishing

            refill_fishing(self.store)
        due = int((self.store.clock() - self.growth_seconds) * 1000)
        now_ms = int(self.store.clock() * 1000)
        monster_references = [
            ref
            for ref, definition in planting.RESOURCES.items()
            if definition["monster_resource"]
        ]
        with self.store.connection() as db:
            resources = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM planted_resources WHERE stage=1 AND creation_time<=%s "
                    "AND resource_reference=ANY(%s)",
                    (due, monster_references),
                )
            ]
            flora = list(
                db.execute(
                    "SELECT p.*,t.to_stage,t.delay_ms,t.probability FROM planted_resources p "
                    "JOIN resource_growth_transitions t ON t.resource_reference=p.resource_reference "
                    "AND t.from_stage=p.stage WHERE p.creation_time+t.delay_ms<=%s "
                    "AND NOT EXISTS (SELECT 1 FROM environmental_owned_resources e "
                    "WHERE e.resource_uid=p.resource_uid AND e.retired_at_ms IS NULL) "
                    "AND NOT EXISTS (SELECT 1 FROM resource_growth_decisions d "
                    "WHERE d.resource_uid=p.resource_uid AND d.from_stage=p.stage)",
                    (now_ms,),
                )
            )
        candidates = []
        for resource in resources:
            definition = planting.RESOURCES[resource["resource_reference"]]
            if definition["monster_resource"] and not authorize_spawn(resource):
                continue
            candidates.append((resource, definition, None))
        for row in flora:
            from .resource_domains import is_fixed_resource

            if is_fixed_resource(row["resource_reference"]):
                continue
            resource = {
                key: value
                for key, value in row.items()
                if key not in ("to_stage", "delay_ms", "probability")
            }
            definition = planting.RESOURCES[resource["resource_reference"]]
            transition = (row["to_stage"], row["delay_ms"], row["probability"])
            if (
                definition["monster_resource"]
                or row["to_stage"] not in definition["stages"]
            ):
                raise ValueError(
                    "Growth transition is absent from native flora definition"
                )
            candidates.append((resource, definition, transition))
        self.apply_growth_candidates(candidates, random_draw=random_draw)
        return self.publish_growth(groups, publish=publish)

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
                        member = monster_growth_member(resource, definition)
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
                        planting.resource_packet(resource)
                        if (
                            resource.get("mining_spawn")
                            or resource.get("fishing_spawn")
                            or resource.get("flora_spawn")
                        )
                        else state_packet(resource, resource["stage"])
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


def monster_growth_member(resource, definition, *, decision_seed=None):
    """Choose uniformly among this seed's native initial family alternatives.

    Selection happens once before the durable growth payload is recorded;
    publication retries reuse that payload and never draw a new identity/form.
    A decision seed preserves the preference across periodic batch reshuffling.
    The real actor identity is allocated transactionally when growth commits.
    """
    from .monsters import REFERENCES, owned_instance
    from .monster_collect import _actions

    seed_refs = {
        s["item_reference"]
        for s in planting.SEEDS.values()
        if s["resource_reference"] == definition["resource_reference"]
    }
    eligible = []
    fallback = []
    for ref, template in REFERENCES.items():
        if template["family_id"] not in definition["monster_family_ids"]:
            continue
        try:
            member = owned_instance(
                ref,
                template["min_level"],
                -1,
                map_id=resource["map_id"],
                x=resource["x"],
                y=resource["y"],
                z=resource["z"],
            )
        except ValueError:
            continue
        key = (template["min_level"], ref)
        fallback.append((key, ref))
        if any(
            raw["csP"] in seed_refs
            and raw["clT"].strip() in ("", 'not IsDead("target")')
            for (m, a), raw in _actions().items()
            if m == ref
        ):
            eligible.append((key, ref))
    choices = eligible or fallback
    if not choices:
        raise ValueError(
            "Native seed family has no valid local monster growth template"
        )
    from .monster_family_stages import initial_candidates

    allowed = {ref for _, ref in choices}
    candidates = [
        candidate
        for family_id in definition["monster_family_ids"]
        for candidate in initial_candidates(family_id, eligible_references=allowed)
    ]
    if not candidates:
        raise ValueError("Native seed family has no eligible initial monster form")
    if decision_seed is None:
        ref = secrets.choice(candidates)["reference"]
        group_id = secrets.randbits(62) + 1
    else:
        import hashlib

        def rank(label):
            return hashlib.sha256(f"{decision_seed}:{label}".encode()).digest()

        ref = min(candidates, key=lambda c: rank(f"variant:{c['reference']}"))[
            "reference"
        ]
        group_id = (
            int.from_bytes(rank("preview_identity")[:8], "big") % ((1 << 62) - 1)
        ) + 1
    template = REFERENCES[ref]
    member = owned_instance(
        ref,
        template["min_level"],
        -group_id,
        map_id=resource["map_id"],
        x=resource["x"],
        y=resource["y"],
        z=resource["z"],
        instance_id=resource["instance_id"],
    )
    return member
