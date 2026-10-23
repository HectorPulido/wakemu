"""Native sidekick equipment custody, retrieval and lossless item unlinking.

Equipment uses the existing full-item chest custody serializer and inventory
capacity planner. Moving an item never creates a second physical UID.
"""
from copy import deepcopy
import struct

from psycopg.types.json import Jsonb

# Original eSo.rcz: eSy unlocks precisely these native fnO positions.
SLOTS = frozenset((0, 3, 4, 5, 7, 8, 10, 12, 13, 15, 16, 22, 17))


def hydrate_equipment(db, companions):
    from wakfu_server.haven_chest import _unjson

    by_id = {row["id"]: row for row in companions}
    for row in companions:
        row["equipment_entries"] = []
    if by_id:
        for entry in db.execute(
            "SELECT * FROM companion_equipment WHERE companion_id=ANY(%s) ORDER BY slot",
            (list(by_id),),
        ):
            by_id[entry["companion_id"]]["equipment_entries"].append(
                dict(slot=entry["slot"], entry=_unjson(entry["entry"]))
            )
    return companions


def equipment_blob(entries):
    """Original pT/vF: u16 count, i16 slot + vj item, u16 reserved count."""
    from wakfu_server.inventory_items import item_form

    entries = tuple(entries)
    if len(entries) > len(SLOTS) or len({row["slot"] for row in entries}) != len(
        entries
    ):
        raise ValueError("Invalid native companion equipment slots")
    payload = []
    for row in sorted(entries, key=lambda row: row["slot"]):
        if row["slot"] not in SLOTS or row["entry"]["item"]["quantity"] != 1:
            raise ValueError("Invalid native companion equipment unit")
        payload.append(struct.pack(">h", row["slot"]) + item_form(row["entry"]["item"]))
    return struct.pack(">H", len(entries)) + b"".join(payload) + b"\x00\x00"


def pseudo_character(entries, owner, level):
    """Reuse exact owned equipment predicates and effects without owner aptitudes."""
    from wakfu_server.wire import proto_field

    items = [dict(row["entry"]["item"], character_id=owner["id"]) for row in entries]
    sheet = b"".join(
        proto_field(
            10,
            proto_field(8, row["entry"]["item"]["uid"]) + proto_field(16, row["slot"]),
        )
        for row in entries
    )
    return dict(
        id=owner["id"],
        account_id=owner["account_id"],
        level=level,
        effective_level=level,
        active_build_index=0,
        inventory_items=items,
        builds={
            0: dict(
                sheet=proto_field(24, level).hex(), equipment=sheet.hex(), aptitudes=""
            )
        },
    )


def criterion_context(owner, level, resource_baseline=None):
    """Only native NPC identity, account-company and projected scene authority.

    Original eJD resolves the registered bje actor's account, not its owner
    character's breed, aptitudes or other player-only criterion components.
    """
    from wakfu_server.company_authority import CompanySnapshot
    from wakfu_server.world_clock import current_time_ms

    from wakfu_server.national_progression import NPC_SOURCE

    context = dict(
        actor_kind="native_companion_npc",
        level=level,
        native_national_component=NPC_SOURCE,
        resource_baseline=resource_baseline,
        world_time_ms=current_time_ms(),
    )
    if type(owner.get("account_id")) is int and owner["account_id"] > 0:
        context["account_id"] = owner["account_id"]
    stored = owner.get("equipment_criterion_context") or {}
    if "is_neo_server" in stored:
        if type(stored["is_neo_server"]) is not bool:
            raise ValueError("Invalid actual companion equipment Neo mode")
        context["is_neo_server"] = stored["is_neo_server"]
    if "company_snapshot" in stored:
        snapshot = CompanySnapshot.from_record(stored["company_snapshot"])
        snapshot.require_owner(context.get("account_id"))
        context["company_snapshot"] = snapshot.record()
    if "map_id" in owner:
        if type(owner["map_id"]) is not int or owner["map_id"] < 0:
            raise ValueError("Invalid actual companion projected map")
        context["native_map_id"] = owner["map_id"]
    return context


def stat_bonuses(
    entries, owner, level, *, native_baseline=None, native_resource_baseline=None
):
    from wakfu_server.equipment_stats import bonuses

    # This call is made only for a durable native NPC companion projection.
    # Keep the criterion authority explicit; ordinary player equipment callers
    # continue to use the fail-closed default context.
    return bonuses(
        pseudo_character(entries, owner, level),
        criterion_context=criterion_context(owner, level, native_resource_baseline),
        ignore_ineligible=True,
        native_baseline=native_baseline,
    )


