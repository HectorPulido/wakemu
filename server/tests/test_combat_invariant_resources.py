"""Hash-bound resource checks use the published native definitions only."""
import copy
import hashlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from wakfu_server import native_catalog
from wakfu_server.combat_invariant_resources import ResourceAuthority
from wakfu_server.combat_invariants import Boundary, check_prepared_boundary
from wakfu_server.paths import DATA_ROOT


class CombatInvariantResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.revision = native_catalog.release()
        cls.document_hashes = native_catalog.document_hashes()
        cls.actor_path = DATA_ROOT / "native-actor-characteristics.json"
        cls.copy_path = DATA_ROOT / "native-class-copy-characteristics.json"
        cls.actor_bytes = native_catalog.read_bytes(cls.actor_path)
        cls.copy_bytes = native_catalog.read_bytes(cls.copy_path)
        cls.actor_name = "native-actor-characteristics.json"
        cls.copy_name = "native-class-copy-characteristics.json"
        cls.actor_sha256 = cls.document_hashes[cls.actor_name]
        cls.copy_sha256 = cls.document_hashes[cls.copy_name]
        cls.authority = ResourceAuthority.from_documents(
            revision=cls.revision,
            actor_bytes=cls.actor_bytes,
            copy_bytes=cls.copy_bytes,
            actor_sha256=cls.actor_sha256,
            copy_sha256=cls.copy_sha256,
        )

        # Use actors with characteristics installed by the ordinary native
        # snapshot builders. Tests mutate a private copy only for corruption
        # cases; expected limits always come from the published documents.
        from test_combat_spell_transaction import SpellTransactionTests

        _, _, cls.fight = SpellTransactionTests().native_server_fixture(15, 20)

    def candidate(self):
        return copy.deepcopy(self.fight)

    def report(self, fight, authority=None):
        return check_prepared_boundary(
            fight,
            None,
            Boundary("resource-test", "prepared"),
            resource_authority=self.authority if authority is None else authority,
        )

    @staticmethod
    def finding(report, invariant):
        return [row for row in report.findings if row.invariant == invariant]

    def test_authority_uses_active_document_bytes_and_rejects_tampering(self):
        self.assertEqual(
            hashlib.sha256(self.actor_bytes).hexdigest(), self.actor_sha256
        )
        self.assertEqual(hashlib.sha256(self.copy_bytes).hexdigest(), self.copy_sha256)
        self.assertEqual(self.authority.revision, self.revision)
        self.assertEqual(
            tuple(row.stat for row in self.authority.definitions), (1, 2, 3, 4)
        )
        with self.assertRaises(FrozenInstanceError):
            self.authority.revision = "changed"

        with self.assertRaisesRegex(ValueError, "bytes differ"):
            ResourceAuthority.from_documents(
                revision=self.revision,
                actor_bytes=self.actor_bytes + b" ",
                copy_bytes=self.copy_bytes,
                actor_sha256=self.actor_sha256,
                copy_sha256=self.copy_sha256,
            )
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            ResourceAuthority.from_documents(
                revision=self.revision,
                actor_bytes=self.actor_bytes,
                copy_bytes=self.copy_bytes,
                actor_sha256="0" * 64,
                copy_sha256=self.copy_sha256,
            )

    def test_published_wp_hard_limit_twenty_is_enforced(self):
        wp = next(row for row in self.authority.definitions if row.stat == 4)
        self.assertEqual(wp.hard_maximum, 20)
        fight = self.candidate()
        actor = fight.actors[7]
        actor.effect_maxima[4] = wp.hard_maximum + 1

        report = self.report(fight)
        matches = self.finding(report, "resource.hard_bounds")
        self.assertTrue(any(row.path.endswith("effect_stats[4]") for row in matches))

    def test_raw_signed32_and_catalog_hard_bounds_are_checked(self):
        ap = next(row for row in self.authority.definitions if row.stat == 2)
        self.assertEqual(ap.hard_maximum, (1 << 31) - 1)
        fight = self.candidate()
        fight.actors[7].effect_resource_raw_currents[2] = 1 << 31
        self.assertTrue(self.finding(self.report(fight), "resource.raw_width"))

        # HP's published hard minimum is zero. A signed32 raw current below
        # that bound is distinct from the signed-width violation above.
        hp = next(row for row in self.authority.definitions if row.stat == 1)
        self.assertEqual(hp.hard_minimum, 0)
        fight = self.candidate()
        actor = fight.actors[7]
        actor.effect_hp_raw_current = -1
        actor.hp = actor.effect_stats[1] = max(
            actor.effect_minima[1], min(actor.effect_maxima[1], -1)
        )
        self.assertTrue(self.finding(self.report(fight), "resource.raw_hard_bounds"))

    def test_java_int32_percentage_projection_and_corrupt_maximum(self):
        fight = self.candidate()
        actor = fight.actors[7]
        definition = next(row for row in self.authority.definitions if row.stat == 1)
        self.assertEqual(definition.hard_maximum, (1 << 31) - 1)

        # This native operand pair exercises signed-int multiplication wrap,
        # then Java's truncation toward zero before effective-bound clamping.
        base, percentage = 2_000_000_000, 100
        product = ((base * percentage + (1 << 31)) % (1 << 32)) - (1 << 31)
        quotient = abs(product) // 100 * (-1 if product < 0 else 1)
        expected_maximum = max(
            definition.hard_minimum,
            min(
                definition.hard_maximum,
                ((base + quotient + (1 << 31)) % (1 << 32)) - (1 << 31),
            ),
        )
        self.assertEqual(expected_maximum, 1_981_365_371)
        actor.effect_base_maxima[1] = base
        actor.effect_percentages[1] = percentage
        actor.effect_maxima[1] = expected_maximum
        actor.max_hp = expected_maximum
        actor.hp = actor.effect_stats[1] = max(
            actor.effect_minima[1], min(expected_maximum, actor.effect_hp_raw_current)
        )
        self.assertFalse(
            self.finding(self.report(fight), "resource.maximum_projection")
        )

        actor.effect_maxima[1] = expected_maximum - 1
        actor.max_hp = expected_maximum - 1
        actor.hp = actor.effect_stats[1] = max(
            actor.effect_minima[1],
            min(expected_maximum - 1, actor.effect_hp_raw_current),
        )
        self.assertTrue(self.finding(self.report(fight), "resource.maximum_projection"))

    def test_raw_hp_above_reduced_visible_maximum_remains_authoritative(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_maximum

        fight = self.candidate()
        actor = fight.actors[7]
        raw_before = actor.effect_hp_raw_current
        self.assertGreater(raw_before, 1)
        set_hp_raw_maximum(actor, actor.effect_base_minima[1])
        self.assertEqual(actor.effect_hp_raw_current, raw_before)
        self.assertGreater(actor.effect_hp_raw_current, actor.effect_maxima[1])

        report = self.report(fight)
        self.assertFalse(self.finding(report, "resource.raw_hard_bounds"))
        self.assertFalse(self.finding(report, "resource.maximum_projection"))

    def test_inspection_is_read_only_and_never_loads_catalog_or_providers(self):
        fight = self.candidate()
        actor = fight.actors[7]
        frozen = actor.effect_frozen
        projections = {
            name: (getattr(actor, name), copy.deepcopy(getattr(actor, name)))
            for name in (
                "effect_stats",
                "effect_minima",
                "effect_maxima",
                "effect_base_minima",
                "effect_base_maxima",
                "effect_percentages",
                "effect_frozen",
            )
        }

        def forbidden(*_args, **_kwargs):
            raise AssertionError("Boundary inspection called a catalog/provider")

        with patch.object(
            native_catalog, "read_bytes", side_effect=forbidden
        ), patch.object(native_catalog, "load", side_effect=forbidden):
            report = self.report(fight)

        self.assertIn("resource.hard_bounds", report.checked)
        self.assertIs(actor.effect_frozen, frozen)
        for name, (original, expected) in projections.items():
            self.assertIs(getattr(actor, name), original)
            self.assertEqual(getattr(actor, name), expected)


if __name__ == "__main__":
    unittest.main()
