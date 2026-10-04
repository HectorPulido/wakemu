"""Native monster harvesting; no invented profession XP or server loot tables.

Callers resolve a live registry monster and native reachability before start.
Yield/cooldown are explicit local policies, not undocumented official rates.
"""
import gzip
import json
import struct
import uuid
import threading
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
    with gzip.open(DATA_ROOT / "monster-encyclopedia.json.gz", "rt") as stream:
        catalog = json.load(stream)
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


def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS monster_harvest_receipts(
        token TEXT PRIMARY KEY,character_id INTEGER NOT NULL,monster_id INTEGER NOT NULL,
        action_id INTEGER NOT NULL,completed_at REAL NOT NULL,item_uid INTEGER NOT NULL)"""
    )


class Harvests:
    """One pending occupation per character/target; grant and receipt commit together."""

    def __init__(self, store):
        self.store = store
        self.pending = {}
        self.targets = {}
        self.lock = threading.RLock()
        with store.connection() as db:
            schema(db)

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
        reachable,
        quantity,
        cooldown_seconds=0
    ):
        request = decode_request(body)
        with self.store.connection() as db:
            _lease(self.store, db, account_id, generation, character_id)
            character = self.store.character(account_id, character_id, db)
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
            db.execute("BEGIN IMMEDIATE")
            _lease(self.store, db, account_id, generation, character_id)
            schema(db)
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
                "SELECT 1 FROM monster_harvest_receipts WHERE token=?",
                (ticket["token"],),
            ).fetchone():
                self.cancel(character_id)
                return dict(applied=False, packets=[])
            last = db.execute(
                "SELECT MAX(completed_at) FROM monster_harvest_receipts WHERE monster_id=? AND action_id=?",
                (monster["id"], ticket["rule"]["action_id"]),
            ).fetchone()[0]
            if (
                last is not None
                and self.store.clock() - last < ticket["cooldown_seconds"]
            ):
                raise ValueError("Local monster harvest cooldown")
            # Base pocket accepts ordinary materials; no bag specialty assumptions.
            base = character["inventory_containers"][0]
            occupied = {
                i["slot"]
                for i in character["inventory_items"]
                if i["container"] == base["uid"]
            }
            slot = next((s for s in range(base["capacity"]) if s not in occupied), None)
            if slot is None:
                raise ValueError("Base inventory full")
            uid = allocate(db)
            item = dict(
                uid=uid,
                character_id=character_id,
                reference=ticket["rule"]["item_ref"],
                quantity=ticket["quantity"],
                container=base["uid"],
                slot=slot,
            )
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) VALUES(?,?,?,?,?,?)",
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
            db.execute(
                "INSERT INTO monster_harvest_receipts VALUES(?,?,?,?,?,?)",
                (
                    ticket["token"],
                    character_id,
                    monster["id"],
                    ticket["rule"]["action_id"],
                    self.store.clock(),
                    uid,
                ),
            )
            packet = insertion(item, notification=True)
        self.cancel(character_id)
        return dict(applied=True, item=item, packets=[packet])