def unsupported_are_runtime_operators(entries, unsupported):
    """Identify only complete passive roots that the shared battle motor owns.

    Scalar projection must not reject a native operator merely because it
    changes combat state instead of a character-stat snapshot. This helper
    grants no execution authority: the Ready-time complete graph validator
    still pins or explicitly defers each source against the live factory.
    Missing identities, child-only effects, malformed templates, and passive
    roots owned by another subsystem remain rejected here.
    """
    if not unsupported:
        return True
    try:
        from wakfu_server.equipment_stats import CATALOG
        from wakfu_server.combat_character_copy_equipment import (
            native_copied_equipment_catalog,
        )
        from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
        from wakfu_server.combat_equipment_root_roles import root_role
    except (ImportError, KeyError, TypeError, ValueError):
        return False

    by_uid = {}
    for row in entries:
        entry = row.get("entry") if isinstance(row, dict) else None
        item = entry.get("item") if isinstance(entry, dict) else None
        if not isinstance(item, dict) or type(item.get("uid")) is not int:
            return False
        by_uid[item["uid"]] = item
    definitions = native_copied_equipment_catalog()
    for issue in unsupported:
        if (
            not isinstance(issue, dict)
            or issue.get("reason") != "unsupported-native-effect"
            or type(issue.get("uid")) is not int
            or type(issue.get("reference")) is not int
            or type(issue.get("effect_id")) is not int
        ):
            return False
        item = by_uid.get(issue["uid"])
        if item is None or item.get("reference") != issue["reference"]:
            return False
        template = CATALOG.get(issue["reference"])
        if not isinstance(template, dict):
            return False
        identities = [
            effect
            for effect in template.get("effects", ())
            if isinstance(effect, dict) and effect.get("id") == issue["effect_id"]
        ]
        if len(identities) != 1:
            return False
        try:
            plan = copied_equipment_plan(issue["reference"], definitions)
        except (KeyError, TypeError, ValueError):
            return False
        roots = [
            root
            for root in plan["roots"]
            if root.get("reference") == issue["effect_id"]
        ]
        if len(roots) != 1:
            return False
        try:
            if (
                root_role(issue["reference"], roots[0], identities[0])
                != "runtime-operator"
            ):
                return False
        except (KeyError, TypeError, ValueError):
            return False
    return True


def decode_save(body):
    if not isinstance(body, bytes) or len(body) < 10:
        raise ValueError("Invalid native companion equipment request")
    identity, count = struct.unpack_from(">qh", body)
    if identity <= 0 or not 0 <= count <= 26:
        raise ValueError("Invalid companion equipment identity or change count")
    cursor, changes, seen = 10, [], set()
    for _ in range(count):
        if cursor + 2 > len(body):
            raise ValueError("Truncated companion equipment change")
        equip, slot = struct.unpack_from(">Bb", body, cursor)
        cursor += 2
        if equip not in (0, 1) or slot not in SLOTS or slot in seen:
            raise ValueError("Invalid or repeated native companion equipment position")
        seen.add(slot)
        uid = None
        if equip:
            if cursor + 8 > len(body):
                raise ValueError("Truncated companion equipment UID")
            uid = struct.unpack_from(">q", body, cursor)[0]
            cursor += 8
            if uid <= 0:
                raise ValueError("Invalid owned equipment identity")
        changes.append(dict(slot=slot, uid=uid))
    if cursor != len(body):
        raise ValueError("Trailing companion equipment data")
    return identity, changes


def identity_request(body):
    if (
        not isinstance(body, bytes)
        or len(body) != 8
        or struct.unpack(">q", body)[0] <= 0
    ):
        raise ValueError("Invalid native companion identity request")
    return struct.unpack(">q", body)[0]


def response(identity, *, error=False, entries=None):
    """cug12646 restores the build editor even after an unsuccessful save."""
    return 12646, struct.pack(
        ">qBB", identity, int(error), int(entries is not None)
    ) + (equipment_blob(entries) if entries is not None else b"")


