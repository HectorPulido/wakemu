"""Owned native stele selection, costs and immutable boss encounter receipts.

The installed client supplies the interface, costs, states and reward identities.
Reward rotation is deliberately fixed in SQL instead of pretending to reproduce
an unavailable official monthly server. Listed items are eligibility, not grants.
"""
import json
import struct
from datetime import timedelta

from wakfu_server.inventory_items import _lease
from wakfu_server.wire import proto_field, account_kamas_update


def definition(store, map_id, object_id):
    """Classify native browse actions without treating unrelated objects as steles."""
    with store.connection() as db:
        row = db.execute(
            "SELECT * FROM dungeon_stele_placements WHERE map_id=%s AND object_id=%s",
            (map_id, object_id),
        ).fetchone()
    return None if row is None else dict(row)


def cancel_packet(character_id):
    """Cancel the client-local native type-34 occupation after rejected browsing."""
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid stele occupation actor")
    return 12088, struct.pack(">BhqI", 3, 34, character_id, 0)


def close(store, account_id, generation, character_id, object_id):
    """Release only this session's matching view; stale closes preserve new views."""
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        db.execute(
            "DELETE FROM dungeon_stele_leases WHERE character_id=%s AND generation=%s AND object_id=%s",
            (character_id, generation, object_id),
        )
    return []


def request(body):
    if len(body) < 12:
        raise ValueError("Truncated stele selection")
    identity, count = struct.unpack_from(">qh", body)
    if identity <= 0 or not 0 <= count <= 32 or len(body) < 12 + count * 4:
        raise ValueError("Invalid stele difficulty list")
    difficulties = list(struct.unpack_from(">" + "i" * count, body, 10))
    offset = 10 + count * 4
    count = struct.unpack_from(">h", body, offset)[0]
    offset += 2
    if not 0 <= count <= 128 or len(body) != offset + count * 4:
        raise ValueError("Invalid stele reward list")
    rewards = list(struct.unpack_from(">" + "i" * count, body, offset))
    if len(set(difficulties)) != len(difficulties) or len(set(rewards)) != len(rewards):
        raise ValueError("Duplicate stele selection")
    return identity, sorted(difficulties), sorted(rewards)


def plan(configuration, difficulties, rewards):
    """Validate selection against the server's fixed native reward rotation."""
    native = {r["id"]: r for r in configuration["difficulties"]}
    if any(type(i) is not int or i not in native for i in difficulties):
        raise ValueError("Unknown native stele difficulty")
    if len(set(difficulties)) != len(difficulties) or len(set(rewards)) != len(rewards):
        raise ValueError("Duplicate stele selection")
    weight = sum(native[i]["weight"] for i in difficulties)
    selected, allowed, paid_options = [], set(), 0
    for tier in configuration["tiers"]:
        if weight < tier["required_weight"]:
            continue
        dynamic = {r["id"]: r for r in tier["dynamic_rewards"]}
        chosen = set(rewards) & dynamic.keys()
        allowed.update(dynamic)
        selected.extend(tier["static_rewards"])
        selected.extend(dynamic[i] for i in sorted(chosen))
        paid_options += max(0, len(chosen) - tier["free_rewards_count"])
    if set(rewards) - allowed:
        raise ValueError("Stele reward is outside the unlocked fixed rotation")
    return dict(
        difficulty_ids=sorted(difficulties),
        reward_ids=sorted(rewards),
        state_ids=[native[i]["state_id"] for i in sorted(difficulties)],
        weight=weight,
        paid_options=paid_options,
        rewards=selected,
        item_references=sorted({r["item_reference"] for r in selected}),
        source_sha256=configuration["source_sha256"],
    )


