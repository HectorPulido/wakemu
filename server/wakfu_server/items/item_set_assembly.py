"""Transactional assembly of explicitly qualified native item sets.

Authority, costs, outputs and optional objective provenance come from reviewed
server descriptors, never from client-submitted Lua, reward IDs or callback names.
"""
import struct

from .inventory_owner import lock_item_owner
from .simple_item_actions import _criterion, _equipped, _idle


def validate_input_metadata(metadata):
    """Preserve binding; reject state with no set-to-product inheritance law.

    Empty selection/observation records carry no enhancement. The assembly
    combines several physical inputs into a quest product, so a conversion's
    singleton-main inheritance contract cannot be reused here.
    """
    for table, row in metadata.items():
        if table == "inventory_item_bindings":
            continue  # The transaction inherits effective binding below.
        if table == "inventory_item_elements" and (
            row["damage_elements"] == 0 and row["resistance_elements"] == 0
        ):
            continue
        if table == "inventory_item_recycling_state" and (
            row["unidentified"] is False and row["socketed"] is False
        ):
            continue
        raise ValueError(
            "Assembly input metadata has no qualified inheritance contract"
        )


def assemble(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight,
    document,
    plan,
    source_sha256,
    policy,
    authority_table,
    availability,
    native_map_id=None,
    material_matrix=None,
    eligibility=None,
    settlement=None,
):
    """Consume one exact physical set and grant its qualified typed output.

    The selected source UID is always among the set debits. All inputs are
    actual owned bag items, never company heroes, temporary or quest projections.
    Every source-specific option remains protected until inheritance is proven.
    """
    if material_matrix is not None:
        return _assemble_material_matrix(
            store,
            account_id,
            generation,
            character_id,
            body,
            in_fight=in_fight,
            document=document,
            plan=plan,
            source_sha256=source_sha256,
            policy=policy,
            authority_table=authority_table,
            availability=availability,
            material_matrix=material_matrix,
            eligibility=eligibility,
            settlement=settlement,
        )
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Assemble these item sets outside combat")
    if authority_table not in (
        "native_captain_map_item_actions",
        "native_journal_part_item_actions",
    ):
        raise ValueError("Unsupported item-set assembly authority")
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Invalid native item-set assembly grammar")
    action_id, uid = struct.unpack(">iq", body)
    if action_id != plan["action_id"] or uid <= 0:
        raise ValueError("Invalid native item-set assembly source")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        if owner_id != character_id:
            raise ValueError("Select the character carrying the complete item set")
        _idle(db, owner_id, store.now())
        source = db.execute(
            "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container "
            "AND c.character_id=i.character_id WHERE i.uid=%s AND i.character_id=%s FOR UPDATE OF i",
            (uid, owner_id),
        ).fetchone()
        if (
            source is None
            or source["reference"] != plan["item_ref"]
            or source["quantity"] < 1
        ):
            raise ValueError("The selected item does not match this native action")
        rule = db.execute(
            f"SELECT * FROM {authority_table} WHERE item_ref=%s", (source["reference"],)
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["policy"] != policy
            or rule["source_sha256"] != source_sha256
            or document["policy"] != policy
        ):
            raise ValueError("The item-set assembly policy has changed")
        from .haven_bag_furniture_knowledge import _rules

        active = _rules().get(source["reference"], {})
        if (
            active.get("use_action_class") != "bIn"
            or active.get("use_action_id") != action_id
        ):
            raise ValueError(
                "The item-set action differs from the active native catalog"
            )
        availability(db, document)
        character = store.character(account_id, owner_id, db)
        if not _criterion(
            store, db, account_id, character, plan["criterion"], native_map_id
        ):
            raise ValueError("Collect every required item before assembling this set")
        rows = list(
            db.execute(
                "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container "
                "AND c.character_id=i.character_id WHERE i.character_id=%s AND i.reference=ANY(%s) "
                "AND i.quantity>0 ORDER BY i.uid FOR UPDATE OF i",
                (owner_id, document["input_references"]),
            )
        )
        chosen = {source["reference"]: source}
        for item in rows:
            chosen.setdefault(item["reference"], item)
        if set(chosen) != set(document["input_references"]):
            raise ValueError(
                "The complete item set must be in this character's actual bags"
            )
        costs = sorted(chosen.values(), key=lambda item: item["uid"])
        from wakfu_server.item_custody_metadata import snapshot_many

        metadata = snapshot_many(db, [item["uid"] for item in costs])
        for item in costs:
            if _equipped(character, item["uid"]):
                raise ValueError("Unequip all assembly inputs first")
            validate_input_metadata(metadata[item["uid"]])
        from wakfu_server.combat_drop_delivery import _binding_rows, _effective_bound

        bindings = _binding_rows(db, costs)
        bound = any(
            _effective_bound(dict(item, bound=bindings.get(item["uid"], False)))
            for item in costs
        )
        packets = []
        for item in costs:
            if item["quantity"] == 1:
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                    (item["uid"], owner_id),
                )
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                    (item["uid"], owner_id),
                )
            packets.append((12470, struct.pack(">qh", item["uid"], -1)))
        from .item_action_delivery import grant_outputs

        outcome = grant_outputs(
            store,
            db,
            account_id,
            generation,
            character,
            {int(ref): quantity for ref, quantity in document["products"].items()},
            force_bound=bound,
        )
        from psycopg.types.json import Jsonb

        binding = document.get("mission_binding")
        observed_running = False
        if binding is not None:
            from wakfu_server.achievements import storage

            state = storage.load_locked(db, owner_id)
            observed_running = binding["definition_id"] in state["running"]
        fact = dict(
            kind="item_set_assembled",
            action_id=action_id,
            source_uid=uid,
            inputs=[
                dict(uid=item["uid"], reference=item["reference"], quantity=1)
                for item in costs
            ],
            products=document["products"],
            group_id=document.get("group_id", "captain_maps"),
            binding_inherited=bound,
            native_objective_binding=binding,
            mission_running_at_assembly=observed_running,
            mission_effect=(
                "qualified_already_running_receipt_adapter"
                if binding and observed_running and character["level"] >= 178
                else "deferred_unqualified_completion_engine"
                if binding
                else "none"
            ),
        )
        if binding is not None:
            fact["assembly_real_level"] = character["level"]
        receipt = db.execute(
            "INSERT INTO item_set_assembly_receipts(account_id,character_id,source_uid,policy,fact) "
            "VALUES(%s,%s,%s,%s,%s) RETURNING id",
            (account_id, owner_id, uid, policy, Jsonb(fact)),
        ).fetchone()
        mission = dict(packets=[], xp_changed=False, applied=False)
        if binding is not None:
            from wakfu_server.achievements.mission_assembly import settle

            mission = settle(db, store, character, receipt["id"])
            outcome["character"] = store.character(account_id, owner_id, db)
        return dict(
            outcome,
            packets=packets + outcome["packets"] + mission["packets"],
            native_class="bIn",
            applied=True,
            consumed=len(costs),
            source_consumed=1,
            source_uid=uid,
            source_reference=source["reference"],
            consumed_uids=[item["uid"] for item in costs],
            products={
                int(ref): quantity for ref, quantity in document["products"].items()
            },
            assembly_policy=policy,
            binding_inherited=bound,
            assembly_fact=fact,
            assembly_receipt_id=receipt["id"],
            mission_result=mission,
            xp_changed=mission["xp_changed"],
            mission_packets=mission["packets"],
        )


