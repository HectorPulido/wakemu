import unittest
from types import SimpleNamespace as N
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_movement_link import (
    NativeMovementLinkHandler,
    remove_movement_link,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class MovementLinkTests(unittest.TestCase):
    def fixture(self, source_props=None, target_props=None, team=1):
        actors = [
            Actor(7, 0, (0, 0, 0), 20, 6, 3, 100, 1, 3, True),
            Actor(-7, team, (1, 0, 0), 20, 4, 3, 0, 1),
        ]
        if team == 0:
            actors.append(Actor(-8, 1, (2, 0, 0), 20, 4, 3, 0, 1))
        fight = Fight(
            78,
            actors,
            {a.position for a in actors},
            {t: {a.position for a in actors if a.team == t} for t in (0, 1)},
        )
        packets = []
        handler = NativeMovementLinkHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 91,
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
            authority=N(
                property_counts=lambda p, a: (source_props or {})
                if a.id == 7
                else (target_props or {})
            ),
        )
        return fight, packets, handler, EffectInvocation(123, 1, 7, -7, (1, 0, 0))

    def test_native_application_reciprocal_without_moving_or_changing_resources(self):
        f, p, h, i = self.fixture()
        before = [(a.position, a.hp, a.ap, a.mp) for a in f.actors.values()]
        self.assertTrue(
            h({"effect_class": 802, "native_effect_flags": []}, {"parameters": []}, i)
        )
        self.assertEqual(f.native_movement_links, {7: -7, -7: 7})
        self.assertEqual(
            [(a.position, a.hp, a.ap, a.mp) for a in f.actors.values()], before
        )
        self.assertEqual(p[0][0], 13497)
        h2 = N(fight=f, packets=p, action_id=2)
        remove_movement_link(h2, 91)
        self.assertEqual(f.native_movement_links, {})
        self.assertNotIn(91, f.owned_stat_effects)
        self.assertEqual(p[-1][0], 13560)

    def test_stabilization_depends_on_team_and_explicit_ignore36(self):
        for props, team in (({11: 1}, 1), ({110: 1}, 1), ({111: 1}, 0)):
            f, p, h, i = self.fixture(target_props=props, team=team)
            self.assertFalse(
                h(
                    {"effect_class": 802, "native_effect_flags": []},
                    {"parameters": []},
                    i,
                )
            )
            self.assertEqual(p, [])
            self.assertTrue(
                h(
                    {"effect_class": 802, "native_effect_flags": [36]},
                    {"parameters": []},
                    i,
                )
            )

    def test_replacement_does_not_repair_stale_third_party_links(self):
        f, p, h, i = self.fixture()
        f.native_movement_links = {7: 99, 99: 7, -7: 98, 98: -7}
        h({"effect_class": 802, "native_effect_flags": []}, {"parameters": []}, i)
        self.assertEqual(f.native_movement_links, {7: -7, -7: 7, 99: 7, 98: -7})

    def test_missing_property_authority_and_unknown_flags_reject_before_mutation(self):
        f, p, h, i = self.fixture()
        h.authority = None
        with self.assertRaises(ValueError):
            h({"effect_class": 802, "native_effect_flags": []}, {"parameters": []}, i)
        self.assertEqual(p, [])
        with self.assertRaises(ValueError):
            h(
                {"effect_class": 802, "native_effect_flags": [123]},
                {"parameters": []},
                i,
            )
        self.assertEqual(f.owned_stat_effects, {})

    def test_counter_manager_container_dependencies_are_validated_before_any_removal(
        self,
    ):
        from wakfu_server.combat_retained_effects import (
            RetainedEffect,
            NativeRetainedRemoval,
        )

        rows = [
            RetainedEffect(
                1,
                -7,
                802,
                100,
                manager_id=-7,
                container_present=True,
                container_type=11,
                container_id=5,
            ),
            RetainedEffect(
                2,
                7,
                400,
                101,
                manager_id=7,
                container_present=True,
                container_type=11,
                container_id=5,
            ),
            RetainedEffect(
                3,
                7,
                400,
                102,
                manager_id=7,
                container_present=True,
                container_type=11,
                container_id=6,
            ),
        ]
        f = N(owned_stat_effects={1: dict(executed=True, caster_id=7, target_id=-7)})
        view = N(fight=f, entries=rows, by_uid={r.uid: r for r in rows})
        removal = NativeRetainedRemoval(view)
        live = {1, 2, 3}
        removed = []
        for family in (802, 400):
            removal.register(
                family,
                exists=lambda uid: uid in live,
                remove=lambda uid: removed.append(uid) or live.remove(uid),
                validate=lambda entry: None,
            )
        self.assertEqual([e.uid for e in removal.plan([1])], [2, 1])
        removal.remove([1])
        self.assertEqual(removed, [2, 1])
        self.assertEqual(live, {3})
        # Missing counter-manager callback must reject before removing link.
        removal = NativeRetainedRemoval(view)
        removal.register(
            802,
            exists=lambda uid: True,
            remove=lambda uid: self.fail("partial removal"),
            validate=lambda entry: None,
        )
        with self.assertRaises(ValueError):
            removal.remove([1])

    def test_checkpoint_keeps_owned_link_identity(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        f, p, h, i = self.fixture()
        h({"effect_class": 802, "native_effect_flags": []}, {"parameters": []}, i)
        self.assertEqual(snapshot(f)["native_movement_links"], {"7": -7, "-7": 7})

    def test_native_event2123_produced_in_lifecycle_without_relocating_actor(self):
        f, p, h, i = self.fixture()
        seen = []

        def phase(e, inv, **kw):
            self.assertNotIn(91, f.owned_stat_effects)
            seen.append(
                (
                    kw["channel"],
                    kw["_event_ids"],
                    dict(getattr(f, "native_movement_links", {})),
                )
            )

        h.event_lifecycle = N(phase=phase)
        effect = {
            "effect_class": 802,
            "native_effect_flags": [],
            "target_masks": [[], [], [], [], [], [], []],
        }
        i = h.prepare(effect, {"parameters": []}, i)
        h(effect, {"parameters": []}, i)
        self.assertEqual([row[0] for row in seen], [1, 2, 3, 4])
        self.assertEqual([row[1] for row in seen], [(0, 2123)] * 4)
        self.assertEqual(seen[0][2], {})
        self.assertEqual(seen[2][2], {7: -7, -7: 7})