def information(configuration, chosen=None):
    chosen = chosen or dict(difficulty_ids=[], reward_ids=[], weight=0)

    def reward(row, enabled):
        return b"".join(
            proto_field(tag, value)
            for tag, value in (
                (8, row["id"]),
                (16, row["item_reference"]),
                (24, row["quantity"]),
                (32, int(enabled)),
            )
        )

    body = proto_field(8, configuration["id"])
    for tier in configuration["tiers"]:
        unlocked = chosen["weight"] >= tier["required_weight"]
        value = proto_field(8, tier["id"])
        for row in tier["static_rewards"]:
            value += proto_field(18, reward(row, unlocked))
        for row in tier["dynamic_rewards"]:
            value += proto_field(
                26, reward(row, unlocked and row["id"] in chosen["reward_ids"])
            )
        value += proto_field(32, tier["required_weight"])
        body += proto_field(18, value)
    for identity in chosen["difficulty_ids"]:
        body += proto_field(24, identity)
    body += proto_field(32, int(bool(chosen["difficulty_ids"])))
    return 13326, body


def _scope(store, db, account_id, generation, character_id, object_id):
    _lease(store, db, account_id, generation, character_id)
    character = db.execute(
        "SELECT * FROM characters WHERE id=%s", (character_id,)
    ).fetchone()
    instance = character["instance_id"]
    run = db.execute(
        "SELECT r.*,i.status instance_status FROM dungeon_room_runs r JOIN dungeon_instances i USING(instance_id) WHERE r.instance_id=%s FOR UPDATE OF r,i",
        (instance,),
    ).fetchone()
    if (
        run is None
        or run["status"] != "active"
        or run["instance_status"] != "active"
        or run["current_room"] != len(run["rooms"])
    ):
        raise ValueError("Steles require the active boss room")
    member = db.execute(
        "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s AND session_generation=%s AND role='leader' AND status='active'",
        (instance, character_id, generation),
    ).fetchone()
    room = db.execute(
        "SELECT asset_map_id FROM dungeon_room_spawn_receipts WHERE instance_id=%s AND room_order=%s",
        (instance, run["current_room"]),
    ).fetchone()
    leader = db.execute(
        "SELECT 1 FROM player_parties p JOIN player_party_members m ON m.party_id=p.id AND m.character_id=p.leader_id WHERE p.id=%s AND p.leader_id=%s FOR UPDATE OF p",
        (run["party_id"], character_id),
    ).fetchone()
    if (
        member is None
        or leader is None
        or room is None
        or room["asset_map_id"] != character["map_id"]
    ):
        raise ValueError(
            "Only the current dungeon leader may activate a boss room stele"
        )
    from wakfu_server import dungeon_fight_binding

    dungeon_fight_binding.reconcile_aborted_encounters(db, instance_id=instance)
    if db.execute(
        "SELECT 1 FROM dungeon_room_encounters WHERE instance_id=%s AND status='active'",
        (instance,),
    ).fetchone():
        raise ValueError("Stele selection is frozen during the encounter")
    placement = db.execute(
        "SELECT p.*,d.configuration FROM dungeon_stele_placements p JOIN dungeon_stele_definitions d USING(stele_id) WHERE p.map_id=%s AND p.object_id=%s",
        (character["map_id"], object_id),
    ).fetchone()
    if (
        placement is None
        or abs(character["x"] - placement["x"]) + abs(character["y"] - placement["y"])
        > 4
        or abs(character["z"] - placement["z"]) > 1
    ):
        raise ValueError("Stele is outside the current interaction range")
    _eligibility(db, instance, placement["configuration"])
    return character, placement


def _eligibility(db, instance, configuration):
    from wakfu_server import dungeon_difficulty

    chosen = dungeon_difficulty.selection(db, instance)
    if configuration["competitive_required"] and not chosen["competitive"]:
        raise ValueError("Stele requires competitive mode")
    if chosen["stasis_level"] < configuration["minimum_stasis"]:
        raise ValueError("Stele requires a higher Stasis level")


def _chosen(db, instance, identity):
    row = db.execute(
        "SELECT selection FROM dungeon_stele_selections WHERE instance_id=%s AND stele_id=%s",
        (instance, identity),
    ).fetchone()
    return None if row is None else row["selection"]


