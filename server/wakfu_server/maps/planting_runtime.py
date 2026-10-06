"""Native planting occupations, own resource snapshots and explicit local timing.

Seed requirement/surface authorization come from installed data and caller.
3000ms is the local server policy, not an official profession-duration formula.
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
        self, store, *, duration_ms=3000, open_test_policy=False, growth_seconds=30
    ):
        if type(duration_ms) is not int or not 0 < duration_ms < 2**31:
            raise ValueError("Invalid local planting duration")
        self.store = store
        self.duration = duration_ms
        self.open_test_policy = bool(open_test_policy)
        self.growth_seconds = growth_seconds
        self.pending = {}
        self.cells = {}
        self.lock = threading.RLock()
        self.publisher_lock = threading.Lock()
        if type(growth_seconds) not in (int, float) or growth_seconds <= 0:
            raise ValueError("Invalid local planting growth delay")

    def begin(self, account, generation, character, body, authorize_cell):
        with self.lock:
            prepared = planting.prepare(
                self.store,
                account,
                generation,
                character,
                body,
                authorize_cell=authorize_cell,
                open_test_policy=self.open_test_policy,
            )
            current = prepared["character"]
            cid = current["id"]
            old = self.pending.get(cid)
            if old and old["generation"] != generation:
                self.cancel(cid, old["generation"])
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
            ticket = dict(
                prepared=prepared,
                account=account,
                generation=generation,
                started=self.store.clock(),
                token=uuid.uuid4().hex,
                cell=key,
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
                duration=self.duration,
                egY=animation,
                x=request["x"],
                y=request["y"],
            )

    def cancel(self, character_id, generation=None):
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
            if self.store.clock() - ticket["started"] + 0.05 < self.duration / 1000:
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
            )
            self.cancel(cid, generation)
            finished["applied"] = not finished["duplicate"]
            return finished

    def snapshots(self, map_id, instance_id):
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT * FROM planted_resources WHERE map_id=%s AND instance_id=%s ORDER BY resource_uid",
                    (map_id, instance_id),
                )
            )
        return [planting.resource_packet(dict(row)) for row in rows]

    def mature(self, groups, *, publish, authorize_spawn=lambda resource: True):
        """Local30s growth policy; returns map-scoped broadcasts for main writer.

        SQL outbox survives Redis outages. Caller excludes live players/objects
        and group occupancy before spawn. No lease belongs to a planted world
        resource: it continues growing after its planter logs out.
        """
        due = int((self.store.clock() - self.growth_seconds) * 1000)
        with self.store.connection() as db:
            resources = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM planted_resources WHERE stage=1 AND creation_time<=%s",
                    (due,),
                )
            ]
        candidates = []
        for resource in resources:
            definition = planting.RESOURCES[resource["resource_reference"]]
            if definition["monster_resource"] and not authorize_spawn(resource):
                continue
            candidates.append((resource, definition))
        with self.lock, self.store.connection() as db:
            for resource, definition in candidates:
                current = db.execute(
                    "SELECT * FROM planted_resources WHERE resource_uid=%s FOR UPDATE",
                    (resource["resource_uid"],),
                ).fetchone()
                if current is None or dict(current) != resource:
                    continue
                if definition["monster_resource"]:
                    member = monster_growth_member(resource, definition)
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
                elif 2 in definition["stages"]:
                    db.execute(
                        "UPDATE planted_resources SET stage=2 WHERE resource_uid=%s",
                        (resource["resource_uid"],),
                    )
                    db.execute(
                        "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,NULL) ON CONFLICT(resource_uid) DO NOTHING",
                        (resource["resource_uid"], Jsonb(dict(resource, stage=2))),
                    )
        return self.publish_growth(groups, publish=publish)

    def publish_growth(self, groups, *, publish):
        from .combat_monster_world import spawn_group

        published = []
        with self.publisher_lock:
            with self.store.connection() as db:
                rows = [
                    dict(row)
                    for row in db.execute(
                        "SELECT * FROM planting_growth_outbox WHERE published=FALSE ORDER BY resource_uid"
                    )
                ]
            for row in rows:
                resource = row["resource"]
                group = row["group_payload"] if row["group_payload"] else None
                if group:
                    groups.register(*group["key"], group["members"])
                    packets = [
                        state_packet(resource, 0),
                        (
                            12608,
                            spawn_group(group["members"], group_id=group["key"][2]),
                        ),
                    ]
                else:
                    packets = [state_packet(resource, resource["stage"])]
                delivery = dict(
                    map_id=resource["map_id"],
                    instance_id=resource["instance_id"],
                    resource_uid=resource["resource_uid"],
                    packets=packets,
                )
                # The durable event remains pending if world delivery fails.
                # A crash after delivery can replay the exact state packet.
                publish(delivery)
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE planting_growth_outbox SET published=TRUE WHERE resource_uid=%s",
                        (row["resource_uid"],),
                    )
                published.append(delivery)
        return published


def state_packet(resource, stage):
    # cAx12782 -> cFJ. stage0 plays native disappearance; temporary resources
    # (13135 field6=false) mark kED on Fg.aAw then bOw/bOv removes them.
    return 12782, struct.pack(
        ">iihhqi",
        resource["x"],
        resource["y"],
        resource["z"],
        stage,
        resource["creation_time"],
        0,
    )


def monster_growth_member(resource, definition):
    """Explicit local population selection: minimum native level, then reference.

    Prefer family members whose native collection action returns this seed, so
    tutorial creatures without harvesting do not break the farming loop. This
    is a local rule, not the official species distribution or maturity timing.
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
    ref = min(choices)[1]
    template = REFERENCES[ref]
    group_id = secrets.randbits(62) + 1
    member = owned_instance(
        ref,
        template["min_level"],
        -group_id,
        map_id=resource["map_id"],
        x=resource["x"],
        y=resource["y"],
        z=resource["z"],
    )
    member["instance_id"] = resource["instance_id"]
    return member