def _fence(store, db, account_id, generation, character_id, identity):
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.simple_item_actions import _idle

    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    lock_inventory_character(store, db, account_id, generation, character_id)
    _idle(db, character_id, store.now())
    companion = db.execute(
        "SELECT * FROM account_companions WHERE id=%s AND account_id=%s FOR UPDATE",
        (identity, account_id),
    ).fetchone()
    if companion is None or not companion["linked"]:
        raise ValueError("Companion is unavailable or belongs to another account")
    if db.execute(
        "SELECT 1 FROM combat_fight_companions c JOIN combat_fights f ON f.id=c.fight_id "
        "WHERE c.companion_id=%s AND f.status IN ('placement','active') "
        "AND c.health_settled_at IS NULL LIMIT 1",
        (identity,),
    ).fetchone():
        raise ValueError("Companion equipment cannot change during combat")
    return dict(companion), store.character(account_id, character_id, db)


def _allocate_return(containers, inventory, entries, character_id):
    from wakfu_server.achievements.rewards import _plan_item_capacity
    from wakfu_server.combat_drop_delivery import _container_can_hold

    eligible = [bag for bag in containers if _container_can_hold(bag, character_id)]
    planned = deepcopy(inventory)
    for entry in entries:
        _, places = _plan_item_capacity(
            eligible, [row["item"] for row in planned], [], 1, 1
        )
        bag, slot, amount = places[0]
        restored = deepcopy(entry)
        restored["item"].update(
            character_id=character_id, container=bag["uid"], slot=slot, quantity=1
        )
        planned.append(restored)
    return planned


def _result(store, db, account_id, character_id, companion, *, entries):
    from wakfu_server.inventory_items import equipment_inventory
    from wakfu_server.inventory_move import synchronization
    from wakfu_server.companions import collection, refresh_packet

    character = store.character(account_id, character_id, db)
    return dict(
        character=character,
        companion_id=companion["id"],
        packets=[
            synchronization(character),
            equipment_inventory(character),
            response(companion["id"], entries=entries),
            refresh_packet(collection(db, account_id)),
        ],
    )


