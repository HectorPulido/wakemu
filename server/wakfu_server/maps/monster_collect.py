"""Native monster harvesting; no invented profession XP or server loot tables.

Callers resolve a live registry monster and native reachability before start.
Yield/cooldown are explicit local policies, not undocumented official rates.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import struct
import uuid
import threading
import math
from datetime import timedelta
from functools import wraps, lru_cache


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self.lock:
            return method(self, *args, **kwargs)

    return call


from .paths import DATA_ROOT
from .wire import proto_fields
from .inventory_items import _lease, insertion


class Regenerating(ValueError):
    def __init__(self, monster_id, action_id):
        super().__init__("Monster harvest resource is regenerating")
        self.monster_id = monster_id
        self.action_id = action_id


def availability_packet(monster_id, action_id, enabled):
    """cyg13421 updates the target NPC's contextual action availability."""
    if (
        type(monster_id) is not int
        or not -(1 << 63) <= monster_id < 0
        or type(action_id) is not int
        or not 0 < action_id < (1 << 31)
        or type(enabled) is not bool
    ):
        raise ValueError("Invalid monster resource availability")
    return 13421, struct.pack(">qiB", monster_id, action_id, int(enabled))


def policy(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='monster_harvest'"
    ).fetchone()
    value = None if row is None else row["value"]
    if (
        not isinstance(value, dict)
        or set(value) != {"quantity", "cooldown_seconds"}
        or type(value["quantity"]) is not int
        or not 1 <= value["quantity"] <= 32767
        or type(value["cooldown_seconds"]) not in (int, float)
        or not math.isfinite(value["cooldown_seconds"])
        or not 0 < value["cooldown_seconds"] <= 86400
    ):
        raise ValueError("Invalid database monster harvest policy")
    return value


def available(db, store, monster, action_id):
    key = (monster["map_id"], monster["instance_id"], monster["id"], action_id)
    lock_key = "harvest:" + ":".join(map(str, key))
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
    from .npc_actor_identity_repair import identity_lineage

    lineage = identity_lineage(db, *key[:2], key[2])
    last = db.execute(
        "SELECT MAX(regenerates_until) AS last FROM monster_harvest_receipts "
        "WHERE map_id=%s AND instance_id=%s AND monster_id=ANY(%s) AND action_id=%s",
        (*key[:2], lineage, key[3]),
    ).fetchone()["last"]
    if last is not None and store.now() < last:
        raise Regenerating(monster["id"], action_id)


def decode_request(body):
    fields = list(proto_fields(body))
    if len(fields) != 2 or {tag for tag, _ in fields} != {8, 16}:
        raise ValueError("Invalid monster harvest protobuf")
    values = dict(fields)
    action = values[8]
    target = values[16]
    if (
        type(action) is not int
        or not 0 < action < 2**31
        or type(target) is not int
        or not 0 < target < 2**64
    ):
        raise ValueError("Invalid monster harvest identities")
    if target >= 2**63:
        target -= 2**64
    if target >= 0:
        raise ValueError("Monster harvest requires a local NPC")
    return dict(action_id=action, monster_id=target)


def decode_result(body):
    if len(body) != 3:
        raise ValueError("Invalid occupation result")
    result, kind = struct.unpack(">Bh", body)
    if kind != 6 or result not in (2, 3):
        raise ValueError("Unsupported monster occupation result")
    return result


@lru_cache(maxsize=1)
def _actions():
    catalog = protocol_catalog.load(DATA_ROOT / "monster-encyclopedia.json")
    return {
        (m["ref"], a["d"]): a for m in catalog["monsters"] for a in m["collect_actions"]
    }


def action(monster_ref, action_id):
    native = _actions().get((monster_ref, action_id))
    if native is None:
        raise ValueError("Action does not belong to this monster")
    native = dict(native)
    return dict(
        action_id=action_id,
        item_ref=native["csP"],
        profession_id=native["ckL"],
        required_level=native["csM"],
        duration_ms=native["getDuration"],
        condition=native["clT"],
        native=native,
    )


