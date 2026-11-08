"""Selected native statistics sources keep their exact per-actor birth authority."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from wakfu_ai.native.native_stats import NativeStats
from wakfu_server import combat_ordinary_reinforcement_sources as sources
from wakfu_server.rift_combat_adapter import creation_delivery, creation_replay
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from native_birth_fixture import admitted_native_birth


class NativeStatsSelectedTests(unittest.TestCase):
    def test_native_birth_known_sources_and_wire_are_local_and_alias_safe(self):
        fight, source, packets = admitted_native_birth()
        identity = source["id"]
        captured = {
            uid: row for uid, row in fight.rift_monsters.items() if uid != identity
        }
        expected = sources.current_monster_sources(
            fight, captured, map_id=source["map_id"]
        )
        self.assertIs(expected[identity], fight.rift_monsters[identity])
        stats = NativeStats(
            characters={}, monsters=captured, fight_id=fight.id, map_id=source["map_id"]
        )
        actor = fight.actors[identity]
        with patch.object(
            sources,
            "current_monster_source",
            side_effect=lambda current, old, uid, **kw: sources.current_monster_sources(
                current, old, **kw
            ).get(uid),
        ):
            expected_wire = stats(actor, fight)
        with patch.object(
            sources,
            "current_monster_sources",
            side_effect=AssertionError("Global source scan"),
        ):
            self.assertEqual(stats(actor, fight), expected_wire)
            self.assertIs(
                sources.current_monster_source(
                    fight, captured, identity, map_id=source["map_id"]
                ),
                fight.rift_monsters[identity],
            )
            old_identity = next(iter(captured))
            self.assertIs(
                sources.current_monster_source(
                    fight, captured, old_identity, map_id=source["map_id"]
                ),
                captured[old_identity],
            )
            # A malformed disconnected historical receipt is not this birth's authority.
            fight.rift_wave_state["staged_receipts"].append({"unrelated": True})
            self.assertEqual(stats(actor, fight), expected_wire)
        fight.rift_wave_state["staged_receipts"].pop()
        replayed = creation_replay(fight)
        self.assertEqual(creation_delivery(fight, identity), replayed[-2:])
        cloned = deepcopy(fight)
        fields = decode_state(
            json.loads(
                json.dumps(
                    encode_state(
                        {
                            "locations": fight.native_rift_birth_locations,
                            "receipts": fight.rift_wave_state["staged_receipts"],
                            "deliveries": fight.native_rift_creation_deliveries,
                        }
                    )
                )
            )
        )
        cloned.native_rift_birth_locations = fields["locations"]
        cloned.rift_wave_state["staged_receipts"] = fields["receipts"]
        cloned.native_rift_creation_deliveries = fields["deliveries"]
        with patch.object(
            sources,
            "current_monster_sources",
            side_effect=AssertionError("Global restored source scan"),
        ):
            self.assertEqual(
                sources.current_monster_source(
                    cloned, captured, identity, map_id=source["map_id"]
                ),
                source,
            )
        calls = []
        stats.monster_sources = lambda current: (calls.append(current) or expected)
        self.assertEqual(stats(actor, fight), expected_wire)
        self.assertEqual(calls, [fight])

    def test_selected_receipt_source_and_packet_mutations_reject_without_stale_cache(
        self,
    ):
        fight, source, packets = admitted_native_birth()
        identity = source["id"]
        captured = {
            uid: row for uid, row in fight.rift_monsters.items() if uid != identity
        }
        for damage in (
            "receipt",
            "slot",
            "species",
            "level",
            "instance",
            "map",
            "birth",
        ):
            candidate = deepcopy(fight)
            receipt_index, actor_offset = candidate.native_rift_birth_locations[
                identity
            ]
            row = candidate.rift_monsters[identity]
            if damage == "receipt":
                candidate.rift_wave_state["staged_receipts"][receipt_index] = {}
            elif damage == "slot":
                candidate.native_rift_birth_locations[identity] = (
                    receipt_index,
                    actor_offset + 100,
                )
            elif damage == "species":
                candidate.rift_wave_state["staged_receipts"][receipt_index][
                    "next_species_refs"
                ][actor_offset] += 1
            elif damage == "birth":
                candidate.native_rift_creation_deliveries[identity][1][
                    "payload_hex"
                ] = "00"
            else:
                key = {"level": "level", "instance": "instance_id", "map": "map_id"}[
                    damage
                ]
                row[key] += 1
            with self.subTest(damage=damage), self.assertRaises(ValueError):
                sources.current_monster_source(
                    candidate, captured, identity, map_id=source["map_id"]
                )
        legacy = deepcopy(fight)
        del legacy.native_rift_birth_locations
        self.assertEqual(
            sources.current_monster_source(
                legacy, captured, identity, map_id=source["map_id"]
            ),
            source,
        )
        fully_captured = deepcopy(fight.rift_monsters)
        fight.rift_monsters[identity]["ref"] += 1
        with self.assertRaisesRegex(ValueError, "changed captured authority"):
            sources.current_monster_source(
                fight, fully_captured, identity, map_id=source["map_id"]
            )


if __name__ == "__main__":
    unittest.main()
