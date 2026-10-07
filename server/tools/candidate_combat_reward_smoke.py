"""Exercise the integrated victory reward path in a disposable candidate DB.

This smoke creates an isolated account/character and a native-shaped terminal
fight, then runs the real ``prepare_finish(policy_resolver=...)`` transaction.
It deliberately avoids opening a game client or joining the live world socket.
Run only inside a candidate container with a database named
``wakemu_candidate_smoke_*``.
"""
import os
import secrets
import struct

from psycopg.conninfo import conninfo_to_dict

from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
from wakfu_server.combat_lifecycle import prepare_finish, outside_progression
from wakfu_server.combat_drops import resolve as resolve_drops, report_loots
from wakfu_server.storage.combat_drop_delivery import (
    apply as deliver_drops,
    claim as claim_temporary,
    temporary_section,
    temporary_update,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_rewards import award
from wakfu_server.fight_store import activate as activate_fight
from wakfu_server.fight_store import create as create_fight
from wakfu_server.inventory_items import equipment_inventory
from wakfu_server.inventory_move import synchronization
from wakfu_server.monsters import owned_instance
from wakfu_server.progression import level_xp
from wakfu_server.reward_policy import resolve as resolve_reward_policy
from wakfu_server.storage.combat_reward_context import build_context as reward_context
from wakfu_server.store import Store
from wakfu_server.wire import account_kamas, account_kamas_update


def _varint(data, offset):
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, offset
        shift += 7
    raise AssertionError("Malformed protobuf varint")


def _fields(data):
    """Decode the protobuf wire types used by FightReport, rejecting extras."""
    rows = []
    offset = 0
    while offset < len(data):
        tag, offset = _varint(data, offset)
        number, wire_type = tag >> 3, tag & 7
        if number <= 0:
            raise AssertionError("Invalid protobuf field number")
        if wire_type == 0:
            value, offset = _varint(data, offset)
        elif wire_type == 2:
            size, offset = _varint(data, offset)
            end = offset + size
            if end > len(data):
                raise AssertionError("Truncated protobuf field")
            value = data[offset:end]
            offset = end
        else:
            raise AssertionError("Unexpected FightReport wire type")
        rows.append((number, wire_type, value))
    return rows


def _one(rows, number, wire_type=None):
    matches = [row for row in rows if row[0] == number]
    if len(matches) != 1 or (wire_type is not None and matches[0][1] != wire_type):
        raise AssertionError(f"Expected exactly one protobuf field {number}")
    return matches[0][2]


def decode_xp_notification(character_id, body):
    if len(body) != struct.calcsize(">BBqqhB"):
        raise AssertionError("Unexpected native 13613 length")
    enabled, count, recipient, delta, levels, spell_count = struct.unpack(
        ">BBqqhB", body
    )
    if enabled != 1 or count != 1 or recipient != character_id or spell_count != 0:
        raise AssertionError("Unexpected native 13613 identity/layout")
    return delta, levels


def decode_wallet_update(body):
    if not isinstance(body, bytes) or len(body) != 8:
        raise AssertionError("Unexpected native 12753 wallet-update length")
    balance = struct.unpack(">q", body)[0]
    if balance < 0:
        raise AssertionError("Native wallet balance cannot be negative")
    return balance


def decode_wallet_section(body):
    if not isinstance(body, bytes) or len(body) != 16:
        raise AssertionError("Unexpected native 13873 wallet-section length")
    count, section, balance = struct.unpack(">IIq", body)
    if count != 1 or section != 6 or balance < 0:
        raise AssertionError("Invalid native 13873 wallet section")
    return balance


def decode_fight_report(fight_id, body):
    if len(body) < 12:
        raise AssertionError("Truncated 12755 envelope")
    envelope_fight, _action_id, _actor_id = struct.unpack_from(">iii", body)
    if envelope_fight != fight_id:
        raise AssertionError("12755 envelope belongs to a different fight")
    report = _fields(body[12:])
    if _one(report, 1, 0) != fight_id or _one(report, 4, 0) != 0:
        raise AssertionError("FightReport identity or winning team is incorrect")
    winning_team = _fields(_one(report, 5, 2))
    player = _fields(_one(winning_team, 2, 2))
    progress = _fields(_one(player, 8, 2))
    loots = []
    for number, wire_type, value in player:
        if number != 7:
            continue
        if wire_type != 2:
            raise AssertionError("FightLoot has an unexpected wire type")
        item = _fields(value)
        loots.append(
            {
                "reference": _one(item, 1, 0),
                "quantity": _one(item, 2, 0),
                "is_purse_loot": bool(_one(item, 3, 0)),
                "is_pvp_loot": bool(_one(item, 4, 0)),
            }
        )
    return {
        "character_id": _one(player, 1, 0),
        "end_xp": _one(progress, 1, 0),
        "won_xp": _one(progress, 2, 0),
        "start_level": _one(progress, 5, 0),
        "end_level": _one(progress, 6, 0),
        "kamas": _one(player, 9, 0),
        "loots": loots,
    }


def _candidate_database(url):
    database = conninfo_to_dict(url).get("dbname", "")
    if not database.startswith("wakemu_candidate_smoke_"):
        raise ValueError("Combat reward smoke requires a disposable candidate database")


def _require_reward_schema(store):
    with store.connection() as db:
        required = db.execute(
            "SELECT to_regclass('fight_reward_policy_receipts') AS receipt, "
            "to_regclass('combat_reward_level_defaults') AS levels"
        ).fetchone()
        if required["receipt"] is None or required["levels"] is None:
            raise ValueError("Candidate database is missing combat reward migrations")
        if (
            db.execute(
                "SELECT 1 FROM combat_reward_level_defaults WHERE monster_level=1"
            ).fetchone()
            is None
        ):
            raise ValueError("Candidate database has no configured level-1 reward")
        drop_schema = db.execute(
            "SELECT to_regclass('fight_drop_awards') AS awards, "
            "to_regclass('fight_drop_delivery_receipts') AS deliveries, "
            "to_regclass('temporary_combat_items') AS temporary"
        ).fetchone()
        if any(
            drop_schema[key] is None for key in ("awards", "deliveries", "temporary")
        ):
            raise ValueError("Candidate database is missing combat drop migrations")


def _fill_inventory(store, character_id):
    """Occupy every available inventory slot so drops exercise overflow."""
    with store.connection() as db:
        containers = db.execute(
            "SELECT uid,capacity FROM inventory_containers "
            "WHERE character_id=%s AND kind IN (0,1,2,3) ORDER BY uid FOR UPDATE",
            (character_id,),
        ).fetchall()
        for container in containers:
            occupied = {
                row["slot"]
                for row in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=%s FOR UPDATE",
                    (container["uid"],),
                ).fetchall()
            }
            for slot in range(container["capacity"]):
                if slot not in occupied:
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,2021,1,%s,%s)",
                        (character_id, container["uid"], slot),
                    )