def validate_action(rule, monster, *, profession_level):
    if type(profession_level) is not int or profession_level < rule["required_level"]:
        raise ValueError("Profession level insufficient")
    expression = rule["condition"].strip()
    dead = monster["hp"] <= 0
    if expression not in ("", 'IsDead("target")', 'not IsDead("target")'):
        raise ValueError("Native harvest criterion not implemented")
    if (expression == 'IsDead("target")' and not dead) or (
        expression == 'not IsDead("target")' and dead
    ):
        raise ValueError("Native harvest target criterion failed")
    if rule["item_ref"] <= 0 or rule["duration_ms"] < 0:
        raise ValueError("Unsupported native harvest output")


def start_packet(character_id, monster_id, rule):
    # cta.dp -> chT -> blN.jX -> bNZ.a: duration milliseconds, not timestamp.
    return 13597, struct.pack(
        ">Bhqqqi",
        0,
        6,
        character_id,
        rule["duration_ms"],
        monster_id,
        rule["action_id"],
    )


def resolve_target(registry, character, monster_id):
    """Resolve only available own NPCs in the actual map and instance."""
    matches = []
    for group in registry.available(character["map_id"], character["instance_id"]):
        for member in group["members"]:
            if member["id"] == monster_id:
                target = dict(
                    member,
                    map_id=group["key"][0],
                    instance_id=group["key"][1],
                    group_key=group["key"],
                )
                if "hp" not in target:
                    target["hp"] = target["stats"]["HP"]
                matches.append(target)
    if len(matches) != 1:
        raise ValueError("Monster harvest target unavailable or ambiguous")
    return matches[0]


