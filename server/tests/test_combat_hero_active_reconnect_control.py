"""Real admitted hero ownership and spell identity across account takeover."""
import copy
import struct
import unittest
from types import SimpleNamespace

import test_combat_heroes_postgres as heroes_fixture
from postgres_case import PostgresCase
from wakfu_server.combat.combat_shared import Registry, Session
from wakfu_server.combat.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat.combat_actor import actual_actor_stats, actor_effects
from wakfu_server.combat.combat_wire import arena, decode_bootstrap
from wakfu_server.combat.combat_cast import resolve_owned_spell_action
from wakfu_server.breed_resources import live_wp
from wakfu_server.spells import default_deck, validate_deck, owned_spell_records


class HeroActiveReconnectControlTests(heroes_fixture.CombatHeroesPostgresTests):
    def setUp(self):
        heroes_fixture.CombatHeroesPostgresTests.setUp(self)

    _fight = heroes_fixture.CombatHeroesPostgresTests._fight
    _admit = heroes_fixture.CombatHeroesPostgresTests._admit

    def test_actual_admitted_current_hero_keeps_account_book_and_paid_input_after_takeover(
        self,
    ):
        admission = self._admit()
        fight = admission["fight"]
        sources = {self.main["id"]: admission["leader"], **admission["characters"]}
        live = {self.session}
        registry = Registry(lambda session: session in live)
        shared = registry.register(fight, self.session)
        registry.ready(fight.id, self.session, True, lambda *_: [])
        fight = shared.fight
        hero_id = self.hero_a["id"]
        for _ in range(8):
            if fight.current.id == hero_id:
                break
            actor = fight.current
            if actor.controlled:
                fight.end_turn(self.account, actor.id, actor.turn_count)
            else:
                fight.end_server_turn(actor.id, fight.turn_id)
        self.assertEqual(fight.current.id, hero_id)
        shared.join_context = dict(
            arena=arena(
                527, 0, [(x, 0, 0) for x in range(6)], {0: (0, 0, 0), 1: (5, 0, 0)}
            ),
            terrain_effect_id=46,
            terrain_instance_id=-300,
            leaders={0: self.main["id"], 1: -200},
        )
        shared.runtime = SimpleNamespace(
            turn_deadline=None, native_action_id=1, awaiting_ack=None
        )
        before = copy.deepcopy(
            (fight.order, fight.turn_index, fight.turn_id, fight.events)
        )

        def payload(state, actor, session):
            if not actor.controlled:
                return b"native-enemy-fixture", actor_effects()
            wp, maximum_wp = live_wp(state, actor.id)
            return (
                actual_actor_stats(
                    sources[actor.id],
                    actor,
                    state.id,
                    wp_current=wp,
                    wp_maximum=maximum_wp,
                ),
                actor_effects(),
            )

        replacement = Session(
            self.account, self.main["id"], "new-transport-generation", 527, 0
        )
        live.clear()
        live.add(replacement)
        registry.takeover(
            fight.id,
            replacement,
            lambda state, current, session: owned_snapshot(
                state, current, session, actor_payload=payload
            ),
        )
        packets = shared.outboxes[self.account][-1].packets
        decoded = decode_bootstrap(
            next(body for opcode, body in packets if opcode == 12847)
        )
        rows = {row["actor_id"]: row for row in decoded["participants"]}
        for identity in sources:
            self.assertEqual(rows[identity]["myB"], 0)
            self.assertEqual(
                struct.unpack_from(
                    ">qBqBh", rows[identity]["myE"], len(rows[identity]["myE"]) - 20
                )[0:3:2],
                (identity, self.account),
            )
        self.assertIn(12514, [opcode for opcode, _ in packets])
        self.assertIn(12053, [opcode for opcode, _ in packets])
        self.assertFalse({13337, 13482} & {opcode for opcode, _ in packets})
        self.assertEqual(
            (fight.order, fight.turn_index, fight.turn_id, fight.events), before
        )
        hero = sources[hero_id]
        deck = default_deck(hero)
        active = validate_deck(deck, hero["breed"], hero["level"])["active"]
        reference = active[0]
        uid = (hero_id << 32) | reference
        self.assertIn((uid, reference, hero["level"]), owned_spell_records(hero))
        actor, resolved, level = resolve_owned_spell_action(
            dict(actor_id=hero_id, spell_uid=uid, target=fight.actors[-200].position),
            hero,
            fight,
            self.account,
            deck,
        )
        self.assertEqual(
            (actor.id, resolved, level), (hero_id, reference, hero["level"])
        )
        before_ap = actor.ap
        registry.execute(
            fight.id,
            replacement,
            hero_id,
            lambda state, runtime: (state.spend(self.account, hero_id, ap=1), [])[1],
        )
        self.assertEqual(shared.fight.actors[hero_id].ap, before_ap - 1)


# Keep this module's discovery focused; the inherited admission suite runs in
# its own module, while its real database fixture is reused here.
for _name in vars(heroes_fixture.CombatHeroesPostgresTests):
    if _name.startswith("test_"):
        setattr(HeroActiveReconnectControlTests, _name, None)