def browse(store, account_id, generation, character_id, object_id):
    with store.connection() as db:
        character, placement = _scope(
            store, db, account_id, generation, character_id, object_id
        )
        db.execute(
            "INSERT INTO dungeon_stele_leases VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET instance_id=EXCLUDED.instance_id,map_id=EXCLUDED.map_id,object_id=EXCLUDED.object_id,stele_id=EXCLUDED.stele_id,generation=EXCLUDED.generation,expires_at=EXCLUDED.expires_at",
            (
                character_id,
                character["instance_id"],
                character["map_id"],
                object_id,
                placement["stele_id"],
                generation,
                store.now() + timedelta(minutes=5),
            ),
        )
        return [
            information(
                placement["configuration"],
                _chosen(db, character["instance_id"], placement["stele_id"]),
            )
        ]


def _consume(db, account_id, character_id, costs):
    """Consume owned resource stacks and wallet in the selection transaction."""
    packets, kamas, items = [], 0, {}
    for cost, multiplier in costs:
        for row in cost:
            kamas += row["kamas"] * multiplier
            if row["item_reference"] > 0 and row["quantity"] > 0:
                items[row["item_reference"]] = (
                    items.get(row["item_reference"], 0) + row["quantity"] * multiplier
                )
    if kamas:
        row = db.execute(
            "UPDATE account_wallets SET kamas=kamas-%s WHERE account_id=%s AND kamas>=%s RETURNING kamas",
            (kamas, account_id, kamas),
        ).fetchone()
        if row is None:
            raise ValueError("Insufficient stele activation kamas")
        packets.append((12753, account_kamas_update(row["kamas"])))
    for reference, required in sorted(items.items()):
        rows = list(
            db.execute(
                "SELECT uid,quantity FROM inventory_items WHERE character_id=%s AND reference=%s ORDER BY uid FOR UPDATE",
                (character_id, reference),
            )
        )
        if sum(r["quantity"] for r in rows) < required:
            raise ValueError("Insufficient stele activation resources")
        for row in rows:
            take = min(required, row["quantity"])
            if not take:
                break
            if take == row["quantity"]:
                db.execute("DELETE FROM inventory_items WHERE uid=%s", (row["uid"],))
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s",
                    (take, row["uid"]),
                )
            packets.append((12470, struct.pack(">qh", row["uid"], -take)))
            required -= take
    return packets


def activate(store, account_id, generation, character_id, body):
    identity, difficulties, rewards = request(body)
    with store.connection() as db:
        lease = db.execute(
            "SELECT * FROM dungeon_stele_leases WHERE character_id=%s AND generation=%s AND expires_at>%s",
            (character_id, generation, store.now()),
        ).fetchone()
        if lease is None or lease["stele_id"] != identity:
            raise ValueError("Stele selection requires an owned browse lease")
        character, placement = _scope(
            store, db, account_id, generation, character_id, lease["object_id"]
        )
        if (
            character["instance_id"] != lease["instance_id"]
            or character["map_id"] != lease["map_id"]
            or placement["stele_id"] != identity
        ):
            raise ValueError("Stele browse lease belongs to another room")
        config = placement["configuration"]
        chosen = plan(config, difficulties, rewards)
        old = _chosen(db, character["instance_id"], identity)
        if (
            old
            and old["difficulty_ids"] == difficulties
            and old["reward_ids"] == rewards
        ):
            return [information(config, old)]
        # A paid activation is cumulative for this dungeon run. Removing options
        # cannot manufacture refunds or evade the cost of re-enabling them.
        if old and (
            set(old["difficulty_ids"]) - set(difficulties)
            or set(old["reward_ids"]) - set(rewards)
        ):
            raise ValueError(
                "Activated stele options are cumulative until the dungeon resets"
            )
        additional = len(difficulties) - (len(old["difficulty_ids"]) if old else 0)
        paid = chosen["paid_options"] - (old["paid_options"] if old else 0)
        packets = _consume(
            db,
            account_id,
            character_id,
            [(config["activation_cost"], additional), (config["option_cost"], paid)],
        )
        db.execute(
            "INSERT INTO dungeon_stele_selections(instance_id,stele_id,selection) VALUES(%s,%s,%s::jsonb) ON CONFLICT(instance_id,stele_id) DO UPDATE SET revision=dungeon_stele_selections.revision+1,selection=EXCLUDED.selection",
            (character["instance_id"], identity, json.dumps(chosen)),
        )
        return packets + [information(config, chosen)]


