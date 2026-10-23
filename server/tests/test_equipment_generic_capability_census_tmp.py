import json
import unittest
from pathlib import Path
from random import Random

from test_combat_spell_transaction import SpellTransactionTests
from wakfu_server.combat_server_spell import server_runtime, compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import characteristic_registry
from wakfu_server.combat_owned_equipment import compiled_with_sources
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_equipment_operation_capability import validate_graph
from wakfu_server.spells import encode_deck


class EquipmentGenericCapabilityCensusTests(unittest.TestCase):
    def test_previously_rejected_ready_graphs_against_real_factory(self):
        data = Path(
            ".runtime/equipment-capability-census-20261021/full/full-items.jsonl"
        )
        rejected = []
        for line in data.open():
            item = json.loads(line)
            checks = [
                check
                for case in item.get("cases", [])
                for check in case.get("ready_source_checks", [])
                if check.get("reason")
            ]
            if checks:
                rejected.append((item, checks[0]))
        character, monster, _fight = SpellTransactionTests().native_server_fixture(
            8, 21
        )
        factory, _adapter = server_runtime(
            character,
            {monster["id"]: monster},
            encode_deck((), ()),
            action_id=1,
            critical=False,
            rng=Random(1),
        )
        routes, provider = factory.equipment_operation_capability()
        base = compiled_runtime_catalog()
        registry = characteristic_registry()
        output = []
        for item, check in rejected:
            reference = item["reference"]
            slot = item.get("native_slots", [None])[0]
            owned = dict(
                character,
                inventory_items=[
                    dict(
                        uid=101,
                        character_id=character["id"],
                        reference=reference,
                        quantity=1,
                    )
                ],
            )
            sources = plan(
                owned, ordinary_only=True, _selected_entries=[dict(uid=101, slot=slot)]
            )
            if not sources:
                output.append(
                    dict(
                        reference=reference,
                        roots=check.get("roots"),
                        status="no-planned-source",
                    )
                )
                continue
            compiled = compiled_with_sources(base, sources)
            for source in sources:
                result = validate_graph(
                    source,
                    compiled,
                    registry,
                    runtime_bindings=routes,
                    criteria_capability=provider,
                )
                output.append(
                    dict(
                        reference=reference,
                        roots=list(source["roots"]),
                        status=result.status,
                        reasons=list(result.reasons),
                    )
                )
        counts = {
            status: sum(row["status"] == status for row in output)
            for status in sorted({row["status"] for row in output})
        }
        Path(
            ".runtime/equipment-capability-census-20261021/generic-capability-17-results.json"
        ).write_text(
            json.dumps(
                {
                    "factory_type": type(factory).__name__,
                    "routes_type": type(routes).__name__,
                    "provider_type": type(provider).__name__,
                    "sources": len(rejected),
                    "cases": len(output),
                    "counts": counts,
                    "results": output,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        print(
            json.dumps(
                {
                    "sources": len(rejected),
                    "cases": len(output),
                    "counts": counts,
                    "results": output,
                },
                ensure_ascii=False,
            )
        )
