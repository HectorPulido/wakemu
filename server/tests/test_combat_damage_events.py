import unittest
from wakfu_server.combat_damage_events import damage_event_ids


class NativeDamageEventsTests(unittest.TestCase):
    def events(
        self,
        kind=1,
        flags=(),
        container=11,
        phase=1,
        blocked=False,
        localization="FRONT",
        fight=True,
    ):
        return damage_event_ids(
            dict(
                effect_class=kind,
                native_effect_flags=list(flags),
                target_masks=[None] * 7,
            ),
            container_type=container,
            phase=phase,
            blocked=blocked,
            localization=localization,
            context_is_native_fight=fight,
        )

    def test_registry_native_element_matrix(self):
        for kind, expected in (
            (1, (0, 2)),
            (2, (0, 2, 5)),
            (3, (0, 2, 8)),
            (4, (0, 2, 6)),
            (5, (0, 2, 7)),
            (1083, (0, 2, 11)),
        ):
            self.assertEqual(self.events(kind), expected)

    def test_native_flag_matrix_and_fOG_container_gate(self):
        self.assertEqual(
            self.events(flags=(4, 22, 23, 24)), (0, 2, 2215, 2216, 2217, 2218)
        )
        self.assertEqual(self.events(container=3), (0, 2, 2268))
        self.assertEqual(self.events(container=None), (0, 2, 2268))
        self.assertEqual(self.events(container=12), (0, 2))
        self.assertEqual(self.events(container=3, flags=(34,)), (0, 2))

    def test_block_and_back_only_join_after_application(self):
        self.assertEqual(
            self.events(phase=2, blocked=True, localization="BACK"), (0, 2)
        )
        self.assertEqual(
            self.events(phase=3, blocked=True, localization="BACK"), (0, 2, 29, 2233)
        )
        self.assertEqual(self.events(phase=4, blocked=True, fight=False), (0, 2))

    def test_unknown_source_context_rejects(self):
        for kwargs in (
            dict(phase=5),
            dict(kind=6),
            dict(blocked=None),
            dict(fight=None),
            dict(localization=None),
        ):
            with self.assertRaises(ValueError):
                self.events(**kwargs)
