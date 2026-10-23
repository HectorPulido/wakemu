"""Legitimate six-owner Ombrage preparation with original startup resources."""
from datetime import datetime, timezone
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from postgres_case import PostgresCase


ROOT = Path(__file__).resolve().parents[2]


class OmbrageNativeCohortTests(PostgresCase):
    def test_six_native_level200_owners_enter_clock_with_genuine_startup(self):
        from native_paid_party_fixture import (
            NativePartyBuild,
            NativeGear,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats

        scene = resolve_supreme_scene(
            4770,
            json.loads(
                (ROOT / ".runtime/ultimate-scenes-20261021/map-1229.json").read_text()
            ),
        )
        scene.update(reference=4770, level=200)
        gear = tuple(
            NativeGear(reference, slot)
            for reference, slot in (
                (20722, 3),
                (20723, 5),
                (20724, 13),
                (20725, 0),
                (20726, 12),
                (20727, 4),
                (20728, 7),
                (20729, 15),
                (20730, 8),
            )
        )
        build = NativePartyBuild(
            breed=1,
            level=200,
            active_spells=(6972,),
            aptitudes=((1, 40), (16, 10)),
            gear=gear,
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            ROOT
            / f".runtime/ultimate-scenes-20261021/ombrage-six-owner-startup-{stamp}.json"
        )
        receipt = dict(
            status="pending",
            phase_or_resource_grants=False,
            traces=[],
            damage_calculations=[],
        )
        execute = EffectDispatcher.execute
        calculate = NativeDamageHandler._calculate

        def observe_damage(handler, effect, invocation, **kwargs):
            result = calculate(handler, effect, invocation, **kwargs)
            context, flags, amount = result
            receipt["damage_calculations"].append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    amount=amount,
                    flags=flags,
                    context=dict(vars(context)),
                )
            )
            return result

        selected = {
            266403,
            268103,
            268097,
            269259,
            268940,
            268941,
            268942,
            268943,
            266405,
            266997,
            268102,
        }

        def observe(dispatcher, invocation, **kwargs):
            fight = getattr(
                getattr(dispatcher, "native_retention", None), "fight", None
            )
            before = (
                {}
                if fight is None
                else {
                    identity: (actor.hp, actor.effect_stats.get(4))
                    for identity, actor in fight.actors.items()
                }
            )
            result = execute(dispatcher, invocation, **kwargs)
            after = (
                {}
                if fight is None
                else {
                    identity: (actor.hp, actor.effect_stats.get(4))
                    for identity, actor in fight.actors.items()
                }
            )
            changed = {
                str(identity): dict(before=value, after=after.get(identity))
                for identity, value in before.items()
                if value != after.get(identity)
            }
            if invocation.reference in selected or changed:
                receipt["traces"].append(
                    dict(
                        reference=invocation.reference,
                        result=bool(result),
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        level=invocation.level,
                        changes=changed,
                        table=None
                        if fight is None
                        else getattr(fight, "native_table_turn", None),
                        turn=None if fight is None else fight.turn_id,
                    )
                )
            return result

        try:
            with original_bootstrap_publication() as publication, patch.object(
                EffectDispatcher, "execute", observe
            ), patch.object(NativeDamageHandler, "_calculate", observe_damage):
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    resources,
                    generations,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    (build,) * 6,
                    scene["party_placement_cells"],
                    name_prefix="ombrage-cohort",
                    encounter_layout=scene,
                )
                receipt["premise"] = premise
                receipt["recorded_publication"] = publication
                receipt["after_fight_start"] = {
                    str(identity): dict(
                        hp=actor.hp, wp=actor.effect_stats[4], position=actor.position
                    )
                    for identity, actor in fight.actors.items()
                }
                first = next(iter(characters))
                rng = Random(0)
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)

                def serialize(actor, current):
                    if getattr(actor, "native_summon_source", None) is not None:
                        return registered_summon_stats(actor, current, 1229)
                    source = characters.get(actor.id)
                    values = dict(
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        fight=current,
                    )
                    if source is not None:
                        return actual_actor_stats(source, actor, current.id, **values)
                    return actual_monster_actor_stats(
                        monsters[actor.id], actor, current.id, **values
                    )

                runtime = RuntimeMessages(
                    fight,
                    runtime_stats_serializer=serialize,
                    turn_start_provider=lambda phase, **kwargs: prepare_server_turn_start(
                        characters[first],
                        monsters,
                        phase,
                        decks[first],
                        native_events=True,
                        area_callbacks=True,
                        **common,
                        **kwargs,
                    ),
                    turn_end_provider=lambda phase, **kwargs: prepare_server_turn_end(
                        characters[first],
                        monsters,
                        phase,
                        decks[first],
                        **common,
                        **kwargs,
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        characters[first],
                        monsters,
                        decks[first],
                        action_id=action_id,
                        critical=False,
                        **common,
                    )[0],
                )
                packets = runtime.turn_started()
            current = runtime.fight
            receipt.update(
                phase=current.phase,
                table=getattr(current, "native_table_turn", None),
                turn=current.turn_id,
                first_turn_packets=len(packets),
                actors={
                    str(identity): dict(
                        hp=actor.hp,
                        wp=actor.effect_stats[4],
                        position=actor.position,
                        states=[
                            (entry.reference, entry.level)
                            for entry in actor.state_ledger.entries
                        ],
                    )
                    for identity, actor in current.actors.items()
                },
                native_areas=[
                    dict(reference=row["reference"], cell=row["cell"])
                    for row in current.native_effect_areas.values()
                ],
            )
            self.assertEqual(len(characters), 6)
            self.assertEqual(
                len({character["account_id"] for character in characters.values()}), 6
            )
            self.assertEqual(
                {character["level"] for character in characters.values()}, {200}
            )
            self.assertTrue(
                all(len(items) == 9 for items in premise["equipment"].values())
            )
            self.assertTrue(
                any(row["reference"] == 266403 for row in receipt["traces"])
            )
            summary = dict(
                phase=current.phase,
                hp={identity: current.actors[identity].hp for identity in characters},
                boss_wp=current.actors[-200].effect_stats[4],
            )
            self.assertEqual(current.phase, "active", summary)
            self.assertTrue(
                all(current.actors[identity].hp > 0 for identity in characters), summary
            )
            receipt["status"] = "native_six_owner_cohort_survives_first_ombrage_turn"
        except Exception as error:
            import traceback

            receipt.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