def save(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight,
    native_admission=None
):
    """cnS13191 saves one validated atomic equipment change plan."""
    from wakfu_server.haven_chest import _snapshot, _json, persist_inventory
    from wakfu_server.companions import level_for_xp, loaded_level_cap
    from wakfu_server.builds import effective_sheet_level
    from wakfu_server.equipment import validate_sheet
    from wakfu_server.simple_item_actions import _equipped
    from wakfu_server.combat_drop_delivery import _template_binding, _effective_bound

    identity, changes = decode_save(body)
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Companion equipment cannot change during combat")
    with store.connection() as db:
        companion, character = _fence(
            store, db, account_id, generation, character_id, identity
        )
        existing = hydrate_equipment(db, [companion])[0]["equipment_entries"]
        selected = {row["slot"]: deepcopy(row) for row in existing}
        inventory = [_snapshot(db, item) for item in character["inventory_items"]]
        by_uid = {row["item"]["uid"]: row for row in inventory}
        physical_uids = set(by_uid)
        by_uid.update({row["entry"]["item"]["uid"]: row["entry"] for row in existing})
        outgoing = set()
        for change in changes:
            slot, uid = change["slot"], change["uid"]
            selected.pop(slot, None)
            if uid is None:
                continue
            entry = by_uid.get(uid)
            if (
                entry is None
                or entry["item"]["quantity"] != 1
                or _equipped(character, uid)
            ):
                raise ValueError(
                    "Companion equipment requires one unequipped owned unit"
                )
            item = entry["item"]
            binding = (
                entry["metadata"].get("inventory_item_bindings", {}).get("bound", False)
            )
            kind = _template_binding(item["reference"])[0]
            if kind.endswith("TO_CHARACTER") and _effective_bound(
                dict(item, bound=binding)
            ):
                raise ValueError("Character-bound equipment cannot move to a companion")
            if uid in outgoing:
                raise ValueError(
                    "The same owned unit cannot occupy two companion positions"
                )
            if uid in physical_uids:
                outgoing.add(uid)
            selected[slot] = dict(slot=slot, entry=entry)
        final = list(selected.values())
        level = min(
            level_for_xp(companion["xp"]),
            loaded_level_cap(
                db, store, account_id, character_id, owner_character=character
            ),
        )
        pseudo = pseudo_character(final, character, level)
        from wakfu_server.combat_actor_snapshot import native_npc_creation_values
        from wakfu_server.equipment_resource_bonuses import from_native_values

        native_values = native_npc_creation_values(companion["breed_ref"], level)
        baseline = {identity: row["current"] for identity, row in native_values.items()}
        resource_baseline = from_native_values(native_values)
        from wakfu_server.equipment import physical_sheet
        from wakfu_server.equipment_conditions import catalog

        context = criterion_context(character, level, resource_baseline)
        blob = bytes.fromhex(pseudo["builds"][0]["equipment"])
        physical = physical_sheet(pseudo, blob, criterion_context=context)
        owned = {row["uid"]: row for row in pseudo["inventory_items"]}
        if any(
            "GetCharac"
            in (
                catalog().get(str(owned[row["uid"]]["reference"]), {}).get("EQUIP")
                or ""
            )
            for row in physical
        ):
            from wakfu_server.equipment_eligibility import precheck_new
            from wakfu_server.combat_companions import equipment_bonuses
            from wakfu_server.equipment_characteristics import native_rows

            prior_gear = equipment_bonuses(
                level,
                existing,
                character,
                native_baseline=baseline,
                native_resource_baseline=resource_baseline,
            )
            current_stats = {}
            for stat, row in native_rows().items():
                if row["expandable"] or row["frozen"]:
                    continue
                value = (
                    (baseline[stat] + prior_gear.get(stat, 0) + (1 << 31)) % (1 << 32)
                ) - (1 << 31)
                current_stats[stat] = min(row["maximum"], max(row["minimum"], value))

            precheck_new(
                pseudo,
                physical,
                previous_character=pseudo_character(existing, character, level),
                criterion_context=context,
                native_baseline=baseline,
                current_characteristics=current_stats,
            )
        validate_sheet(
            pseudo,
            blob,
            criterion_context=context,
            native_baseline=baseline,
        )
        effects = stat_bonuses(
            final,
            character,
            level,
            native_baseline=baseline,
            native_resource_baseline=resource_baseline,
        )
        if not unsupported_are_runtime_operators(final, effects["unsupported"]) or any(
            effects["percentages"].values()
        ):
            raise ValueError(
                "Companion equipment contains an unsupported native passive effect"
            )
        if effects["unsupported"]:
            if not callable(native_admission):
                raise ValueError(
                    "Native companion passive requires live factory admission"
                )
            admission = native_admission(companion, character, final, level)
            if (
                not isinstance(admission, dict)
                or admission.get("status") != "supported"
            ):
                reasons = (
                    admission.get("reasons", ()) if isinstance(admission, dict) else ()
                )
                detail = "; ".join(str(reason) for reason in reasons)
                raise ValueError(
                    "Native companion passive graph is not fully admitted"
                    + (": " + detail if detail else "")
                )
        # Validate the original wire before deleting any physical inventory unit.
        equipment_blob(final)
        final_uids = {row["entry"]["item"]["uid"] for row in final}
        returned = [
            row["entry"]
            for row in existing
            if row["entry"]["item"]["uid"] not in final_uids
        ]
        planned = [row for row in inventory if row["item"]["uid"] not in outgoing]
        planned = _allocate_return(
            character["inventory_containers"], planned, returned, character_id
        )
        persist_inventory(db, character_id, inventory, planned)
        db.execute("DELETE FROM companion_equipment WHERE companion_id=%s", (identity,))
        for row in final:
            db.execute(
                "INSERT INTO companion_equipment(companion_id,slot,uid,entry) VALUES(%s,%s,%s,%s)",
                (
                    identity,
                    row["slot"],
                    row["entry"]["item"]["uid"],
                    Jsonb(_json(row["entry"])),
                ),
            )
        from wakfu_server.combat_companions import native_stats
        from secrets import randbelow

        projected = native_stats(
            companion["breed_ref"],
            level,
            equipment_entries=final,
            owner=character,
            record=companion,
            equipment_rng=randbelow,
        )
        maximum = projected["max_hp"]
        missing = companion["max_hp"] - companion["hp"]
        hp = (
            projected["hp"]
            if projected.get("equipment_hp_projection")
            else max(0, maximum - missing)
        )
        checkpoint = projected.get("equipment_hp_projection")
        db.execute(
            "UPDATE account_companions SET max_hp=%s,hp=%s,equipment_hp_projection=%s WHERE id=%s",
            (
                maximum,
                hp,
                Jsonb(checkpoint) if checkpoint is not None else None,
                identity,
            ),
        )
        return _result(store, db, account_id, character_id, companion, entries=final)


