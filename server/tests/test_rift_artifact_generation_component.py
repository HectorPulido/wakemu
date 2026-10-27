"""Native artifact constructor/choice component; not a full Rift/class Ready.

One synthetic flat arena and genuine owned PC/NPC snapshots exercise all58
original prototypes, paid contact, paired native effects and actual successor
registration. SQL files supply the policy; enabling is local to this preview.
"""
from copy import deepcopy
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch


class RiftArtifactGenerationComponentTests(unittest.TestCase):
    @staticmethod
    def native_policy():
        migrations = Path(__file__).resolve().parents[1] / "migrations"
        baseline = (migrations / "312_rift_native_gameplay_sources.sql").read_text()
        native = json.loads(re.search(r"\n'(\{.*\})'::jsonb", baseline).group(1))
        updates = (migrations / "315_rift_scoped_native_gameplay.sql").read_text()
        for encoded in re.findall(r"'(\{[^']+\})'::jsonb", updates):
            value = json.loads(encoded)
            if "rarity_weights" in value:
                native["artifacts"].update(value)
            elif value.get("source_kind") == "native_context_area_ref":
                native["artifacts"]["producer"] = value
            elif value.get("policy") == "wakemu.rift.ultimate-encounter-roles.v1":
                native["encounter_roles"] = value
        native["enabled"] = True
        native["enabled_types"] = ["ULTIMATE_INFINITE_WAVE"]
        native["artifacts"]["enabled"] = True
        return native

    def test_all_native_prototypes_paid_pairs_successor_leftovers_and_rollback(self):
        from tools.sublimation_semantic_fixture import build_fixture
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope
        from wakfu_server.combat_random_transaction import rollback_external_rng
        from wakfu_server.combat_value_transfer import transfer_value_context
        from wakfu_server.combat_execution_context import constructed_execution_context
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.monsters import owned_instance
        from wakfu_server.rift_encounter_roles import roles_for_catalog
        from wakfu_server.rift_artifact_generation import spawn_artifacts
        from wakfu_server.rift_native_gameplay import (
            artifact_contact_eligible,
            distribute_unclaimed_artifacts,
            install_wave_state,
        )
        from wakfu_server.rift_npc_creation import install_native_wave
        from wakfu_server.rift_wave_initialization import initialize_registered_wave

        manifest = os.environ.get("WAKFU_RIFT_ARTIFACT_MANIFEST")
        if not manifest:
            raise RuntimeError("Explicit source-pinned Rift artifact manifest required")
        native = self.native_policy()
        variant = os.environ.get("WAKFU_RIFT_ARTIFACT_VARIANT", "all")
        if variant not in ("all", "remaining_flow"):
            raise ValueError("Unknown strict Rift artifact component variant")
        template_reference = native["artifacts"]["producer"][
            "template_effect_reference"
        ]
        catalog = dict(
            type="ULTIMATE_INFINITE_WAVE", map_id=1134, wave_id=1, species_refs=[5525]
        )
        wave_policy = dict(
            policy_kind="local_dev_not_official",
            enabled=True,
            max_members=6,
            turn_budget=40,
            starting_wave=1,
            classic_wave_size=2,
            ultimate_wave_size=2,
            selection="uniform_with_replacement",
            scaling="native_base_grade",
            rewards="callback_only",
            native_gameplay=native,
        )
        roles = roles_for_catalog(catalog, wave_policy, monster_references=(5525,))
        # Four reachable free arms; NPC constructor cells are separate islands.
        # This declared test topology guarantees two real picks cost exactly3MP.
        center = (0, 0, 0)
        arms = {(-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0)}
        fixture = build_fixture(
            27152,
            manifest,
            constructor_roles=roles,
            terrain_cells=arms | {center, (3, 0, 0), (3, 1, 0)},
        )
        source = fixture.fight
        source.rift_wave_state = dict(
            instance_id=9,
            wave=1,
            turn_budget=40,
            wave_actor_ids=[-200],
            catalog=catalog,
            policy=wave_policy,
            seed="artifact-component",
            world_group_id=source.id,
        )
        source.rift_monsters = deepcopy(fixture.monster_sources)
        initial_dispatcher, _ = fixture.dispatcher_for(source)
        self.assertTrue(
            install_wave_state(initial_dispatcher, actor_ids=(-200,), wave=1)
        )
        self.assertTrue(
            any(
                entry.reference == 6807 and entry.level == 1
                for entry in source.actors[-200].state_ledger.entries
            )
        )
        del initial_dispatcher
        rng = fixture.factory.transaction_rng
        source_bytes, rng_before = snapshot(source), rng.getstate()
        references = sorted(
            ref for pool in native["artifacts"]["pools"].values() for ref in pool
        )
        self.assertEqual(len(references), 58)
        constructed, failed_plan, consumer_proofs = set(), {}, []
        if variant == "remaining_flow":
            proof_path = Path(os.environ["WAKFU_RIFT_ARTIFACT_QUALIFIED_RECEIPT"])
            proof_bytes = proof_path.read_bytes()
            self.assertEqual(
                hashlib.sha256(proof_bytes).hexdigest(),
                os.environ["WAKFU_RIFT_ARTIFACT_QUALIFIED_RECEIPT_SHA256"],
            )
            proof = json.loads(proof_bytes)
            self.assertEqual(
                proof["status"], "native58_private_component_consumers_qualified"
            )
            original_manifest_bytes = Path(
                os.environ["WAKFU_RIFT_ARTIFACT_QUALIFIED_MANIFEST"]
            ).read_bytes()
            self.assertEqual(
                hashlib.sha256(original_manifest_bytes).hexdigest(),
                proof["manifest_sha256"],
            )
            original_manifest = json.loads(original_manifest_bytes)
            self.assertEqual(
                original_manifest["revision"], fixture.dataset.manifest["revision"]
            )
            self.assertEqual(
                original_manifest["semantic"]["published_document_inventory"]["sha256"],
                fixture.dataset.manifest["semantic"]["published_document_inventory"][
                    "sha256"
                ],
            )
            self.assertEqual(
                proof["actual_actor_roles"], [roles.player_team, roles.npc_team]
            )
            self.assertFalse(proof["world_commit_qualified"])
            self.assertFalse(proof["class_ready_qualified"])
            self.assertEqual(len(proof["prototypes"]), 58)
            self.assertEqual(
                {row["reference"] for row in proof["prototypes"]}, set(references)
            )
            from wakfu_server.combat_effect_area import native_effect_areas

            definitions = native_effect_areas()
            for row in proof["prototypes"]:
                self.assertTrue(row["native843_consumed"] and row["receipt_complete"])
                self.assertEqual(row["level"], source.actors[7].effective_level)
                self.assertIn(row["native304_status"], ("completed", "no_effect"))
                if row["native304_status"] == "no_effect":
                    self.assertTrue(row["state_existed_before"])
                pending, seen, carriers = (
                    list(definitions[str(row["reference"])]["effect_ids"]),
                    set(),
                    [],
                )
                while pending:
                    reference = pending.pop()
                    if reference in seen:
                        continue
                    seen.add(reference)
                    definition = fixture.compiled.effects[str(reference)]
                    if definition["effect_class"] == 304:
                        carriers.append(reference)
                    pending.extend(definition.get("children", ()))
                self.assertEqual(carriers, [row["native304"]])
                self.assertEqual(
                    effect_profile(
                        fixture.compiled.effects[str(carriers[0])], row["level"]
                    )["parameters"][0],
                    row["native_state_reference"],
                )
            constructed.update(references)

        @rollback_external_rng
        def attempt(*, mode, rng):
            preview = deepcopy(source)
            dispatcher, packets = fixture.dispatcher_for(preview)
            self.assertIs(dispatcher.rift_artifact_rng, rng)
            # Bind only the immutable metadata dependency to this same factory;
            # all real pin/digest/custody/retention checks execute unchanged.
            with patch(
                "wakfu_server.combat_server_spell.compiled_runtime_catalog",
                return_value=fixture.compiled,
            ):
                if mode == "constructors":
                    original = deepcopy(dispatcher.effects[str(template_reference)])
                    for reference in references:
                        # Independent action previews of ONE admitted fixture.
                        # Earlier original artifacts can legitimately kill this
                        # low-level NPC; never heal/revive that retired candidate.
                        # The immutable baseline already contains native6807.
                        del preview, dispatcher, packets
                        gc.collect()
                        preview = deepcopy(source)
                        dispatcher, packets = fixture.dispatcher_for(preview)
                        before = set(preview.native_effect_areas)
                        self.assertTrue(
                            dispatcher.execute(
                                EffectInvocation(
                                    template_reference,
                                    preview.actors[7].effective_level,
                                    7,
                                    None,
                                    (-1, 0, 0),
                                    native_context_hex=transfer_value_context(
                                        constructed_execution_context().payload(),
                                        reference,
                                    ).hex(),
                                    native_retained_container={"present": False},
                                )
                            )
                        )
                        created = set(preview.native_effect_areas) - before
                        self.assertEqual(len(created), 1)
                        row = preview.native_effect_areas[created.pop()]
                        self.assertEqual(row["reference"], reference)
                        self.assertEqual(
                            row["level"], preview.actors[7].effective_level
                        )
                        self.assertEqual(row["native_area_contract"], "faM")
                        definition = dispatcher.native_area_events._definition(row)
                        pending, seen, carriers = (
                            list(definition["effect_ids"]),
                            set(),
                            [],
                        )
                        while pending:
                            effect_id = pending.pop()
                            if effect_id in seen:
                                continue
                            seen.add(effect_id)
                            leaf = dispatcher.effects[str(effect_id)]
                            if leaf["effect_class"] == 304:
                                carriers.append(effect_id)
                            pending.extend(leaf.get("children", ()))
                        self.assertEqual(len(carriers), 1)
                        state_reference = effect_profile(
                            dispatcher.effects[str(carriers[0])], row["level"]
                        )["parameters"][0]
                        existing = any(
                            entry.reference == state_reference
                            for entry in preview.actors[-200].state_ledger.entries
                        )
                        trace = []
                        try:
                            with combat_diagnostic_scope(
                                lambda **item: trace.append(item), limit=512
                            ):
                                self.assertTrue(
                                    dispatcher.native_area_events.assign_artifact(
                                        row["uid"], -200
                                    )
                                )
                        except Exception as error:
                            context = dict(
                                reference=reference,
                                qualified_before=len(consumer_proofs),
                                area_uid=row["uid"],
                                area_live=row["uid"] in preview.native_effect_areas,
                                recipient_hp=preview.actors[-200].hp,
                                recipient_max_hp=preview.actors[-200].max_hp,
                                recipient_in_play=preview._in_play(
                                    preview.actors[-200]
                                ),
                            )
                            output = os.environ.get("WAKFU_RIFT_ARTIFACT_RECEIPT")
                            if output:
                                destination = Path(output)
                                destination.parent.mkdir(parents=True, exist_ok=True)
                                destination.write_text(
                                    json.dumps(
                                        dict(
                                            status="native58_component_consumers_partial",
                                            manifest_sha256=hashlib.sha256(
                                                Path(manifest).read_bytes()
                                            ).hexdigest(),
                                            prototypes=consumer_proofs,
                                            failed_context=context,
                                            error_type=type(error).__name__,
                                            error=str(error),
                                        ),
                                        indent=2,
                                    )
                                    + "\n"
                                )
                            error.add_note(
                                "Native artifact prototype context: "
                                + json.dumps(context, sort_keys=True)
                            )
                            raise
                        applied = [
                            item
                            for item in trace
                            if item.get("event") == "combat_effect"
                            and item.get("effect_reference") == carriers[0]
                            and item.get("target_id") == -200
                            and item.get("status") in ("completed", "no_effect")
                        ]
                        self.assertTrue(
                            applied, "original304 must execute, not only subscribe/skip"
                        )
                        self.assertFalse(
                            any(
                                item.get("effect_reference") == carriers[0]
                                and (
                                    item.get("status", "").startswith("skipped")
                                    or item.get("status") == "subscribed_waiting_event"
                                )
                                for item in trace
                            )
                        )
                        if applied[-1]["status"] == "no_effect":
                            self.assertTrue(
                                existing,
                                "native no-op requires an already present original state",
                            )
                        self.assertTrue(
                            any(
                                entry.reference == state_reference
                                for entry in preview.actors[-200].state_ledger.entries
                            )
                        )
                        self.assertTrue(
                            any(
                                item.get("effect_class") == 843
                                and item.get("status") == "completed"
                                for item in trace
                            )
                        )
                        self.assertNotIn(row["uid"], preview.native_effect_areas)
                        receipt = preview.native_artifact_activation_receipts[
                            str(row["uid"])
                        ]
                        self.assertTrue(receipt["complete"])
                        self.assertEqual(receipt["reference"], reference)
                        self.assertEqual(receipt["origin"], "assignment")
                        self.assertEqual(receipt["recipient_team"], roles.npc_team)
                        consumer_proofs.append(
                            dict(
                                reference=reference,
                                area_uid=row["uid"],
                                level=row["level"],
                                native304=carriers[0],
                                native304_status=applied[-1]["status"],
                                native_state_reference=state_reference,
                                state_existed_before=existing,
                                native843_consumed=True,
                                receipt_complete=True,
                            )
                        )
                        constructed.add(reference)
                    self.assertEqual(
                        dispatcher.effects[str(template_reference)], original
                    )
                    self.assertEqual(len(consumer_proofs), 58)
                    output = os.environ.get("WAKFU_RIFT_ARTIFACT_RECEIPT")
                    if output:
                        target = Path(output)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(
                            json.dumps(
                                dict(
                                    status="native58_private_component_consumers_qualified",
                                    manifest_sha256=hashlib.sha256(
                                        Path(manifest).read_bytes()
                                    ).hexdigest(),
                                    template_effect_reference=template_reference,
                                    prototypes=consumer_proofs,
                                    actual_actor_roles=[
                                        roles.player_team,
                                        roles.npc_team,
                                    ],
                                    isolation="one_admitted_fixture_independent_transaction_previews",
                                    class_ready_qualified=False,
                                    world_commit_qualified=False,
                                ),
                                indent=2,
                            )
                            + "\n"
                        )
                    raise ValueError("discard native prototype component")
                if mode == "reject":
                    checkpoint, random_state = snapshot(preview), rng.getstate()
                    dispatcher.rift_artifact_rng = None
                    with self.assertRaisesRegex(ValueError, "accepted transaction RNG"):
                        spawn_artifacts(dispatcher, wave=1)
                    self.assertEqual(snapshot(preview), checkpoint)
                    self.assertEqual(rng.getstate(), random_state)
                    dispatcher.rift_artifact_rng = rng
                ids = spawn_artifacts(dispatcher, wave=1)
                self.assertEqual(len(ids), 4)
                self.assertEqual(
                    {tuple(preview.native_effect_areas[uid]["cell"]) for uid in ids},
                    arms,
                )
                group = preview.rift_wave_state["native_artifact_groups"]["1"]
                if mode == "reject":
                    failed_plan.update(
                        deepcopy(
                            preview.rift_wave_state["native_artifact_generation"]["1"]
                        )
                    )
                    raise ValueError("discard generated native group")
                if mode in ("picks", "inheritance"):
                    if mode == "picks":
                        self.assertEqual(
                            preview.rift_wave_state["native_artifact_generation"]["1"],
                            failed_plan,
                        )
                    checkpoint, state = snapshot(preview), rng.getstate()
                    self.assertEqual(spawn_artifacts(dispatcher, wave=1), ids)
                    self.assertEqual(snapshot(preview), checkpoint)
                    self.assertEqual(rng.getstate(), state)
                    row = preview.native_effect_areas[ids[0]]
                    self.assertFalse(
                        artifact_contact_eligible(preview, area_row=row, actor_id=-200)
                    )
                    registrations = getattr(
                        preview, "native_summon_registrations", None
                    )
                    preview.native_summon_registrations = {7: {"untrusted": True}}
                    self.assertFalse(
                        artifact_contact_eligible(preview, area_row=row, actor_id=7)
                    )
                    if registrations is None:
                        del preview.native_summon_registrations
                    else:
                        preview.native_summon_registrations = registrations
                    moves = []
                    for index in range(2):
                        uid = group["remaining"][0]
                        cell = tuple(preview.native_effect_areas[uid]["cell"])
                        path = [cell] if index == 0 else [center, cell]
                        try:
                            moves.append(
                                preview.move(
                                    3,
                                    7,
                                    path,
                                    step_callback=lambda f, actor, old, new: dispatcher.native_area_events.movement(
                                        actor.id, from_cell=old, to_cell=new
                                    ),
                                )
                            )
                        except ValueError as error:
                            error.add_note(
                                str(
                                    dict(
                                        mode=mode,
                                        pick=index,
                                        path=path,
                                        position=preview.actors[7].position,
                                        ap=preview.actors[7].ap,
                                        mp=preview.actors[7].mp,
                                        artifacts=preview.rift_wave_state[
                                            "native_artifact_generation"
                                        ]["1"]["references"],
                                    )
                                )
                            )
                            raise
                    self.assertEqual(sum(move["cost"] for move in moves), 3)
                    self.assertEqual(group["choices_made"], 2)
                    self.assertEqual(group["remaining"], [])
                    self.assertEqual(len(group["assignments"]), 2)
                    for item in group["assignments"]:
                        for uid, origin, team in (
                            (item["collected"], "contact", roles.player_team),
                            (item["opponent"], "assignment", roles.npc_team),
                        ):
                            receipt = preview.native_artifact_activation_receipts[
                                str(uid)
                            ]
                            self.assertTrue(receipt["complete"])
                            self.assertEqual(receipt["origin"], origin)
                            self.assertEqual(receipt["recipient_team"], team)
                            self.assertNotIn(uid, preview.native_effect_areas)
                    if mode == "picks":
                        return
                # These are original native artifact outcomes, captured before
                # death. No arbitrary species innate is inheritance authority.
                picked_states = {
                    entry.reference: entry.level
                    for entry in preview.actors[-200].state_ledger.entries
                    if entry.reference != 6807
                }
                sources = deepcopy(fixture.monster_sources)

                def advance(next_wave):
                    old_ids = tuple(preview.rift_wave_state["wave_actor_ids"])
                    old_group = preview.rift_wave_state["native_artifact_groups"][
                        str(next_wave - 1)
                    ]
                    for uid in old_ids:
                        if preview._in_play(preview.actors[uid]):
                            preview.apply_effect_damage(7, uid, preview.actors[uid].hp)
                    self.assertIsNotNone(preview.rift_wave_state["pending_wave"])
                    born = [
                        owned_instance(
                            5525,
                            1,
                            uid,
                            map_id=1134,
                            instance_id=9,
                            x=3,
                            y=y,
                            z=0,
                            team=1,
                        )
                        for uid, y in (
                            (-200 - (next_wave - 1) * 2 + 1, 0),
                            (-200 - (next_wave - 1) * 2, 1),
                        )
                    ]
                    sources.update({row["id"]: row for row in born})
                    preview.rift_monsters = deepcopy(sources)

                    def initialized(current, actors, monsters):
                        from wakfu_server.rift_artifact_inheritance import (
                            inherit_artifact_grants,
                        )

                        live, outbox = fixture.dispatcher_for(
                            current, monster_sources=sources
                        )
                        initialize_registered_wave(
                            live, actors=actors, monsters=monsters, player_ids=(7,)
                        )
                        self.assertEqual(old_group["remaining"], [])
                        self.assertEqual(
                            len(
                                current.rift_wave_state["native_artifact_groups"][
                                    str(next_wave)
                                ]["remaining"]
                            ),
                            4,
                        )
                        inheritance = current.rift_wave_state[
                            "native_artifact_inheritance"
                        ][str(next_wave)]
                        self.assertTrue(inheritance["complete"])
                        self.assertEqual(
                            inheritance["actors"], [actor.id for actor in actors]
                        )
                        if mode == "inheritance":
                            self.assertEqual(
                                len(inheritance["grants"]), 2 if next_wave < 4 else 4
                            )
                            if next_wave == 2:
                                # A fresh native5525 has no artifact innates;
                                # the picked states come only from consumed choices.
                                for actor in actors:
                                    actual = {
                                        entry.reference: entry.level
                                        for entry in actor.state_ledger.entries
                                    }
                                    for reference, level in picked_states.items():
                                        self.assertEqual(actual.get(reference), level)
                        checkpoint, state = snapshot(current), rng.getstate()
                        self.assertFalse(
                            inherit_artifact_grants(
                                live,
                                actor_ids=tuple(actor.id for actor in actors),
                                wave=next_wave,
                            )
                        )
                        self.assertFalse(
                            distribute_unclaimed_artifacts(live, before_wave=next_wave)
                        )
                        self.assertEqual(snapshot(current), checkpoint)
                        self.assertEqual(rng.getstate(), state)
                        return tuple(outbox)

                    install_native_wave(
                        preview,
                        born,
                        initialize_actor=lambda *_: (),
                        initialize_wave=initialized,
                    )
                    self.assertEqual(preview.rift_wave_state["wave"], next_wave)
                    self.assertEqual(old_group["remaining"], [])
                    self.assertEqual(len(old_group["assignments"]), 2)
                    expected = (
                        "contact_pair"
                        if mode == "inheritance" and next_wave == 2
                        else "automatic_pair"
                    )
                    self.assertTrue(
                        all(
                            item["kind"] == expected
                            for item in old_group["assignments"]
                        )
                    )

                advance(2)
                if mode == "inheritance":
                    # Wave3 inherits the picked grants and receives wave2's
                    # genuine unclaimed native faM grants. Wave4 validates their
                    # real retained PL/history after native merging, not a sum
                    # of observed post-merge grades.
                    advance(3)
                    advance(4)
                    raise ValueError("discard inherited native waves")

        rejected_cases = [("reject", "discard generated native group")]
        if variant == "all":
            rejected_cases.insert(0, ("constructors", "discard native prototype"))
        for mode, message in rejected_cases:
            try:
                attempt(mode=mode, rng=rng)
            except ValueError as error:
                if message not in str(error):
                    self.fail(
                        "Unexpected original consumer failure: "
                        + str(error)
                        + "; "
                        + "; ".join(getattr(error, "__notes__", ()))
                    )
            else:
                self.fail(
                    "The native private component must deliberately reject after qualification"
                )
            self.assertEqual(snapshot(source), source_bytes)
            self.assertEqual(rng.getstate(), rng_before)
            gc.collect()
        self.assertEqual(constructed, set(references))
        # Extend the first paid-pick transaction through successor inheritance.
        # Do not reroll a second pick scenario after accepting unrelated draws:
        # original artifacts themselves may legitimately change movement stats.
        before_inheritance = rng.getstate()
        with self.assertRaisesRegex(ValueError, "discard inherited native waves"):
            attempt(mode="inheritance", rng=rng)
        self.assertEqual(snapshot(source), source_bytes)
        self.assertEqual(rng.getstate(), before_inheritance)
        gc.collect()
        attempt(mode="leftovers", rng=rng)
        self.assertEqual(snapshot(source), source_bytes)
