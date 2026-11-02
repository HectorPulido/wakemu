"""Actual Ready, held callbacks, normalized SQL and one real Jondo turn."""
import json
import os
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from native_rushu_party_fixture import declared_builds

SIX = {7272, 7274, 7277, 7278, 7279, 7284}
SEVEN = {7275, 7276, 7280, 7281, 7282, 7287, 7288}
SCHEDULED = SIX | SEVEN
POSITIVE = {318947: 7013, 318991: 7017, 319341: 7018, 319068: 7024}
POLICY = "wakemu-rushu-native-vestige-callbacks-v1"


class RushuVestigeCallbackOwnershipTests(PostgresCase):
    def test_actual_turn_preserves_held_callbacks_and_excludes_unearned_advice(self):
        from wakfu_server import native_catalog
        from wakfu_server import combat_ai_callback_spells as policy
        from wakfu_server import combat_rushu_encounter_setup as setup
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_rushu_scene_layout import reconstructed_scene
        from wakfu_ai.native.native_oracle import NativeOracle
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        import native_paid_party_fixture as party
        import jondo_native_turn_probe

        # PostgresCase applies the maintained migrations, including350/351, only
        # inside its disposable schema. Published native catalogs stay read-only.
        with patch.object(native_catalog, "_database", return_value=self.store):
            declarations = policy._layout_declarations.__wrapped__()
        self.assertEqual(
            {r["spell_reference"] for r in declarations if r["policy"] == POLICY}, SIX
        )
        self.assertEqual(
            {
                r["spell_reference"]
                for r in declarations
                if r["policy"] == "wakemu-rushu-native-vestige-callbacks-v2"
            },
            SEVEN,
        )
        positive, commits, seeds = [], [], []
        proof = {"normalized_sql_read": True}

        def facts(fight):
            return {
                identity: dict(
                    hp=a.hp, ap=a.ap, mp=a.mp, wp=a.effect_stats[4], position=a.position
                )
                for identity, a in fight.actors.items()
            }

        stage = {"value": None}
        original_execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            fight = dispatcher.native_retention.fight
            held = (
                [
                    (e.reference, e.level)
                    for e in fight.actors[-200].state_ledger.entries
                ]
                if -200 in fight.actors
                else []
            )
            result = original_execute(dispatcher, invocation, **kwargs)
            if (
                stage["value"] is not None
                and invocation.reference in POSITIVE
                and result
            ):
                positive.append(
                    dict(
                        effect=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        held=held,
                        stage=stage["value"],
                        table=fight.native_table_turn,
                        turn=fight.turn_id,
                    )
                )
            return result

        original_fixture = party.native_paid_party_fixture

        def fixture(*args, **kwargs):
            stage["value"] = "constructor_ready"
            try:
                return original_fixture(*args, **kwargs)
            finally:
                stage["value"] = None

        original_start = RuntimeMessages.turn_started

        def start(receiver, *args, **kwargs):
            current = getattr(self, "component", None)
            if current is None or receiver is not current.runtime:
                return original_start(receiver, *args, **kwargs)
            stage["value"] = "actual_initial_turn_started"
            try:
                return original_start(receiver, *args, **kwargs)
            finally:
                stage["value"] = None

        original_commit = NativeOracle.commit

        def commit(oracle, action, *args, **kwargs):
            before = [
                (e.reference, e.level)
                for e in oracle.runtime.fight.actors[-200].state_ledger.entries
            ]
            actors_before = facts(oracle.runtime.fight)
            result = original_commit(oracle, action, *args, **kwargs)
            commits.append(
                dict(
                    action=action,
                    actors_before=actors_before,
                    actors_after=facts(oracle.runtime.fight),
                    held_before=before,
                    held_after=[
                        (e.reference, e.level)
                        for e in oracle.runtime.fight.actors[-200].state_ledger.entries
                    ],
                )
            )
            return result

        original_setup = setup.install_rushu_encounter_setup

        def observe_setup(dispatcher, **kwargs):
            result = original_setup(dispatcher, **kwargs)
            if result:
                seeds.append(
                    [
                        dict(uid=uid, reference=area["reference"], cell=area["cell"])
                        for uid, area in dispatcher.native_retention.fight.native_effect_areas.items()
                        if area["reference"] in (1650, *range(1652, 1667))
                    ]
                )
            return result

        def drain():
            runtime = self.component.runtime
            for _ in range(32):
                if runtime.awaiting_ack is None:
                    return
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            self.fail("Actual pending ACK chain exceeded32")

        try:
            with patch.object(
                policy, "_layout_declarations", return_value=declarations
            ), patch.object(EffectDispatcher, "execute", observe), patch.object(
                party, "native_paid_party_fixture", fixture
            ), patch.object(
                RuntimeMessages, "turn_started", start
            ), patch.object(
                NativeOracle, "commit", commit
            ):
                scene = reconstructed_scene(
                    json.loads(
                        (
                            Path(__file__).parent
                            / "fixtures/ultimate_encounter_scene_recipes.json"
                        ).read_text()
                    )["maps"]["1332"]
                )
                scene.update(reference=5306, level=230)
                with original_bootstrap_publication(), patch.object(
                    setup, "install_rushu_encounter_setup", observe_setup
                ):
                    (
                        fight,
                        characters,
                        monsters,
                        decks,
                        _,
                        _,
                        premise,
                    ) = party.native_paid_party_fixture(
                        self.store,
                        scene,
                        declared_builds(),
                        (
                            (-39, 7, -4),
                            (-39, 4, -4),
                            (-39, 10, -4),
                            (-38, 12, -4),
                            (-37, 4, -4),
                            (-37, 10, -4),
                        ),
                        name_prefix="rushu-terminal",
                        encounter_layout=scene,
                        production_scene=True,
                        placement_directions=(5,) * 6,
                    )
                self.assertIs(premise["combat_state_grants"], False)
                self.assertTrue(any(len(rows) == 16 for rows in seeds))
                self.component = PaidComponentRuntime(
                    fight, characters, monsters, decks, map_id=1332
                )
                c = self.component
                c.runtime.turn_started(arm_deadline=False)
                drain()
                self.assertEqual(c.fight.current.id, -200)
                inspector = NativeOracle(
                    c.runtime,
                    characters=characters,
                    monsters=monsters,
                    decks=decks,
                    excluded_decks={i: frozenset() for i in characters},
                    viewer_id=c.first,
                    flags=dict(native_area_callbacks=True, native_start_events=True),
                )
                book = inspector.owned_spells(c.fight)
                advice = policy.deliberate_spells(c.fight, book, monsters)
                proof.update(
                    book_before=book,
                    advice=advice,
                    before=facts(c.fight),
                    held_before=[
                        (e.reference, e.level)
                        for e in c.fight.actors[-200].state_ledger.entries
                    ],
                )
                self.assertTrue(SCHEDULED <= book.keys())
                self.assertFalse(SCHEDULED.intersection(advice))
                self.assertEqual(set(advice), {7283, 7285, 7286, 7306})

                def factory(**kwargs):
                    return (
                        c.runtime,
                        characters,
                        monsters,
                        decks,
                        {i: frozenset() for i in characters},
                        SimpleNamespace(
                            pc=c.fight.actors[c.first], character=characters[c.first]
                        ),
                    )

                result = jondo_native_turn_probe.run(
                    "tcp://ai-jondo:8091",
                    reference=5306,
                    level=230,
                    max_actions=12,
                    fixture_factory=factory,
                )
                proof["actual_turn"] = result
                self.assertIsNone(result.get("nativeError"), result.get("nativeError"))
                self.assertIsNone(result.get("ackError"), result.get("ackError"))
                self.assertTrue(result["ackAccepted"])
                drain()
                self.assertIsNone(c.runtime.awaiting_ack)
                self.assertFalse(
                    SCHEDULED.intersection(a.get("spellId") for a in result["actions"])
                )
                self.assertEqual(inspector.owned_spells(c.fight, actor_id=-200), book)
                qualified = [
                    r
                    for r in positive
                    if r["caster"] == -200
                    and any(ref == POSITIVE[r["effect"]] for ref, level in r["held"])
                ]
                self.assertEqual(
                    {row["effect"] for row in qualified}, set(POSITIVE), positive
                )
                proof.update(
                    status="qualified_actual_first_turn",
                    positive_held_callbacks=qualified,
                    after=facts(c.fight),
                    awaiting_ack=c.runtime.awaiting_ack,
                )
        finally:
            proof.update(
                positive_trace=positive, commits=commits, seed_publications=seeds
            )
            destination = os.environ.get("WAKFU_RUSHU_PROOF_PATH")
            if destination:
                output = Path(destination)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(proof, indent=2, default=str) + "\n")