def _assemble_material_matrix(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight,
    document,
    plan,
    source_sha256,
    policy,
    authority_table,
    availability,
    material_matrix,
    eligibility,
    settlement,
):
    """Configured retained-tool assembly, authenticated and committed once.

    Quantities and reconstructed choices belong to the pinned server policy.
    Client action bodies carry only their original action/source identity.
    """
    from psycopg.types.json import Jsonb
    from wakfu_server.item_custody_metadata import snapshot_many
    from wakfu_server.combat_drop_delivery import _binding_rows, _effective_bound
    from .item_action_delivery import grant_outputs

    if type(in_fight) is not bool or in_fight:
        raise ValueError("Assemble these materials outside combat")
    if (
        authority_table != "configured_scenario_assembly_actions"
        or document.get("preserve_source") is not True
        or not callable(eligibility)
        or not callable(settlement)
        or not isinstance(material_matrix, dict)
        or not material_matrix
        or any(
            type(ref) is not int or ref <= 0 or type(qty) is not int or qty <= 0
            for ref, qty in material_matrix.items()
        )
        or plan["item_ref"] in material_matrix
    ):
        raise ValueError("Unqualified configured material assembly")
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Invalid native material assembly grammar")
    action_id, uid = struct.unpack(">iq", body)
    if action_id != plan["action_id"] or uid <= 0:
        raise ValueError("Invalid native material assembly source")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (uid,)
        )
        if owner_id != character_id:
            raise ValueError("Select the character carrying this assembly tool")
        _idle(db, owner_id, store.now())
        source = db.execute(
            "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container "
            "AND c.character_id=i.character_id WHERE i.uid=%s AND i.character_id=%s FOR UPDATE OF i",
            (uid, owner_id),
        ).fetchone()
        if (
            source is None
            or source["reference"] != plan["item_ref"]
            or source["quantity"] < 1
        ):
            raise ValueError("The assembly source does not match the native action")
        rule = db.execute(
            "SELECT * FROM configured_scenario_assembly_actions WHERE item_ref=%s",
            (source["reference"],),
        ).fetchone()
        if (
            rule is None
            or rule["action_id"] != action_id
            or rule["policy"] != policy
            or rule["source_sha256"] != source_sha256
            or rule["descriptor"] != document
        ):
            raise ValueError("The configured scenario assembly authority has changed")
        from .haven_bag_furniture_knowledge import _rules

        native = _rules().get(source["reference"], {})
        if (
            native.get("use_action_class") != "bIn"
            or native.get("use_action_id") != action_id
        ):
            raise ValueError(
                "Assembly action differs from the active native item catalog"
            )
        character = store.character(account_id, owner_id, db)
        if _equipped(character, uid):
            raise ValueError("Unequip the assembly tool first")
        previous = db.execute(
            "SELECT * FROM scenario_assembly_receipts WHERE character_id=%s "
            "AND definition_id=%s AND objective_id=%s",
            (owner_id, document["definition_id"], document["objective_id"]),
        ).fetchone()
        if previous is not None:
            if previous["account_id"] != account_id or previous["policy"] != policy:
                raise ValueError("Assembly receipt conflicts with its owner or policy")
            return dict(
                character=character,
                packets=[],
                applied=False,
                consumed=0,
                xp_changed=False,
                native_class="bIn",
                assembly_receipt_id=previous["id"],
            )
        context = eligibility(db, store, character, document)
        # Output capacity is checked before debit; any later failure also rolls
        # back source quantities, objective changes and receipt together.
        availability(db, document, character)
        rows = list(
            db.execute(
                "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container "
                "AND c.character_id=i.character_id WHERE i.character_id=%s AND i.reference=ANY(%s) "
                "AND i.quantity>0 ORDER BY i.uid FOR UPDATE OF i",
                (owner_id, list(material_matrix)),
            )
        )
        remaining, costs = dict(material_matrix), []
        for item in rows:
            quantity = min(remaining[item["reference"]], item["quantity"])
            if quantity:
                costs.append((item, quantity))
                remaining[item["reference"]] -= quantity
        if any(remaining.values()):
            raise ValueError(
                "The exact assembly materials must be in the selected character bags"
            )
        metadata = snapshot_many(db, [item["uid"] for item, _ in costs])
        for item, _ in costs:
            if _equipped(character, item["uid"]):
                raise ValueError("Unequip assembly materials first")
            validate_input_metadata(metadata[item["uid"]])
        bindings = _binding_rows(db, [item for item, _ in costs])
        bound = any(
            _effective_bound(dict(item, bound=bindings.get(item["uid"], False)))
            for item, _ in costs
        )
        packets = []
        for item, quantity in costs:
            if item["quantity"] == quantity:
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                    (item["uid"], owner_id),
                )
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s AND character_id=%s",
                    (quantity, item["uid"], owner_id),
                )
            packets.append((12470, struct.pack(">qh", item["uid"], -quantity)))
        products = {
            int(ref): quantity for ref, quantity in document["products"].items()
        }
        outcome = grant_outputs(
            store, db, account_id, generation, character, products, force_bound=bound
        )
        fact = dict(
            action_id=action_id,
            source_uid=uid,
            source_reference=source["reference"],
            source_consumed=0,
            scenario_id=document["scenario_id"],
            policy=policy,
            inputs=[
                dict(uid=item["uid"], reference=item["reference"], quantity=quantity)
                for item, quantity in costs
            ],
            products=document["products"],
            binding_inherited=bound,
            eligibility=context,
        )
        receipt = db.execute(
            "INSERT INTO scenario_assembly_receipts(account_id,character_id,source_uid,definition_id,"
            "objective_id,policy,fact) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                account_id,
                owner_id,
                uid,
                document["definition_id"],
                document["objective_id"],
                policy,
                Jsonb(fact),
            ),
        ).fetchone()
        mission = settlement(db, store, character, document, receipt["id"], context)
        current = store.character(account_id, owner_id, db)
        notification = (
            13411,
            struct.pack(">BiiB", 0, document["event_id"], document["scenario_id"], 0),
        )
        return dict(
            outcome,
            character=current,
            packets=packets + outcome["packets"] + [notification] + mission["packets"],
            native_class="bIn",
            applied=True,
            consumed=sum(material_matrix.values()),
            source_consumed=0,
            source_uid=uid,
            source_reference=source["reference"],
            products=products,
            assembly_policy=policy,
            assembly_fact=fact,
            assembly_receipt_id=receipt["id"],
            mission_result=mission,
            xp_changed=mission["xp_changed"],
        )