class Harvests:
    """One pending occupation per character/target; grant and receipt commit together."""

    def __init__(self, store):
        self.store = store
        self.pending = {}
        self.targets = {}
        self.lock = threading.RLock()
        self.regenerating = {}
        self.next_regeneration = math.inf

    @_serialized
    def availability_snapshot(self, map_id, instance_id):
        """Restore disabled actions after NPC publication, including reconnect."""
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT COALESCE(a.new_actor_id,r.monster_id) AS monster_id,r.action_id,"
                "MAX(r.regenerates_until) AS regenerates_until FROM monster_harvest_receipts r "
                "LEFT JOIN npc_actor_identity_aliases a ON a.map_id=r.map_id "
                "AND a.instance_id=r.instance_id AND a.old_actor_id=r.monster_id "
                "WHERE r.map_id=%s AND r.instance_id=%s AND r.regenerates_until>%s "
                "GROUP BY COALESCE(a.new_actor_id,r.monster_id),r.action_id",
                (map_id, instance_id, self.store.now()),
            ).fetchall()
        now = self.store.clock()
        packets = []
        for row in rows:
            due = row["regenerates_until"].timestamp()
            if due > now:
                key = (map_id, instance_id, row["monster_id"], row["action_id"])
                self.regenerating[key] = due
                self.next_regeneration = min(self.next_regeneration, due)
                packets.append(availability_packet(key[2], key[3], False))
        return packets

    @_serialized
    def due_availability(self):
        """One global drain; packet traffic only checks the earliest deadline."""
        now = self.store.clock()
        if now < self.next_regeneration:
            return []
        ready = []
        for key, due in list(self.regenerating.items()):
            if due <= now:
                del self.regenerating[key]
                ready.append(
                    (key[0], key[1], availability_packet(key[2], key[3], True))
                )
        self.next_regeneration = min(self.regenerating.values(), default=math.inf)
        return ready

    @_serialized
    def availability_for(self, map_id, instance_id, monster_ids):
        """Reapply cached gates when existing NPC identities reappear."""
        targets = set(monster_ids)
        now = self.store.clock()
        return [
            availability_packet(key[2], key[3], False)
            for key, due in self.regenerating.items()
            if key[:2] == (map_id, instance_id) and key[2] in targets and due > now
        ]

    @_serialized
    def begin(
        self,
        account_id,
        generation,
        character_id,
        body,
        monster,
        *,
        profession_level,
        reachable
    ):
        request = decode_request(body)
        with self.store.connection() as db:
            _lease(self.store, db, account_id, generation, character_id)
            character = self.store.character(account_id, character_id, db)
            configuration = policy(db)
            available(db, self.store, monster, request["action_id"])
        quantity = configuration["quantity"]
        cooldown_seconds = configuration["cooldown_seconds"]
        previous = self.pending.get(character_id)
        if previous is not None and previous["generation"] != generation:
            # The new lease was checked above. An expired/replaced lease cannot
            # retain an occupation or let its finally cancel the new owner.
            self.cancel(character_id, previous["generation"])
        if character_id in self.pending or request["monster_id"] in self.targets:
            raise ValueError("Monster harvest occupation busy")
        if (
            monster["id"] != request["monster_id"]
            or monster["map_id"] != character["map_id"]
            or monster["instance_id"] != character["instance_id"]
        ):
            raise ValueError("Foreign monster harvest target")
        if not reachable:
            raise ValueError("Monster harvest target unreachable")
        if (
            type(quantity) is not int
            or not 1 <= quantity <= 32767
            or cooldown_seconds < 0
        ):
            raise ValueError("Invalid local harvest policy")
        rule = action(monster["ref"], request["action_id"])
        from .inventory_move import STACKS

        stack = STACKS.get(rule["item_ref"])
        if stack is None or quantity > stack["maximum"]:
            raise ValueError("Unknown or exceeded native harvest stack capacity")
        validate_action(rule, monster, profession_level=profession_level)
        ticket = dict(
            token=uuid.uuid4().hex,
            account_id=account_id,
            generation=generation,
            character_id=character_id,
            monster_id=monster["id"],
            rule=rule,
            quantity=quantity,
            started=self.store.clock(),
            cooldown_seconds=cooldown_seconds,
            position=tuple(
                character[k] for k in ("map_id", "instance_id", "x", "y", "z")
            ),
        )
        self.pending[character_id] = ticket
        self.targets[monster["id"]] = character_id
        return start_packet(character_id, monster["id"], rule)

    @_serialized
    def cancel(self, character_id, generation=None):
        ticket = self.pending.get(character_id)
        if ticket is None or (
            generation is not None and ticket["generation"] != generation
        ):
            return False
        self.pending.pop(character_id)
        self.targets.pop(ticket["monster_id"], None)
        return True

    @_serialized
    def complete(
        self, account_id, generation, character_id, body, *, monster, profession_level
    ):
        result = decode_result(body)
        ticket = self.pending.get(character_id)
        if ticket is None:
            return dict(applied=False, packets=[])
        if (ticket["account_id"], ticket["generation"]) != (account_id, generation):
            raise ValueError("Foreign monster harvest occupation")
        if result == 3:
            self.cancel(character_id)
            return dict(applied=False, packets=[])
        if (
            self.store.clock() - ticket["started"] + 0.05
            < ticket["rule"]["duration_ms"] / 1000
        ):
            raise ValueError("Monster harvest completed too early")
        from .inventory_uids import allocate

        with self.store.connection() as db:
            _lease(self.store, db, account_id, generation, character_id)
            character = self.store.character(account_id, character_id, db)
            if (
                tuple(character[k] for k in ("map_id", "instance_id", "x", "y", "z"))
                != ticket["position"]
            ):
                raise ValueError("Monster harvest actor moved")
            if (
                monster["id"] != ticket["monster_id"]
                or monster["map_id"] != character["map_id"]
                or monster["instance_id"] != character["instance_id"]
            ):
                raise ValueError("Monster harvest target changed")
            validate_action(ticket["rule"], monster, profession_level=profession_level)
            if db.execute(
                "SELECT 1 FROM monster_harvest_receipts WHERE token=%s",
                (ticket["token"],),
            ).fetchone():
                self.cancel(character_id)
                return dict(applied=False, packets=[])
            available(db, self.store, monster, ticket["rule"]["action_id"])
            # Base pocket accepts ordinary materials; no bag specialty assumptions.
            base = character["inventory_containers"][0]
            from wakfu_server.inventory_move import STACKS
            from wakfu_server.inventory_elements import masks

            reference = ticket["rule"]["item_ref"]
            quantity = ticket["quantity"]
            stack_rule = STACKS.get(reference)
            if stack_rule is None or quantity > stack_rule["maximum"]:
                raise ValueError("Unsupported native harvest stack quantity")
            existing = next(
                (
                    i
                    for i in character["inventory_items"]
                    if i["container"] == base["uid"]
                    and i["reference"] == reference
                    and stack_rule["minimal_mergeable"]
                    and masks(i) is None
                    and "mount" not in i
                    and i["quantity"] + quantity <= stack_rule["maximum"]
                ),
                None,
            )
            occupied = {
                i["slot"]
                for i in character["inventory_items"]
                if i["container"] == base["uid"]
            }
            slot = next((s for s in range(base["capacity"]) if s not in occupied), None)
            if slot is None and existing is None:
                raise ValueError("Base inventory full")
            uid = existing["uid"] if existing is not None else allocate(db)
            item = dict(
                uid=uid,
                character_id=character_id,
                reference=reference,
                quantity=quantity
                + (existing["quantity"] if existing is not None else 0),
                container=base["uid"],
                slot=existing["slot"] if existing is not None else slot,
            )
            if existing is not None:
                db.execute(
                    "UPDATE inventory_items SET quantity=%s WHERE uid=%s AND character_id=%s",
                    (item["quantity"], uid, character_id),
                )
            else:
                db.execute(
                    "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(%s,%s,%s,%s,%s,%s)",
                    tuple(
                        item[k]
                        for k in (
                            "uid",
                            "character_id",
                            "reference",
                            "quantity",
                            "container",
                            "slot",
                        )
                    ),
                )
            completed_at = self.store.now()
            regenerates_until = completed_at + timedelta(
                seconds=ticket["cooldown_seconds"]
            )
            db.execute(
                "INSERT INTO monster_harvest_receipts(token,character_id,map_id,instance_id,monster_id,action_id,completed_at,item_uid,regenerates_until) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    ticket["token"],
                    character_id,
                    monster["map_id"],
                    monster["instance_id"],
                    monster["id"],
                    ticket["rule"]["action_id"],
                    completed_at,
                    uid,
                    regenerates_until,
                ),
            )
            packet = (
                (12470, struct.pack(">qh", uid, quantity))
                if existing is not None
                else insertion(item, notification=True)
            )
            from .profession_rewards import base_xp
            from .profession_store import award

            progress = award(
                self.store,
                db,
                account_id,
                generation,
                character_id,
                ticket["rule"]["profession_id"],
                base_xp=base_xp(db, "harvest"),
                operation="monster-harvest:" + ticket["token"],
            )
            from .monster_harvest_ecology import change as ecological_harvest

            feedback = ecological_harvest(
                db,
                character_id,
                monster,
                operation="monster-harvest:" + ticket["token"],
            )
        self.cancel(character_id)
        key = (
            monster["map_id"],
            monster["instance_id"],
            monster["id"],
            ticket["rule"]["action_id"],
        )
        due = regenerates_until.timestamp()
        self.regenerating[key] = due
        self.next_regeneration = min(self.next_regeneration, due)
        return dict(
            applied=True,
            item=item,
            packets=[packet, *progress["packets"], *feedback],
            availability=(key[0], key[1], availability_packet(key[2], key[3], False)),
        )