def _decode_temporary_section(section):
    if not isinstance(section, bytes) or len(section) < 2:
        raise AssertionError("Temporary inventory bootstrap section is truncated")
    size = struct.unpack_from(">h", section)[0]
    if size != len(section) - 2 or size < 0:
        raise AssertionError("Temporary inventory bootstrap length is invalid")
    # `wire.proto_field(10, ...)` uses protobuf's encoded tag 10 (field 1,
    # length-delimited), not the abstract field number 10.
    rows = [
        value
        for number, wire_type, value in _fields(section[2:])
        if number == 1 and wire_type == 2
    ]
    return rows


def _build_winning_fight(store, account_id, generation, character):
    from wakfu_server.equipment_stats import combat_resources

    spawned = owned_instance(
        3112,
        1,
        -200,
        map_id=character["map_id"],
        x=character["x"] + 1,
        y=character["y"],
        z=character["z"],
    )
    fight_id = create_fight(store, account_id, generation, character["id"])
    activate_fight(store, account_id, generation, character["id"], fight_id)
    resources = combat_resources(character)
    player = Actor(
        character["id"],
        0,
        (character["x"], character["y"], character["z"]),
        character["hp"],
        resources["ap"],
        resources["mp"],
        resources["initiative"],
        character["level"],
        account_id,
        True,
        max_hp=character["max_hp"],
    )
    monster = Actor(
        spawned["id"],
        1,
        (spawned["x"], spawned["y"], spawned["z"]),
        spawned["hp"],
        spawned["ap"],
        spawned["mp"],
        spawned["initiative"],
        spawned["level"],
        max_hp=spawned["max_hp"],
    )
    player_position, monster_position = player.position, monster.position
    fight = Fight(
        fight_id,
        (player, monster),
        (player_position, monster_position),
        {0: {player_position}, 1: {monster_position}},
    )
    initialize_fight_snapshots(
        fight,
        characters={character["id"]: character},
        monsters={spawned["id"]: spawned},
        wp_resources={
            character["id"]: (resources["wp"], resources["wp"]),
            spawned["id"]: (spawned["wp"], spawned.get("max_wp", spawned["wp"])),
        },
        running_effects={player.id: (), monster.id: ()},
        initial_effect_uid=max(character["id"], 200) + 1,
    )
    fight.ready(account_id)
    fight.apply_effect_damage(player.id, monster.id, monster.hp)
    if fight.phase != "finished" or fight.winner != 0:
        raise AssertionError("Native fight state did not settle to a player victory")
    return fight, spawned


