"""Add the finite original Wild cook contracts to the current NPC aggregate."""
from copy import deepcopy

from wakfu_server.achievements import conversation_story_authoring
from wakfu_server.native_quest_complex_loot import dialogue_consumer_source, digest


def compile_fragment(document, definitions, nodes, speakers, manifest):
    result = conversation_story_authoring.extend(
        document, definitions, nodes, speakers, manifest
    )
    placement = next(
        p for p in result["placements"] if p["row"]["reference_id"] == 2800
    )
    for quest, objective in ((1641, 3104), (1666, 3169)):
        row = dict(
            quest_id=quest,
            objective_id=objective,
            action_ids=[439],
            evidence="Actual native objective says speak to the Bwork Cook; authenticated owner opening of original2800/action439 on public720 qualifies only the running native objective.",
        )
        existing = placement.setdefault("spoken_objectives", [])
        if row not in existing:
            existing.append(row)
    grants = [
        ("wild-cook-burger", 2327, 5629, 1688, 17831, [1640], [3174]),
        ("wild-cook-cure-beer", 2329, 5632, 1641, 17830, [1688], [3087]),
        ("wild-cook-excavation-key", 2365, 5737, 1666, 17864, [1641], [3089]),
        ("wild-cook-excavation-beer", 2365, 5737, 1666, 17830, [1641], [3089]),
    ]
    native = dict(nodes=list(nodes.values()), speakers=list(speakers.values()))
    for identity, node, choice, quest, item, completed, blocked in grants:
        source = dict(reference_id=2800, action_id=439, node_id=node, choice_id=choice)
        row = dict(
            id=identity,
            policy="reviewed-missing-server-supply-v1",
            reference_id=2800,
            action_id=439,
            map_id=720,
            node_id=node,
            choice_id=choice,
            quest_id=quest,
            item_reference=item,
            quantity=1,
            required_completed=completed,
            blocked_objectives=blocked,
            native_source_sha256=digest(dialogue_consumer_source(source, native)),
            evidence="Reviewed missing server supply from the exact original accepted cook offer: native2327 gives the special burger,2329 promises BworkBeer,2365 explicitly gives a key and more beer. Original item identities17831/17830/17864 are independently required by the native actual object/entrance operands; no quest outcome, drop-table row or original serialized server grant is invented. Missing-only owned supply recovery retains normal inventory/capacity transaction authority.",
        )
        rows = result.setdefault("reviewed_item_grants", [])
        previous = [r for r in rows if r["id"] == identity]
        if previous and previous != [row]:
            raise ValueError("Wild cook supply source changed")
        if not previous:
            rows.append(row)
    return result
