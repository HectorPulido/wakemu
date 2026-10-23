"""Explicit Wakemu lossless native-precursor crafting policy.

raw_cvj identifies the native precursor relationship, not an original server
inheritance algorithm. Compatible state is retained; unsupported state fails
before material debit. Ordinary resource sacrifice semantics are unchanged.
"""
import hashlib
import json


def _rich(metadata, reference):
    from .combat_drop_delivery import _template_bound

    for table, row in metadata.items():
        if table == "inventory_item_elements":
            if row["damage_elements"] or row["resistance_elements"]:
                return True
        elif table == "inventory_item_bindings":
            if row["template_reference"] != reference or (
                row["bound"] and not _template_bound(reference)
            ):
                return True
        elif table == "inventory_item_recycling_state":
            if row["unidentified"] is not False or row["socketed"] is not False:
                return True
        else:
            return True
    return False


def protected_ingredients(db, recipe, character):
    """Prefer valid ordinary materials over rich nonprecursor identities.

    The native request identifies ingredient references, not physical UIDs.
    Excluding unsupported rich candidates lets the existing deterministic
    planner use a later ordinary unit without sacrificing enhancement state.
    """
    from .item_custody_metadata import snapshot_many

    references = {row["item_id"] for row in recipe["ingredients"]}
    precursor = recipe.get("raw_cvj", 0)
    candidates = [
        row
        for row in character["inventory_items"]
        if row["reference"] in references and row["reference"] != precursor
    ]
    metadata = snapshot_many(db, [row["uid"] for row in candidates])
    return {
        row["uid"]
        for row in candidates
        if _rich(metadata[row["uid"]], row["reference"])
    }