def main():
    database_url = os.environ["WAKFU_DATABASE_URL"]
    _candidate_database(database_url)
    store = Store(
        database_url,
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        _require_reward_schema(store)
        suffix = secrets.token_hex(5)
        account = store.register("reward_smoke_" + suffix, secrets.token_urlsafe(24))
        account_id = account["id"]
        character_name = "Reward " + "".join(
            secrets.choice("abcdefghjkmnpqrstuvwxyz") for _ in range(8)
        )
        character = store.create_character(account_id, character_name, breed=8)
        generation = store.begin_session(account_id)
        character = store.select_character(account_id, generation, character["id"])
        _fill_inventory(store, character["id"])

        # Put a new level-1 character one XP below the native level-2 threshold;
        # the deterministic configured level-1 reward should cross it.
        with store.connection() as db:
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (level_xp(2) - 1, character["id"]),
            )
        character = store.character(account_id, character["id"])
        fight, spawned = _build_winning_fight(store, account_id, generation, character)
        metadata = {
            character["id"]: dict(
                kind="player",
                account_id=account_id,
                name=character["name"],
                breed=character["breed"],
                is_male=character["sex"] == 0,
            ),
            spawned["id"]: dict(kind="monster", ref=spawned["ref"]),
        }
        runtime = RuntimeMessages(fight)
        delivered_loots = []

        def resolver(db):
            context = reward_context(fight, character, [spawned])
            return resolve_reward_policy(
                store,
                db,
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
                fight_id=fight.id,
                context=context,
                kamas_roll_index=0,
            ).policy

        def loot_resolver(db, reward):
            if not reward.get("awarded") or fight.winner != 0:
                raise AssertionError("Drops require a committed eligible victory")
            from wakfu_server.combat_drops import native_prospection_bonus

            batch = resolve_drops(
                store,
                db,
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
                fight_id=fight.id,
                monsters=[{"actor_id": spawned["id"], "reference": spawned["ref"]}],
                prospecting_bonus=native_prospection_bonus(
                    fight.actors[character["id"]]
                ),
                can_loot=True,
                fight_context={},
                rng=lambda upper: 0,
            )
            delivered = deliver_drops(store, db, batch)
            if not delivered or not any(row["temporary_quantity"] for row in delivered):
                raise AssertionError(
                    "Full inventory did not retain successful drops temporarily"
                )
            delivered_loots[:] = report_loots(batch)
            saved = store.character(account_id, character["id"], db)
            return {
                "loots": delivered_loots,
                "packets": [
                    synchronization(saved),
                    equipment_inventory(saved),
                    temporary_update(db, character["id"]),
                ],
            }

        result = prepare_finish(
            store,
            account_id,
            generation,
            character,
            runtime,
            metadata,
            duration_ms=1,
            fight_instance_id=1,
            policy_resolver=resolver,
            loot_resolver=loot_resolver,
        )
        reward = result["reward"]
        if not reward["awarded"] or reward["xp"] <= 0 or reward["kamas"] <= 0:
            raise AssertionError("Winning fight did not award positive XP and kamas")
        if reward["character"]["level"] != 2:
            raise AssertionError("Winning fight did not cross into level 2")

        packets = dict(result["packets"])
        delta, levels = decode_xp_notification(character["id"], packets[13613])
        if (delta, levels) != (reward["xp"], 1):
            raise AssertionError(
                "13613 XP delta/level notification differs from receipt"
            )
        report = decode_fight_report(fight.id, packets[12755])
        expected_report = {
            "character_id": character["id"],
            "end_xp": reward["character"]["xp"],
            "won_xp": reward["xp"],
            "start_level": 1,
            "end_level": 2,
            "kamas": reward["kamas"],
            "loots": delivered_loots,
        }
        if report != expected_report:
            raise AssertionError(
                "Native 12755 FightReport differs from committed reward: "
                f"decoded={report!r} expected={expected_report!r}"
            )
        if not report["loots"]:
            raise AssertionError(
                "Native 12755 report omitted all successful monster drops"
            )
        packet_opcodes = [opcode for opcode, _body in result["packets"]]
        if packet_opcodes[:3] != [13613, 12238, 12755] or packet_opcodes[-1] != 12691:
            raise AssertionError(
                "Native reward/report/temporary refresh order is incorrect"
            )
        if packet_opcodes.count(12691) != 1:
            raise AssertionError(
                "Victory did not publish the temporary inventory snapshot"
            )
        if (
            decode_wallet_section(account_kamas(reward["character"]["kamas"]))
            != reward["character"]["kamas"]
        ):
            raise AssertionError("Native 13873 absolute wallet packet failed to decode")
        if (
            decode_wallet_update(account_kamas_update(reward["character"]["kamas"]))
            != reward["character"]["kamas"]
        ):
            raise AssertionError("Native 12753 absolute wallet packet failed to decode")

        # A lifecycle retry must return the stored receipt without sending a
        # second delta notification or incrementing either total.
        retry = prepare_finish(
            store,
            account_id,
            generation,
            character,
            runtime,
            metadata,
            duration_ms=1,
            fight_instance_id=1,
            policy_resolver=resolver,
        )
        if retry["reward"]["awarded"] or retry["reward"]["xp"] != reward["xp"]:
            raise AssertionError(
                "Lifecycle retry did not replay the original reward receipt"
            )
        if any(opcode == 13613 for opcode, _body in retry["packets"]):
            raise AssertionError("Lifecycle retry emitted a duplicate XP delta")

        store.close()
        store = Store(
            database_url,
            password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        )
        generation = store.begin_session(account_id)
        restored = store.select_character(account_id, generation, character["id"])
        if (restored["xp"], restored["level"], restored["kamas"]) != (
            reward["character"]["xp"],
            2,
            reward["character"]["kamas"],
        ):
            raise AssertionError("Progression or wallet did not survive reconnect")
        with store.connection() as db:
            bootstrap = temporary_section(db, character["id"])
            bootstrap_items = _decode_temporary_section(bootstrap)
            temp_rows = db.execute(
                "SELECT uid,reference,quantity FROM temporary_combat_items "
                "WHERE character_id=%s ORDER BY uid",
                (character["id"],),
            ).fetchall()
            if len(bootstrap_items) != len(temp_rows) or not temp_rows:
                raise AssertionError(
                    "Reconnect bootstrap omitted durable temporary loot"
                )

            def item_key(item):
                fields = _fields(item)
                return (
                    _one(fields, 1, 0),
                    _one(fields, 2, 0),
                    _one(fields, 3, 0),
                )

            if {item_key(item) for item in bootstrap_items} != {
                (row["uid"], row["reference"], row["quantity"]) for row in temp_rows
            }:
                raise AssertionError(
                    "Temporary bootstrap changed native item identity or quantity"
                )
            destination = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0 "
                "ORDER BY uid LIMIT 1",
                (character["id"],),
            ).fetchone()
            filler = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s AND reference=2021 "
                "ORDER BY uid LIMIT 1 FOR UPDATE",
                (character["id"],),
            ).fetchone()
            if destination is None or filler is None:
                raise AssertionError(
                    "Unable to prepare a native inventory slot for temporary-loot claim"
                )
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (filler["uid"],))
        from wakfu_server.storage.combat_drop_delivery import decode_claim

        claim_row = temp_rows[0]
        claim_body = struct.pack(
            ">qh b q h",
            claim_row["uid"],
            claim_row["quantity"],
            -1,
            destination["uid"],
            -1,
        )
        if decode_claim(claim_body)["uid"] != claim_row["uid"]:
            raise AssertionError("Native temporary-loot claim request failed to decode")
        claimed = claim_temporary(
            store, account_id, generation, character["id"], claim_body
        )
        if not claimed["applied"] or not any(
            opcode == 12691 for opcode, _ in claimed["packets"]
        ):
            raise AssertionError(
                "Temporary-loot claim did not apply and refresh the client"
            )
        with store.connection() as db:
            remaining = db.execute(
                "SELECT count(*) AS n FROM temporary_combat_items WHERE uid=%s AND character_id=%s",
                (claim_row["uid"], character["id"]),
            ).fetchone()["n"]
            transferred = db.execute(
                "SELECT reference,quantity FROM inventory_items WHERE uid=%s AND character_id=%s",
                (claim_row["uid"], character["id"]),
            ).fetchone()
            if (
                remaining
                or transferred is None
                or (transferred["reference"], transferred["quantity"])
                != (claim_row["reference"], claim_row["quantity"])
            ):
                raise AssertionError(
                    "Claim did not move the selected temporary drop into the bag"
                )

        # Replay the frozen policy against the new lease and decode the absolute
        # native actor/wallet refreshes that a reconnect receives.
        with store.connection() as db:
            decision = resolve_reward_policy(
                store,
                db,
                account_id=account_id,
                generation=generation,
                character_id=character["id"],
                fight_id=fight.id,
                context=reward_context(fight, character, [spawned]),
                kamas_roll_index=0,
            )
            replayed_award = award(
                store,
                account_id,
                generation,
                character["id"],
                fight,
                decision.policy,
                db=db,
            )
        if not decision.replayed or replayed_award["awarded"]:
            raise AssertionError("Reconnect replay did not reuse durable receipts")
        actor_opcode, actor_packet = outside_progression(restored)
        if actor_opcode != 13046:
            raise AssertionError(
                "Reconnect progression refresh used an unexpected opcode"
            )
        actor_id, size = struct.unpack_from(">qh", actor_packet)
        actor_blob = actor_packet[10:]
        if actor_id != character["id"] or len(actor_blob) != size or actor_blob[0] != 3:
            raise AssertionError(
                "Native absolute progression actor refresh is malformed"
            )
        if struct.unpack_from(">q", actor_blob, 1)[0] != restored["xp"]:
            raise AssertionError("Native absolute actor refresh has the wrong XP total")
        absolute_wallet = account_kamas(restored["kamas"])
        if decode_wallet_section(absolute_wallet) != restored["kamas"]:
            raise AssertionError("Native absolute wallet refresh is malformed")
        if (
            decode_wallet_update(account_kamas_update(restored["kamas"]))
            != restored["kamas"]
        ):
            raise AssertionError("Native 12753 wallet refresh is malformed")
        with store.connection() as db:
            rows = db.execute(
                "SELECT (SELECT count(*) FROM fight_rewards WHERE fight_id=%s AND character_id=%s) AS rewards, "
                "(SELECT count(*) FROM fight_reward_policy_receipts WHERE fight_id=%s AND character_id=%s) AS policies",
                (fight.id, character["id"], fight.id, character["id"]),
            ).fetchone()
        if rows["rewards"] != 1 or rows["policies"] != 1:
            raise AssertionError("Reward replay created duplicate durable receipts")
        print(
            "PASS: candidate reward callback, XP cross-level, native report/delta, "
            "kamas, drops, full-bag overflow, temporary bootstrap/claim, retry, reconnect "
            "and absolute progression/wallet packets"
        )
    finally:
        store.close()


if __name__ == "__main__":
    main()
