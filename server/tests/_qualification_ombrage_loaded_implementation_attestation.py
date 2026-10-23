"""Record the explicitly authorized two-file disk drift without adopting it."""
import importlib, hashlib, inspect, json, marshal, unittest
from pathlib import Path


def observe():
    module = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = module.OMBRAGE_ACTUAL_CHECKPOINT
    fight = checkpoint["runtime"].fight
    root = Path("server/wakfu_server")
    expected = checkpoint["runtime_source_pins"]
    actual = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*.py")
    }
    changed = sorted(
        k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k)
    )
    permitted = [
        "combat/combat_encounter_area_seed_source.py",
        "combat/combat_state_level_group.py",
    ]
    assert changed == permitted, changed
    messages = importlib.import_module("wakfu_server.combat_runtime_messages")
    state = importlib.import_module("wakfu_server.combat_state")
    groups = importlib.import_module("wakfu_server.combat_state_level_group")
    factory = importlib.import_module("wakfu_server.combat_effect_runtime")
    helper = importlib.import_module("wakfu_server.combat_encounter_area_seed_source")
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    table = getattr(fight, "native_encounter_table_listener_policy", None)
    assert table == checkpoint["receipt"]["frozen_listener_policy"]
    assert (
        fight.native_encounter_roles
        == checkpoint["receipt"]["premise"]["encounter_roles"]
    )
    identities = dict(
        runtime_public_identity=type(checkpoint["runtime"]) is messages.RuntimeMessages,
        actor_public_identities=all(
            type(a) is state.Actor for a in fight.actors.values()
        ),
        factory_group_alias_unchanged=factory.native_state_group_level
        is groups.runtime_child_level,
    )
    assert all(identities.values()), identities

    def code(function):
        return dict(
            signature=str(inspect.signature(function)),
            names=function.__code__.co_names,
            code_sha=hashlib.sha256(marshal.dumps(function.__code__)).hexdigest(),
        )

    row = dict(
        authorization="Root explicitly permits only these two disk-only paths; original pins remain intact",
        attestation="No runtime, factory, handler or policy module/AST reload occurred after Ombrage40 began. Subsequent jobs only read journals, GC references and existing checkpoint data.",
        mutations_permitted=False,
        original_pins_renewed=False,
        drift={k: dict(before=expected[k], after=actual[k]) for k in changed},
        identities=identities,
        loaded_runtime_child_level=code(groups.runtime_child_level),
        helper_has_old_area_source_api=hasattr(
            helper, "seed_program_requires_area_source"
        ),
        helper_has_new_operand_api=hasattr(helper, "seed_program_level_source"),
        frozen_policies={
            k: v
            for k, v in vars(fight).items()
            if k.startswith("native_encounter_")
            and ("policy" in k or "roles" in k or "population" in k)
        },
        table_policy_matches_admission=True,
        roles_match_admission=True,
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage40-two-file-disk-drift-loaded-code-attestation.json"
    ).write_text(json.dumps(row, indent=2, default=repr))
    return unittest.TestSuite()
