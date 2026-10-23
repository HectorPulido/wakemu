"""Common owned turn, movement and spell operations for bounded components."""
from collections import deque
from copy import deepcopy
from random import Random
import struct
from unittest.mock import patch


class PaidComponentRuntime:
    def __init__(self, fight, characters, monsters, decks, *, map_id, seed=0):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )

        self.characters, self.monsters, self.decks = characters, monsters, decks
        self.map_id, self.rng = map_id, Random(seed)
        self.first = next(iter(characters))
        self.common = dict(player_characters=characters, deck_blobs=decks, rng=self.rng)
        first, deck = characters[self.first], decks[self.first]
        self.runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=self.stats,
            stats_serializer=lambda actor: self.stats(actor, fight),
            turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                first,
                monsters,
                phase,
                deck,
                native_events=True,
                area_callbacks=True,
                **self.common,
                **kw
            ),
            turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                first, monsters, phase, deck, **self.common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                first,
                monsters,
                deck,
                action_id=action_id,
                critical=False,
                **self.common
            )[0],
        )
        self.payments = []

    @property
    def fight(self):
        return self.runtime.fight

    def stats(self, actor, fight):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats

        if getattr(actor, "native_summon_source", None) is not None:
            return registered_summon_stats(actor, fight, self.map_id)
        values = dict(
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            fight=fight,
        )
        if actor.id in self.characters:
            return actual_actor_stats(
                self.characters[actor.id], actor, fight.id, **values
            )
        return actual_monster_actor_stats(
            self.monsters[actor.id], actor, fight.id, **values
        )

    def advance(self):
        from combat_audit_turns import advance_actual_turn

        advance_actual_turn(self.runtime)
        for _ in range(32):
            if self.runtime.awaiting_ack is None:
                return
            self.runtime.acknowledge_turn(struct.pack(">i", self.runtime.awaiting_ack))
        raise AssertionError("Native acknowledgment chain exceeded32")

    def area_provider(self, candidate, **kw):
        from wakfu_server.combat_area_transaction import prepare_area_movement

        return prepare_area_movement(
            self.characters[self.first],
            self.monsters,
            candidate,
            self.decks[self.first],
            **self.common,
            **kw
        )

    def npc_move(self, path):
        from wakfu_server.combat_ai import snapshot, validate
        from wakfu_server.combat_movement_runtime import apply_ai, _with_areas

        actor = self.fight.current
        before = dict(position=actor.position, mp=actor.mp, ap=actor.ap)

        def decide(candidate, identity):
            request = snapshot(candidate, identity)
            return validate(
                candidate,
                identity,
                request,
                dict(
                    protocol=1,
                    requestId=request["requestId"],
                    stateKey=request["stateKey"],
                    decision=dict(
                        actor_id=identity,
                        target_id=None,
                        path=[list(cell) for cell in path],
                        attack=None,
                    ),
                ),
            )

        with patch("wakfu_server.combat_ai.plan", decide):
            _with_areas(
                self.runtime,
                self.area_provider,
                lambda candidate, callback: apply_ai(
                    candidate,
                    lambda current: self.stats(current, candidate.fight),
                    direction=actor.direction,
                    _step_callback=callback,
                ),
            )
        after = self.fight.actors[actor.id]
        self.payments.append(
            dict(
                kind="npc_movement",
                actor=actor.id,
                before=before,
                after=dict(position=after.position, mp=after.mp, ap=after.ap),
                path=path,
            )
        )

    def player_move_prefix(self, identity, path):
        from wakfu_server.combat_movement_runtime import apply_client

        actor = self.fight.actors[identity]
        accepted = None
        for count in range(min(len(path), actor.mp), 0, -1):
            candidate = tuple(path[:count])
            try:
                deepcopy(self.fight).move(actor.owner_id, identity, candidate)
            except ValueError:
                continue
            accepted = candidate
            break
        if not accepted:
            return False
        before = dict(position=actor.position, mp=actor.mp, ap=actor.ap)
        apply_client(
            self.runtime,
            actor.owner_id,
            struct.pack(">q", identity)
            + b"".join(struct.pack(">iih", *cell) for cell in accepted),
            lambda current: self.stats(current, self.fight),
            runtime_stats_serializer=self.stats,
            area_provider=self.area_provider,
        )
        after = self.fight.actors[identity]
        self.payments.append(
            dict(
                kind="player_movement",
                actor=identity,
                before=before,
                after=dict(position=after.position, mp=after.mp, ap=after.ap),
                path=accepted,
            )
        )
        return True

    def path_to(self, identity, accepts):
        from wakfu_server.combat_obstacle_condition import footprint

        actor = self.fight.actors[identity]
        blocked = set().union(
            *(
                footprint(other.position, other.physical_radius)
                for other in self.fight.actors.values()
                if other.hp > 0 and other.id != identity
            )
        )
        adjacent = {}
        for start, end in self.fight.edges:
            adjacent.setdefault(tuple(start), []).append(tuple(end))
        pending, seen = deque([(tuple(actor.position), ())]), {tuple(actor.position)}
        while pending:
            cell, path = pending.popleft()
            if accepts(cell):
                return path
            for end in sorted(adjacent.get(cell, ())):
                if end not in seen and end[:2] not in blocked:
                    seen.add(end)
                    pending.append((end, (*path, end)))
        return None

    def cast_path(
        self,
        identity,
        target_id,
        minimum,
        maximum,
        *,
        position_accepts=None,
        visible_footprint=False,
        casting_flags=None
    ):
        from wakfu_server.combat_casting_los import native_casting_ray
        from wakfu_server.combat_server_spell import server_runtime

        actor, target = self.fight.actors[identity], self.fight.actors[target_id]
        _, adapter = server_runtime(
            self.characters[identity],
            self.monsters,
            self.decks[identity],
            action_id=self.runtime.action_id + 1,
            critical=False,
            **self.common
        )

        def accepts(cell):
            if visible_footprint:
                from native_visible_target_fixture import visible_target_cells

                return (position_accepts is None or position_accepts(cell)) and bool(
                    visible_target_cells(
                        self.fight,
                        adapter.actor_authority,
                        self.map_id,
                        actor,
                        target,
                        minimum=minimum,
                        maximum=maximum,
                        source_cell=cell,
                        casting_flags=casting_flags,
                    )
                )
            distance = abs(cell[0] - target.position[0]) + abs(
                cell[1] - target.position[1]
            )
            return (
                minimum <= distance <= maximum
                and (position_accepts is None or position_accepts(cell))
                and native_casting_ray(
                    self.fight,
                    adapter.actor_authority,
                    self.map_id,
                    cell,
                    target.position,
                    source_height=actor.native_los_height,
                    target_height=target.native_los_height,
                    ignored_slots=(
                        *self.fight.native_qi_visibility_ignored_slots,
                        actor.native_obstacle_id,
                    ),
                )
            )

        return self.path_to(identity, accepts)

    def cast(self, identity, reference, target_id, *, aim_cell=None):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint

        actor, target = self.fight.actors[identity], self.fight.actors[target_id]
        target_cell = target.position if aim_cell is None else tuple(aim_cell)
        if (
            target_cell[:2] not in footprint(target.position, target.physical_radius)
            or target_cell[2] != target.position[2]
        ):
            raise AssertionError("Paid aim cell is outside the actual target footprint")
        before = dict(ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4], hp=target.hp)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", identity, (identity << 32) | reference, *target_cell),
            self.characters[identity],
            self.monsters,
            self.fight,
            actor.owner_id,
            self.decks[identity],
            action_id=self.runtime.action_id + 1,
            critical=None,
            line_of_sight=lambda source, destination, candidate: authoritative_visible(
                self.map_id,
                source,
                destination,
                candidate,
                blocking_footprints={
                    other.id: footprint(other.position, other.physical_radius)
                    for other in candidate.actors.values()
                    if other.hp > 0
                },
            ),
            **self.common
        )
        commit_spell_transaction(self.runtime, transaction, stats_serializer=self.stats)
        actor, target = self.fight.actors[identity], self.fight.actors[target_id]
        row = dict(
            kind="player_cast",
            actor=identity,
            reference=reference,
            target=target_id,
            costs=transaction.plan["costs"],
            before=before,
            after=dict(
                ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4], hp=target.hp
            ),
        )
        if aim_cell is not None:
            row["aim_cell"] = target_cell
        self.payments.append(row)
        return row

    def npc_cast(self, reference, target_id):
        from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        actor, target = self.fight.current, self.fight.actors[target_id]
        levels = owned_spells(
            self.fight, self.monsters, player_characters=self.characters
        )
        transaction = prepare_npc_spell(
            self.fight,
            dict(
                type="cast",
                spellId=reference,
                level=levels[reference],
                target=list(target.position),
                targetId=target_id,
            ),
            self.characters[self.first],
            self.monsters,
            self.decks[self.first],
            action_id=self.runtime.action_id + 1,
            **self.common
        )
        before = dict(ap=actor.ap, hp=target.hp)
        commit_spell_transaction(self.runtime, transaction, stats_serializer=self.stats)
        row = dict(
            kind="npc_cast",
            actor=actor.id,
            reference=reference,
            target=target_id,
            costs=transaction.plan["costs"],
            before=before,
            after=dict(
                ap=self.fight.actors[actor.id].ap, hp=self.fight.actors[target_id].hp
            ),
        )
        self.payments.append(row)
        return row