def prepare(db, recipe, batch_count, character, material_plan):
    from .item_custody_metadata import snapshot_many
    from .combat_drop_delivery import _effective_bound
    from .conversion_item_actions import identified_contract
    from .item_action_delivery import validate_selections
    from .conversion_shard_policy import validate_target as validate_shards
    from .conversion_appearance_policy import validate_target as validate_appearance

    items = {row["uid"]: row for row in character["inventory_items"]}
    consumed = material_plan["consumed"]
    metadata = snapshot_many(db, [row["uid"] for row in consumed])
    precursor = recipe.get("raw_cvj", 0)
    rich = [
        row
        for row in consumed
        if _rich(metadata[row["uid"]], items[row["uid"]]["reference"])
    ]
    # Native-bound plain resources are ordinary ingredients. A bound equipment
    # precursor also passes its effective binding to the main output.
    for row in consumed:
        item = items[row["uid"]]
        if item["reference"] == precursor and row not in rich:
            binding = (
                metadata[row["uid"]]
                .get("inventory_item_bindings", {})
                .get("bound", False)
            )
            if _effective_bound(dict(item, bound=binding)):
                rich.append(row)
    if not rich:
        return {}
    if (
        type(precursor) is not int
        or precursor <= 0
        or sum(
            row["quantity"]
            for row in recipe["ingredients"]
            if row["item_id"] == precursor
        )
        != 1
    ):
        raise ValueError(
            "Rich crafting ingredients require an unambiguous native precursor"
        )
    from .equipment import RULES

    left = RULES.get(precursor)
    if left is None or not left.get("slots"):
        raise ValueError("Native crafting precursor lacks equipment slot authority")
    candidates = [
        row
        for row in recipe["products"]
        if row["quantity"] == 1
        and RULES.get(row["item_id"]) is not None
        and all(
            left.get(key) == RULES[row["item_id"]].get(key)
            for key in ("slots", "occupied_slots")
        )
    ]
    if len(candidates) != 1:
        raise ValueError(
            "Native crafting has no unambiguous compatible singleton main product"
        )
    target = candidates[0]["item_id"]
    outputs = []
    for consumed_row in rich:
        source = items[consumed_row["uid"]]
        state = metadata[source["uid"]]
        if source["reference"] != precursor:
            raise ValueError("Rich crafting ingredient is not the native precursor")
        output = {}
        if any(
            table in state
            for table in (
                "inventory_mounts",
                "inventory_pets",
                "inventory_item_companions",
                "random_item_use_counters",
            )
        ):
            raise ValueError("Native precursor state has no lossless crafting contract")
        observation = state.get("inventory_item_recycling_state")
        if observation is not None:
            # Recycling observations are not enhancement payloads, but they
            # still affect later recycling eligibility. Reuse the existing
            # native-domain check: the source and destination must have equal
            # template flags and physical slot domains, while shard state is
            # independently validated below.
            from .conversion_observation_policy import (
                validate_pair as validate_observation,
            )

            output["recycling_observation"] = validate_observation(
                precursor,
                target,
                {key: observation[key] for key in ("unidentified", "socketed")},
            )
        selection = state.get("inventory_item_elements")
        if selection and (
            selection["damage_elements"] or selection["resistance_elements"]
        ):
            plan = dict(
                item_ref=precursor, main_reference=target, products={str(target): 1}
            )
            identified_contract(plan)
            selected = {
                key: selection[key]
                for key in ("damage_elements", "resistance_elements")
            }
            validate_selections({precursor: 1}, {precursor: selected})
            validate_selections({target: 1}, {target: selected})
            output["selection"] = selected
        if "inventory_item_shards" in state:
            blob = bytes(state["inventory_item_shards"]["shard_state"])
            validate_shards(db, precursor, blob)
            validate_shards(db, target, blob)
            output["shards"] = blob.hex()
        if "inventory_item_appearances" in state:
            output["appearance"] = validate_appearance(
                db,
                precursor,
                target,
                state["inventory_item_appearances"]["appearance_ref"],
            )
        # A binding flag alone follows the already-supported inventory split
        # semantics. Individual socket/mask/appearance identities never clone.
        if output and (source["quantity"] != 1 or consumed_row["quantity"] != 1):
            raise ValueError(
                "Identified crafting precursor must be one complete physical unit"
            )
        binding = state.get("inventory_item_bindings", {})
        if binding and binding["template_reference"] != precursor:
            raise ValueError("Native precursor binding template differs")
        output["bound"] = _effective_bound(
            dict(source, bound=binding.get("bound", False))
        )
        output["source_uid"] = source["uid"]
        for unit in range(consumed_row["quantity"]):
            outputs.append(dict(output, source_unit=unit))
    if len(outputs) > batch_count:
        raise ValueError("Native precursor units exceed singleton main products")
    return {target: outputs}


def fingerprint(outputs):
    return hashlib.sha256(
        json.dumps(outputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def apply(db, item, state):
    """Save a prevalidated complete product state before its insertion packet."""
    from .combat_drop_delivery import _save_binding
    from .inventory_shards import save as save_shards

    if "selection" in state:
        selected = state["selection"]
        row = db.execute(
            "UPDATE inventory_item_elements SET damage_elements=%s,resistance_elements=%s WHERE uid=%s RETURNING uid",
            (selected["damage_elements"], selected["resistance_elements"], item["uid"]),
        ).fetchone()
        if row is None:
            raise ValueError("Missing typed crafting output elemental row")
        item.update(selected)
    if "shards" in state:
        blob = bytes.fromhex(state["shards"])
        save_shards(db, item["uid"], blob)
        item["shard_state"] = blob
    if "appearance" in state:
        db.execute(
            "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,%s)",
            (item["uid"], state["appearance"]),
        )
        item["appearance_ref"] = state["appearance"]
    if "recycling_observation" in state:
        observation = state["recycling_observation"]
        db.execute(
            "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,%s,%s)",
            (item["uid"], observation["unidentified"], observation["socketed"]),
        )
    _save_binding(db, item["uid"], item["reference"], state["bound"])
    item["bound"] = state["bound"]
