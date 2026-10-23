"""Bounded real paid attacks against original Ready-created totem actors."""
import json
from pathlib import Path
from random import Random
import unittest


class FulMoonPaidNativeTotemTests(unittest.TestCase):
    def test_original_paid_hammer_reaches_native_totem_damage_guards(self):
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        helper = FulMoonTalKashaNativeBootstrapTests()
        fight, scene, children = helper._started(
            3870, 185, 1056, reconstructed_fulmoon_scene
        )
        character, monsters, deck = helper.encounter_context
        self.assertEqual(fight.current.id, -200)
        identity = next(
            identity for identity, reference in children.items() if reference == 3993
        )
        target = fight.actors[identity]
        self.assertIn(4226, {entry.reference for entry in target.state_ledger.entries})
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_encounter_registered_programs import (
            registered_program_initializer,
        )
        from wakfu_server.combat_summon import SummonRegistration
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        for child in children:
            self.assertEqual(
                len(
                    fight.native_summon_registrations[child][
                        "server_post_registration_programs"
                    ]
                ),
                1,
            )
            self.assertIn(
                4226,
                {entry.reference for entry in fight.actors[child].state_ledger.entries},
            )
        row = fight.native_summon_registrations[identity]
        saved = row["server_post_registration_programs"][0]
        registration = SummonRegistration(
            actor_id=row["actor_id"],
            caster_id=row["caster_id"],
            controller_id=row["controller_id"],
            authority=NativeActorAuthority(**row["authority"]),
            fight_properties=frozenset(row["fight_properties"]),
            world_properties=frozenset(row["world_properties"]),
        )
        factory, _ = server_runtime(
            character, monsters, deck, action_id=3, critical=False, rng=Random(0)
        )
        outbox = []
        unchanged = snapshot(fight)
        self.assertFalse(
            registered_program_initializer(factory, outbox)(
                fight,
                target,
                registration,
                factory.effects[str(saved["producer"])],
                EffectInvocation(
                    saved["producer"], 185, row["caster_id"], None, target.position
                ),
            )
        )
        self.assertEqual(snapshot(fight), unchanged)
        self.assertEqual(outbox, [])
        before = snapshot(fight)
        transaction = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=5693,
                level=185,
                target=list(target.position),
                targetId=identity,
            ),
            character,
            monsters,
            deck,
            action_id=3,
            rng=Random(0),
            player_characters={7: character},
            deck_blobs={7: deck},
        )
        self.assertEqual(snapshot(fight), before)
        candidate = transaction.fight
        result = candidate.actors[identity]
        costs = transaction.plan["costs"]
        self.assertGreater(costs["ap"], 0)
        self.assertEqual(candidate.actors[-200].ap, fight.actors[-200].ap - costs["ap"])
        receipt = dict(
            scope="paid_native_hammer_against_original_ready_totem_component",
            full_encounter_victory=False,
            injected_states_or_resources=False,
            source=scene["source"],
            target_id=identity,
            target_reference=3993,
            hp_before=target.hp,
            hp_after=result.hp,
            maximum=result.max_hp,
            costs=costs,
            states_before=[
                (entry.reference, entry.level) for entry in target.state_ledger.entries
            ],
            states_after=[
                (entry.reference, entry.level) for entry in result.state_ledger.entries
            ],
        )
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/ultimate-scenes-20261021/fulmoon-paid-first-totem.json"
        )
        output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        self.assertLess(result.hp, target.hp, receipt)
        # The real native4226 predicate controls4227; a high-HP hit must not
        # manufacture the later elemental phase or an earned threshold marker.
        marked = 4227 in {entry.reference for entry in result.state_ledger.entries}
        self.assertEqual(marked, result.hp * 100 <= result.max_hp * 20)
        self.assertNotIn(
            4234, {entry.reference for entry in result.state_ledger.entries}
        )

    def test_registered_program_failure_rolls_back_ready_and_rng(self):
        from unittest.mock import patch
        from test_fulmoon_talkasha_native_bootstrap import (
            FulMoonTalKashaNativeBootstrapTests,
        )
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_fulmoon_scene,
        )
        from wakfu_server import combat_encounter_registered_programs as programs
        from wakfu_server import combat_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        original_initializer = programs.registered_program_initializer
        original_prepare = combat_server_spell.prepare_server_initialization
        checked = []

        def broken_initializer(*args):
            initialize = original_initializer(*args)

            def fail_after_real_program(*inputs):
                result = initialize(*inputs)
                if result:
                    raise RuntimeError("post-registration rollback proof")
                return result

            return fail_after_real_program

        def prepare(*args, **kwargs):
            before = snapshot(args[2])
            rng_before = kwargs["rng"].getstate()
            try:
                return original_prepare(*args, **kwargs)
            finally:
                self.assertEqual(snapshot(args[2]), before)
                self.assertEqual(kwargs["rng"].getstate(), rng_before)
                checked.append(True)

        with patch.object(
            programs, "registered_program_initializer", broken_initializer
        ), patch.object(combat_server_spell, "prepare_server_initialization", prepare):
            with self.assertRaisesRegex(
                RuntimeError, "post-registration rollback proof"
            ):
                FulMoonTalKashaNativeBootstrapTests()._started(
                    3870, 185, 1056, reconstructed_fulmoon_scene
                )
        self.assertTrue(checked)