def retrieve_all(store, account_id, generation, character_id, body, *, in_fight):
    identity = identity_request(body)
    # Submit every native slot to the same locked save plan. No read/unlock gap
    # can leave newly equipped gear behind during a retrieve-all operation.
    request = struct.pack(">qh", identity, len(SLOTS)) + b"".join(
        struct.pack(">Bb", 0, slot) for slot in sorted(SLOTS)
    )
    return save(store, account_id, generation, character_id, request, in_fight=in_fight)


def unlink(store, account_id, generation, character_id, body, *, in_fight):
    """coa12019 returns a sidekick item with original companionInfo XP intact.

    The installed current unlink confirmation explicitly promises no XP loss.
    Its UI rejects a sidekick still in the party, with gear, or without room.
    """
    from wakfu_server.companions import descriptors, collection, refresh_packet
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.inventory_items import grant, insertion, equipment_inventory
    from wakfu_server.inventory_move import ACQUISITION_STACKS, synchronization
    from wakfu_server.combat_drop_delivery import _save_binding, _template_bound
    from wakfu_server.simple_item_actions import _idle

    identity = identity_request(body)
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Companion unlinking is unavailable during combat")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        lock_inventory_character(store, db, account_id, generation, character_id)
        _idle(db, character_id, store.now())
        companion = db.execute(
            "SELECT * FROM account_companions WHERE id=%s AND account_id=%s FOR UPDATE",
            (identity, account_id),
        ).fetchone()
        if companion is None:
            raise ValueError("Companion is unavailable or belongs to another account")
        if not companion["linked"]:
            saved = store.character(account_id, character_id, db)
            return dict(
                character=saved,
                companion_id=identity,
                packets=[
                    synchronization(saved),
                    equipment_inventory(saved),
                    refresh_packet(collection(db, account_id)),
                ],
                applied=False,
            )
        companion, character = _fence(
            store, db, account_id, generation, character_id, identity
        )
        if db.execute(
            "SELECT 1 FROM account_companion_slots WHERE companion_id=%s", (identity,)
        ).fetchone():
            raise ValueError("Remove the companion from the party before unlinking it")
        if db.execute(
            "SELECT 1 FROM companion_equipment WHERE companion_id=%s", (identity,)
        ).fetchone():
            raise ValueError("Retrieve the companion's equipment before unlinking it")
        descriptor = next(
            (
                row
                for row in descriptors().values()
                if row["breed_ref"] == companion["breed_ref"]
            ),
            None,
        )
        if descriptor is None:
            raise ValueError("Companion has no original activation item")
        from wakfu_server.achievements.rewards import _plan_item_capacity
        from wakfu_server.combat_drop_delivery import _container_can_hold

        containers = [
            bag
            for bag in character["inventory_containers"]
            if _container_can_hold(bag, character_id)
        ]
        _, placements = _plan_item_capacity(
            containers, character["inventory_items"], [], 1, 1
        )
        bag, slot, _ = placements[0]
        item = grant(
            store,
            account_id,
            generation,
            character_id,
            reference=descriptor["item_ref"],
            quantity=1,
            container=bag["uid"],
            slot=slot,
            allowed_references=ACQUISITION_STACKS,
            db=db,
        )
        _save_binding(
            db, item["uid"], item["reference"], _template_bound(item["reference"])
        )
        db.execute(
            "INSERT INTO inventory_item_companions(uid,xp) VALUES(%s,%s)",
            (item["uid"], companion["xp"]),
        )
        item["companion_xp"] = companion["xp"]
        db.execute(
            "UPDATE account_companions SET linked=false WHERE id=%s", (identity,)
        )
        db.execute(
            "INSERT INTO companion_unlink_receipts(companion_id,link_revision,account_id,item_uid) "
            "VALUES(%s,%s,%s,%s)",
            (identity, companion["link_revision"], account_id, item["uid"]),
        )
        saved = store.character(account_id, character_id, db)
        return dict(
            character=saved,
            companion_id=identity,
            applied=True,
            packets=[
                insertion(item),
                equipment_inventory(saved),
                refresh_packet(collection(db, account_id)),
            ],
        )
