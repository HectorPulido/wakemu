"""Positive native-equilibrium corrections preserve immutable ledger history."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch
from postgres_case import PostgresCase
from wakfu_server import ecology_affinity_reconciliation as reconciliation
from wakfu_server import personal_ecology


def evidence():
    return dict(
        map_id=1134,
        region_id=79001,
        kind="monster",
        family_id=316,
        before_population=129,
        after_population=130,
        limit_source="local_fallback",
        policy=dict(
            version=2, unit="basis_points", balance_delta=25, imbalance_delta=-25
        ),
    )


class AffinityReconciliationUnitTests(unittest.TestCase):
    def test_offline_owner_cannot_apply_or_publish_a_prepared_correction(self):
        store = Mock()
        world = SimpleNamespace(live_identity=lambda **_: None, publish_ecology=Mock())
        result = reconciliation.apply(
            store, world, dict(kind="affinity_reconcile", character_id=1, account_id=2)
        )
        self.assertFalse(result["applied"])
        self.assertEqual(result["reason"], "inactive_character")
        store.connection.assert_not_called()
        world.publish_ecology.assert_not_called()

    def test_runtime_rejects_old_epoch_before_reconciliation_side_effects(self):
        from wakfu_server.ecology.runtime import configure_domains

        bridge = SimpleNamespace(
            epoch="current", store=object(), world=object(), handlers={}
        )
        configure_domains(bridge, regional_bonuses=Mock())
        with patch.object(reconciliation, "apply") as apply:
            result = bridge.handlers["plants"](
                dict(kind="affinity_reconcile", world_epoch="old")
            )
        self.assertFalse(result["applied"])
        apply.assert_not_called()

    def test_reserved_birth_planner_does_not_spend_slots_on_affinity_reconciliation(
        self,
    ):
        from wakfu_server import ecology_plants

        store = MagicMock()
        store.connection.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = (
            []
        )
        snapshot = dict(
            world_epoch="reserved",
            now_ms=100000,
            planning_tick=0,
            reserve_monster_births=True,
            skip_interactive=True,
            players=[],
        )
        with patch.object(reconciliation, "prepare") as prepare:
            self.assertEqual(ecology_plants.prepare(store, snapshot, limit=4), [])
        prepare.assert_not_called()

    def test_wrong_stasis_and_omitted_wakfu_only_generate_positive_restitution(self):
        receipt = dict(
            operation="original",
            revision=1,
            requested_delta=-25,
            before_value=0,
            after_value=-25,
            evidence=evidence(),
        )
        with patch.object(
            reconciliation, "limits", return_value=dict(minimum=150, maximum=200)
        ):
            self.assertEqual(reconciliation.evaluate(receipt)["correction_delta"], 50)
            self.assertEqual(
                reconciliation.evaluate(
                    dict(receipt, requested_delta=0, after_value=0)
                )["correction_delta"],
                25,
            )
        with patch.object(
            reconciliation, "limits", return_value=dict(minimum=0, maximum=10)
        ):
            self.assertEqual(
                reconciliation.evaluate(
                    dict(receipt, requested_delta=25, after_value=25)
                )["correction_delta"],
                -50,
            )


class AffinityReconciliationPostgresTests(PostgresCase):
    def test_active_owner_corrected_after_commit_once_and_offline_owner_excluded(self):
        account = self.store.register("reconcile-owner", "test-password")["id"]
        character = self.store.create_character(account, "Reconcile Owner")
        with self.store.connection() as db:
            personal_ecology.apply(
                db,
                character["id"],
                operation="old-wrong-stasis",
                delta=-25,
                evidence=evidence(),
            )
        published = []

        def publish(committed):
            with self.store.connection() as db:
                value = db.execute(
                    "SELECT ecology_value FROM characters WHERE id=%s",
                    (character["id"],),
                ).fetchone()["ecology_value"]
            self.assertEqual(value, 25)
            published.append(committed)
            return True

        world = SimpleNamespace(
            live_identity=lambda **_: ("generation", character),
            publish_ecology=publish,
            information=Mock(),
        )
        with patch.object(
            reconciliation,
            "limits",
            return_value=dict(
                minimum=150, maximum=200, source="native_chief_wish", revision=None
            ),
        ):
            self.assertEqual(
                reconciliation.prepare(
                    self.store, dict(world_epoch="boot", players=[])
                ),
                [],
            )
            plan = reconciliation.prepare(
                self.store, dict(world_epoch="boot", players=[character])
            )[0]
            first = reconciliation.apply(self.store, world, plan)
            second = reconciliation.apply(self.store, world, plan)
            self.assertTrue(first["applied"])
            self.assertFalse(second["applied"])
            with self.store.connection() as db:
                self.assertEqual(
                    reconciliation.plan(db, character["id"])["corrections"], []
                )
                rows = db.execute(
                    "SELECT operation,requested_delta FROM personal_ecology_receipts WHERE character_id=%s ORDER BY revision",
                    (character["id"],),
                ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["requested_delta"], -25)
        self.assertEqual(rows[1]["requested_delta"], 50)
        self.assertEqual(first["ecology_value"], 25)
        self.assertEqual(len(published), 2)
        world.information.assert_called_once()
        self.assertEqual(world.information.call_args.args[0], character["id"])
        self.assertIn("0.50 puntos hacia Wakfu", world.information.call_args.args[1])
        self.assertIn(
            "No es una recompensa por reproducción natural",
            world.information.call_args.args[1],
        )

    def test_historical_clawback_is_never_planned_or_applied(self):
        account = self.store.register("reconcile-no-clawback", "test-password")["id"]
        character = self.store.create_character(account, "No Clawback")
        with self.store.connection() as db:
            personal_ecology.apply(
                db,
                character["id"],
                operation="old-positive",
                delta=25,
                evidence=evidence(),
            )
        with patch.object(
            reconciliation,
            "limits",
            return_value=dict(
                minimum=0, maximum=10, source="no_native_wish", revision=None
            ),
        ):
            with self.store.connection() as db:
                plan = reconciliation.plan(db, character["id"])
                self.assertEqual(plan["corrections"], [])
                self.assertEqual(
                    plan["skipped"][0]["reason"], "historical_clawback_excluded"
                )
                with self.assertRaises(ValueError):
                    reconciliation.apply_selected(
                        db, character["id"], operations=["old-positive"]
                    )
        self.assertEqual(
            self.store.character(account, character["id"])["ecology_value"], 25
        )
