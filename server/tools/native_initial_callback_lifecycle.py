"""Bounded real turn lifecycle witnesses for native initial family426 callbacks."""
from copy import deepcopy


def source_plans(index, reference, spell):
    if index.get("schema") != "native-zero-range-constant-caller-index-v1":
        raise ValueError("Missing native callback index authority")
    rows = [r for r in index["rows"] if r["ref"] == reference]
    if len(rows) != 1:
        return []
    row = rows[0]
    if spell not in row["zero_range_owned_spell_ids"]:
        return []
    originals = {r["effect_id"]: r for r in index["constant_native_callers"]}
    triples = row["native_initial_state_triples"]
    if len(triples) % 3:
        raise ValueError("Malformed original native constructor")
    result = []
    for path in row["native_initialization"]["source_paths"]:
        if path["spell_id"] != spell or path["route_kind"] != "native426_cast_callback":
            continue
        ancestry = path["path"]
        if (
            not ancestry
            or ancestry[0][0] != "states"
            or ancestry[0][1] not in triples[::3]
            or ancestry[-1] != ["effects", path["callback_effect_id"]]
        ):
            raise ValueError(
                "Callback path is absent from original initial constructor"
            )
        record = originals.get(path["callback_effect_id"])
        if record is None or record["spell_id"] != spell or record["family"] != 426:
            raise ValueError("Missing exact original callback definition")
        native = record["native_definition"]
        parameters = native.get("parameter0_by_level")
        if (
            native.get("native_execution_mode") != 2
            or native.get("parameters") != [float(spell), 0.0]
            or not parameters
            or set(parameters) != {spell}
        ):
            raise ValueError(
                "Callback spell reference is not a constant native producer"
            )
        subscriptions = path["native_subscriptions"]
        eligible = bool(subscriptions) and all(
            s["effect_class"] == 330
            and [(slot, ids) for slot, ids in enumerate(s["target_masks"]) if ids]
            in ([(5, [1001])], [(5, [1037])])
            for s in subscriptions
        )
        result.append(
            dict(
                reference=reference,
                spell_id=spell,
                callback_effect_id=path["callback_effect_id"],
                native_initial_state_triples=list(triples),
                source_path=deepcopy(ancestry),
                subscriptions=deepcopy(subscriptions),
                callback_criterion=native["criteria"],
                normal_turn_lifecycle_supported=eligible,
                ordinary_cast_eligibility_override=False,
                admission=False,
            )
        )
    return result


def actor_values(fight):
    return {
        identity: dict(
            hp=actor.hp,
            states=[(e.reference, e.level) for e in actor.state_ledger.entries],
        )
        for identity, actor in fight.actors.items()
    }


def run_lifecycle(
    fight,
    character,
    monsters,
    deck,
    *,
    plan,
    caster_id,
    observer=None,
    max_boundaries=12
):
    """Commit real start/end transactions; never call the requested spell directly."""
    from native_triggered_spell_observation import TriggeredSpellObservations

    if type(caster_id) is not int or caster_id == 0:
        raise ValueError("Missing actual callback caster identity")
    if observer is None:
        observer = TriggeredSpellObservations()
    from random import Random
    from contextlib import ExitStack
    from unittest.mock import patch
    from wakfu_server.combat_triggered_spell_handler import NativeTriggeredSpellHandler
    from wakfu_server.combat_server_spell import (
        prepare_server_initialization,
        prepare_server_turn_start,
        prepare_server_turn_end,
    )
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_effective_control import effective_server_controlled

    if (
        not plan["normal_turn_lifecycle_supported"]
        or type(max_boundaries) is not int
        or not 1 <= max_boundaries <= 24
    ):
        raise ValueError("Unsupported or unbounded callback lifecycle plan")
    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    ctor = receipts.get(caster_id)
    if (
        monsters[caster_id]["ref"] != plan["reference"]
        or ctor is None
        or ctor["raw_triples"] != plan["native_initial_state_triples"]
    ):
        raise ValueError("Actual placement constructor differs from callback ancestry")
    packets, boundaries = [], []
    original_init = NativeTriggeredSpellHandler.__init__
    with ExitStack() as stack:

        def initialize(handler, *args, **kwargs):
            original_init(handler, *args, **kwargs)
            stack.enter_context(observer.observe(handler))

        stack.enter_context(
            patch.object(NativeTriggeredSpellHandler, "__init__", initialize)
        )
        fight, initial = prepare_server_initialization(
            character,
            monsters,
            fight,
            character["account_id"],
            deck,
            action_id=1,
            rng=Random(0),
            fight_start=True,
            player_characters={character["id"]: character},
            deck_blobs={character["id"]: deck},
        )
        packets.extend(initial)
        for step in range(max_boundaries):
            if fight.phase != "active" or fight.current is None:
                break
            identity = fight.current.id
            packets.extend(RuntimeMessages(fight).turn_started())
            before = actor_values(fight)
            fight, started = prepare_server_turn_start(
                character,
                monsters,
                fight,
                deck,
                actor_id=identity,
                action_id=2 + step * 2,
                rng=Random(0),
            )
            packets.extend(started)
            boundaries.append(
                dict(
                    phase="start",
                    actor_id=identity,
                    turn_id=fight.turn_id,
                    table_turn=fight.native_table_turn,
                    before=before,
                    after=actor_values(fight),
                    packet_count=len(started),
                )
            )
            if fight.phase != "active" or fight.current is None:
                break
            fight, ended = prepare_server_turn_end(
                character,
                monsters,
                fight,
                deck,
                actor_id=identity,
                action_id=3 + step * 2,
                rng=Random(0),
            )
            packets.extend(ended)
            if fight.phase != "active" or fight.current is None:
                break
            actor = fight.actors[identity]
            if effective_server_controlled(fight, actor):
                fight.end_server_turn(identity, fight.turn_id)
            else:
                fight.end_turn(actor.owner_id, identity, actor.turn_count)
    delivered = observer.delivery_receipts(packets)
    selected = [
        r
        for r in delivered
        if r["effect_reference"] == plan["callback_effect_id"]
        and r["resolved_spell_id"] == plan["spell_id"]
        and r["caster_id"] == caster_id
    ]
    return fight, dict(
        plan=deepcopy(plan),
        boundaries=boundaries,
        triggered_delivery_receipts=selected,
        all_callback_receipts=delivered,
        committed_packet_ids=[p[0] for p in packets],
        ordinary_cast_attempts=0,
        ordinary_eligibility_override=False,
        book_admission=False,
        nested_spell_level=None,
    )


def main(argv=None):
    """Build bounded execution plans; gameplay runs through run_lifecycle API."""
    import argparse
    import hashlib
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--reference", type=int, required=True)
    parser.add_argument("--spell", type=int, required=True)
    parser.add_argument("--max-boundaries", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.max_boundaries <= 24:
        parser.error("max-boundaries must be between1 and24")
    if args.output.exists():
        parser.error("output already exists; preserve original evidence")
    raw = args.index.read_bytes()
    plans = source_plans(json.loads(raw), args.reference, args.spell)
    result = dict(
        schema="native-initial426-bounded-plan-v1",
        source_index_sha256=hashlib.sha256(raw).hexdigest(),
        reference=args.reference,
        spell_id=args.spell,
        max_boundaries=args.max_boundaries,
        plans=plans,
        execution_verified=False,
        ordinary_eligibility_override=False,
        admission=False,
        nested_spell_level=None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