def freeze_encounter(db, instance_id, fight_id):
    """Call after bind_encounter, before fight publication, in the same transaction."""
    if (
        db.execute(
            "SELECT to_regclass('dungeon_stele_encounters') relation"
        ).fetchone()["relation"]
        is None
    ):
        return None
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (instance_id,),
    ).fetchone()
    old = encounter_snapshot(db, fight_id)
    if old is not None:
        if old["instance_id"] != instance_id:
            raise ValueError("Stele encounter instance changed")
        return old
    encounter = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s AND instance_id=%s",
        (fight_id, instance_id),
    ).fetchone()
    if run is None or encounter is None:
        raise ValueError("Stele freeze requires a bound dungeon encounter")
    if (
        run["status"] != "active"
        or encounter["status"] != "active"
        or encounter["room_order"] != run["current_room"]
    ):
        raise ValueError("Stele freeze requires the current active encounter")
    from wakfu_server import dungeon_difficulty

    difficulty = dungeon_difficulty.selection(db, instance_id)
    frozen_difficulty = db.execute(
        "SELECT snapshot FROM dungeon_encounter_difficulties WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if frozen_difficulty is None:
        # Legacy and native non-Stasis rooms have no scaling receipt. They also
        # have no stele reward authority; do not require or invent one to fight.
        scaling = dungeon_difficulty.encounter_scaling(db, instance_id)
        selected = db.execute(
            "SELECT 1 FROM dungeon_stele_selections WHERE instance_id=%s LIMIT 1",
            (instance_id,),
        ).fetchone()
        if scaling is None and selected is None:
            return None
    if (
        frozen_difficulty is None
        or frozen_difficulty["snapshot"]["selection_revision"] != difficulty["revision"]
    ):
        raise ValueError("Stele profile differs from the frozen encounter")
    selections = []
    if encounter["room_order"] == len(run["rooms"]):
        for row in db.execute(
            "SELECT s.stele_id,s.revision,s.selection,d.configuration FROM dungeon_stele_selections s JOIN dungeon_stele_definitions d USING(stele_id) WHERE s.instance_id=%s ORDER BY s.stele_id",
            (instance_id,),
        ):
            config = row["configuration"]
            eligible_rewards = not (
                (config["competitive_required"] and not difficulty["competitive"])
                or difficulty["stasis_level"] < config["minimum_stasis"]
            )
            validated = plan(
                config,
                row["selection"]["difficulty_ids"],
                row["selection"]["reward_ids"],
            )
            if validated != row["selection"]:
                raise ValueError("Stele configuration changed after paid activation")
            selections.append(
                dict(
                    row["selection"],
                    stele_id=row["stele_id"],
                    revision=row["revision"],
                    eligible_rewards=eligible_rewards,
                )
            )
    snapshot = dict(
        schema=1,
        instance_id=instance_id,
        fight_id=fight_id,
        player_team=encounter["player_team"],
        difficulty_revision=difficulty["revision"],
        selections=selections,
        selected_stele_item_references=sorted(
            {
                i
                for s in selections
                if s["eligible_rewards"]
                for i in s["item_references"]
            }
        ),
    )
    db.execute(
        "INSERT INTO dungeon_stele_encounters VALUES(%s,%s,%s::jsonb)",
        (fight_id, instance_id, json.dumps(snapshot)),
    )
    # Paid choices survive defeat/abort within this run. Only the interaction
    # lease expires here; each encounter keeps its own immutable selection.
    db.execute("DELETE FROM dungeon_stele_leases WHERE instance_id=%s", (instance_id,))
    return snapshot


def encounter_snapshot(db, fight_id):
    if (
        db.execute(
            "SELECT to_regclass('dungeon_stele_encounters') relation"
        ).fetchone()["relation"]
        is None
    ):
        return None
    row = db.execute(
        "SELECT snapshot FROM dungeon_stele_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    return None if row is None else row["snapshot"]
