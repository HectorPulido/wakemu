"""Bounded candidate runtime used by order-trial baking regressions.

This fixture injects only the reviewed finite 3217 order-trial source delta;
it is not a compiled-catalog publication or installed-release proof.
"""
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import json
from pathlib import Path
import struct
from unittest.mock import patch

from convert_spell_effect_trees import read_effects
from jondo_native_support_probe import build_fixture
from wakfu_server import (
    combat_morph_handler,
    combat_morph_spellbook,
    combat_server_spell,
    native_order_trial_admission as admission,
    native_order_trial_checkpoint as checkpoint,
    spell_audit,
)
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.achievements import native_order_trials as kernel
from wakfu_server.combat_static_catalogs import CompiledEffects
from wakfu_server.native_order_trial_form import apply_form, prepare_form
from wakfu_server.paths import DATA_ROOT


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / ".runtime/quest-archetypes/pizza/candidate-native-source"


@contextmanager
def create_area768_fixture(
    *,
    character_source=None,
    instance_id=99,
    before_initialize=None,
    candidate_trial=True,
    player_position=(1, 0, 0),
):
    """Yield a bounded candidate runtime with original 768 callback roots.

    The isolated scene uses the pinned original map885 floor and an explicit
    test-only placement for the original 768 prototype. It does not claim an
    authenticated mission admission or recovered original glyph placement.
    """
    from wakfu_server.combat_encounter_scene_policy import prepare_scene
    from wakfu_server.combat_encounter_roles import role_assignment

    config = json.loads(
        (
            ROOT
            / ".runtime/quest-archetypes/pizza/astrub-pizzlarva-885.configuration.json"
        ).read_text()
    )
    from wakfu_server import native_order_trial_context

    room_cells = [
        tuple(cell)
        for cell in native_order_trial_context.geometry(config)["battle_floor"]["cells"]
    ]
    glyph_cell = (-4, -6, 0)
    if glyph_cell not in room_cells:
        raise ValueError("Reviewed 768 fixture cell is outside the pinned native floor")
    scene = prepare_scene(
        {
            "schema_version": 1,
            "full_room_scope": True,
            "policy_id": "wakemu.isolated-native-768-callback-fixture.v1",
            "authority": "Original map885 floor and native area/effect exports; test-only placement",
            "source_uri": "fixture://native-order-trial/map885-area768",
            "native_initial_glyphs": [
                {"reference": 768, "cell": list(glyph_cell), "level": 0}
            ],
            "native_initial_glyph_policy": "wakemu.isolated-native-768-callback-fixture.v1",
            "native_initial_glyph_authority": "Test-only placement of original prototype 768",
            "native_initial_glyph_source_url": "fixture://native-order-trial/map885-area768",
        },
        scope=dict(
            map_id=885,
            instance_id=instance_id,
            group_id=1,
            room_order=1,
            policy_version=1,
            route_key="astrub-pizzlarva-native-context",
            evidence_hashes=config["evidence_hashes"],
        ),
        room_cells=room_cells,
    )
    fixture_kwargs = dict(
        npc_position=(-4, -7, 0),
        player_position=player_position,
        map_id=885,
        instance_id=instance_id,
        terrain_instance_id=90000,
        allowed_cells=room_cells,
        full_room_scope=True,
        fixed_member_positions={0: (-4, -7, 0)},
        encounter_scene_record=scene,
        role_record=role_assignment(885, (3206,)).record(),
        character_source=character_source,
        before_initialize=before_initialize,
    )

    if not candidate_trial:
        # The raw area callback needs only two unpublished root definitions.
        # Keep the already published immutable innate/state graph and add the
        # exact original roots without iterating or rebuilding that graph.
        parsed = read_effects(
            ROOT / ".runtime/quest-archetypes/pizza/native-states-effects.tsv"
        )
        compiled = CompiledEffects.from_published("npc_imported").with_effect_sources(
            {key: parsed[key] for key in ("118950", "120464")}
        )
        original_server_runtime = combat_server_spell.server_runtime

        def candidate_server_runtime(*args, **kwargs):
            kwargs.setdefault("compiled", compiled)
            return original_server_runtime(*args, **kwargs)

        with patch.object(
            combat_server_spell, "server_runtime", side_effect=candidate_server_runtime
        ):
            case = build_fixture(3206, 96, **fixture_kwargs)
            fight, character = case.fight, case.characters[case.first]
            factory, _adapter = original_server_runtime(
                character,
                case.monsters,
                case.decks[case.first],
                action_id=17,
                critical=False,
                compiled=compiled,
            )
            dispatcher, _retained = factory(
                fight, {"native_retained_container": {"present": False}}
            )
            yield case, dispatcher, factory
        return

    case = build_fixture(3206, 96, **fixture_kwargs)
    fight, character = case.fight, case.characters[7]
    native_states = json.loads((SOURCE / "native-order-trial-states.json").read_text())
    closure = json.loads(
        (SOURCE / "native-order-trial-effect-closure.json").read_text()
    )
    # This candidate catalog deliberately contains only the exact20 states
    # and106 executable effects in the reviewed source pack. Materializing the
    # published 19MB effects mapping would defeat the bounded fixture.
    candidate_effects = dict(closure["effects"])
    # The real fixture has existing owned state runners beyond the candidate
    # closure. Add only their live retained generic_effect IDs, one exact
    # source lookup each; never materialize the published effects mapping.
    required = {
        row.get("generic_effect")
        for row in fight.native_retained_records.values()
        if type(row.get("generic_effect")) is int and row["generic_effect"] > 0
    }
    for reference in sorted(required):
        key = str(reference)
        if key in candidate_effects:
            continue
        source_effect = protocol_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", reference
        )
        if source_effect is None:
            raise ValueError(
                f"Missing exact retained source effect {reference} in combat-state-definitions"
            )
        candidate_effects[key] = source_effect
    catalog = {"states": native_states["states"], "effects": candidate_effects}

    # Preserve executable TSV records for the two actual Qq roots and reuse
    # the same candidate state catalog identity throughout the real factory.
    parsed = read_effects(
        ROOT / ".runtime/quest-archetypes/pizza/native-states-effects.tsv"
    )
    effects = {key: parsed[key] for key in ("118950", "120464")}
    compiled = CompiledEffects(effects, catalog)
    profile_doc = json.loads((SOURCE / "morph3217-native-profile.json").read_text())
    profiles = profile_doc["profiles"]
    original_server_runtime = combat_server_spell.server_runtime

    def candidate_server_runtime(*args, **kwargs):
        kwargs.setdefault("compiled", compiled)
        return original_server_runtime(*args, **kwargs)

    value = admission.document()
    value["enabled"] = True
    selected = value["sources"]["hard"]
    native_fixture = json.loads(
        (Path(__file__).parent / "fixtures/pizzlarva-native-form.json").read_text()
    )
    proof = admission.plan(
        value,
        character,
        struct.pack(">qHH", selected["object_id"], 0, 0),
        native_source=native_fixture["mode_objects"][str(selected["object_id"])],
    )
    proof = replace(proof, generation="candidate-test")

    with ExitStack() as stack:
        stack.enter_context(
            patch.object(spell_audit, "states_catalog", return_value=catalog)
        )
        stack.enter_context(
            patch.object(combat_server_spell, "states_catalog", return_value=catalog)
        )
        stack.enter_context(
            patch.object(
                combat_server_spell,
                "server_runtime",
                side_effect=candidate_server_runtime,
            )
        )
        stack.enter_context(
            patch.object(
                combat_morph_spellbook, "native_morph_profiles", return_value=profiles
            )
        )
        stack.enter_context(
            patch.object(
                combat_morph_handler, "native_morph_profiles", return_value=profiles
            )
        )
        factory, _adapter = combat_server_spell.server_runtime(
            character,
            case.monsters,
            case.decks[7],
            action_id=17,
            critical=False,
            compiled=compiled,
        )
        dispatcher, _retained = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        form = prepare_form(
            proof, encounter_id=fight.id, character=character, value=value
        )
        apply_form(dispatcher, form, instance_id=99, value=value)
        trial = admission.start_trial(
            proof,
            encounter_id=fight.id,
            orders=(("blue", "tomato"), ("red", "cheese"), ("green", "pepper")),
        )
        rules = kernel.OrderRules(
            tuple((recipe, 5) for recipe in sorted(kernel.RECIPES))
        )
        checkpoint.install(
            fight,
            proof,
            trial,
            rules,
            capability=value,
            provenance={
                "kind": "reviewed_reconstruction",
                "evidence": "Synthetic test matrix only; not native scoring/gameplay",
            },
        )
        # Each paid action creates a fresh dispatcher after sidecar installation.
        dispatcher, _retained = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        yield case, dispatcher, factory
