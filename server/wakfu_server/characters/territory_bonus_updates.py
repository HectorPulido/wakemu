"""Bounded ecology preparation and session-owned regional stat publication."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from types import MappingProxyType

from wakfu_server import (
    ecology_context,
    ecology_population,
    territory_bonuses,
    territory_cells,
)


def _revision(db, scope):
    row = db.execute(
        "SELECT revision FROM ecology_dirty_scopes WHERE map_id=%s AND instance_id=%s",
        scope,
    ).fetchone()
    return 0 if row is None else row["revision"]


def _scope(value):
    result = (value.get("map_id"), value.get("instance_id"))
    if (
        type(result[0]) is not int
        or not 0 < result[0] < 2**31
        or type(result[1]) is not int
        or not 0 <= result[1] < 2**63
    ):
        raise ValueError("Invalid regional bonus scope")
    return result


def prepare(store, world_snapshot, limit=16):
    """Read each bounded online scope once, outside all world ownership locks."""
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("Invalid regional bonus preparation limit")
    epoch = world_snapshot.get("world_epoch", world_snapshot.get("epoch"))
    if not isinstance(epoch, str) or not epoch:
        raise ValueError("Missing regional bonus world epoch")
    scopes = sorted({_scope(player) for player in world_snapshot.get("players", ())})
    if not scopes:
        return []
    offset = int(
        world_snapshot.get(
            "domain_planning_tick", world_snapshot.get("planning_tick", 0)
        )
    ) % len(scopes)
    scopes = (scopes[offset:] + scopes[:offset])[:limit]
    catalog = territory_bonuses._catalog()["territories"]
    with store.connection() as db:
        health_policy = territory_bonuses.control_health_policy(db)
    proposals = []
    for scope in scopes:
        observed_at = time.time()

        with store.connection() as db:
            before = _revision(db, scope)
            population = ecology_population.snapshot(
                db,
                *scope,
                locate=ecology_context.population_region,
                exclude_unassigned=True,
            )
            after = _revision(db, scope)
        if before != after:
            continue  # A concurrent ecology commit needs a fresh population read.
        regions, region_states = {}, {}
        for region_id, territory in catalog.items():
            if territory["map_id"] != scope[0]:
                continue
            counts = population["regions"].get(int(region_id), {})
            region = (
                territory_bonuses.evaluate_population(
                    int(region_id),
                    dict(counts.get("monster", {})),
                    dict(counts.get("plant", {})),
                )
                if population["complete"]
                else None
            )
            region_states[region_id] = (
                None if region is None else region.get("state_id")
            )
            regions[region_id] = {
                str(key): value
                for key, value in territory_bonuses.stat_bonuses(
                    region, health_policy=health_policy
                ).items()
            }
        proposals.append(
            dict(
                domain="bonuses",
                operation="regional_snapshot",
                world_epoch=epoch,
                map_id=scope[0],
                instance_id=scope[1],
                revision=after,
                regions=regions,
                region_states=region_states,
                observed_at=observed_at,
                # Exhausted proposals must receive new IDs on later planning passes.
                observation_bucket=int(observed_at // 2),
            )
        )
    return proposals


@dataclass(frozen=True)
class RegionalSnapshot:
    epoch: str
    scope: tuple[int, int]
    revision: int
    observed_at: float
    received_at: float
    regions: object
    region_states: object


class RegionalBonusUpdates:
    def __init__(self, store, world, clock=time.monotonic):
        self.store, self.world, self.clock = store, world, clock
        self.lock = threading.RLock()
        self.snapshots = {}
        self.pending = {}
        self.health_observations = {}
        self.world_epoch = None

    def apply(self, proposal, *, world_epoch):
        """Fence prepared populations against the current durable scope revision."""
        if proposal.get("world_epoch") != world_epoch:
            return {"status": "stale"}
        if (
            proposal.get("domain") != "bonuses"
            or proposal.get("operation") != "regional_snapshot"
        ):
            raise ValueError("Invalid regional bonus proposal")
        scope = _scope(proposal)
        revision, observed = proposal.get("revision"), proposal.get("observed_at")
        if (
            type(revision) is not int
            or revision < 0
            or type(observed) not in (int, float)
            or not 0 < observed <= time.time() + 5
        ):
            raise ValueError("Invalid regional bonus observation")
        raw = proposal.get("regions")
        if not isinstance(raw, dict) or len(raw) > 256:
            raise ValueError("Invalid regional bonus regions")
        states = proposal.get("region_states", {})
        if not isinstance(states, dict) or any(
            key not in raw
            or (
                value is not None
                and (type(value) is not int or value not in (1915, 1916, 1917))
            )
            for key, value in states.items()
        ):
            raise ValueError("Invalid native regional state provenance")
        regions = {}
        for region, values in raw.items():
            if (
                not isinstance(region, str)
                or not region.isdecimal()
                or int(region) <= 0
            ):
                raise ValueError("Invalid regional bonus region")
            if not isinstance(values, dict) or any(
                key not in ("1", "33", "36")
                or type(value) is not int
                or not -1000 <= value <= 1000
                for key, value in values.items()
            ):
                raise ValueError("Invalid regional characteristic values")
            regions[int(region)] = MappingProxyType(
                {int(key): value for key, value in values.items()}
            )
        with self.store.connection() as db:
            current = _revision(db, scope)
        if current != revision:
            return {"status": "stale"}
        snapshot = RegionalSnapshot(
            world_epoch,
            scope,
            revision,
            observed,
            self.clock(),
            MappingProxyType(regions),
            MappingProxyType({int(key): value for key, value in states.items()}),
        )
        with self.lock:
            if self.world_epoch != world_epoch:
                self.snapshots.clear()
                self.pending.clear()
                self.health_observations.clear()
                self.world_epoch = world_epoch
            previous = self.snapshots.get(scope)
            if (
                previous is not None
                and previous.epoch == world_epoch
                and previous.observed_at >= observed
            ):
                return {"status": "duplicate"}
            self.snapshots[scope] = snapshot
        return {"status": "applied"}

    @staticmethod
    def mark_context_refreshed(character):
        """Keep older worker observations from overriding fresh owner SQL reads."""
        character["_territory_context_refreshed_at"] = time.time()

    def _fence(self, character, generation, peer):
        with self.world.lock:
            entry = self.world.players.get(character["id"])
            return (
                entry is not None
                and entry[0] == generation
                and entry[1] is peer
                and all(
                    entry[2].get(key) == character.get(key)
                    for key in ("map_id", "instance_id", "x", "y", "z")
                )
            )

    @staticmethod
    def _identity(character, generation, peer):
        return (character["id"], generation, id(peer))

    def packets_for(self, character, generation, peer):
        """Serialize the owner session's current build and HP, never worker copies.

        The caller gates combat/spectating and sends the returned packets before
        acknowledge. Failed writes leave the publication marker unchanged.
        """
        if not self._fence(character, generation, peer):
            return []
        scope = _scope(character)
        try:
            region = territory_cells.region_at(scope[0], character["x"], character["y"])
        except (KeyError, ValueError):
            return []
        with self.lock:
            snapshot = self.snapshots.get(scope)
        if (
            snapshot is None
            or self.clock() - snapshot.received_at > 10
            or snapshot.observed_at
            <= character.get("_territory_context_refreshed_at", 0)
        ):
            return []
        bonuses = dict(snapshot.regions.get(region, {}))
        # Older stat-only proposals have no authority to remove an icon.
        state = snapshot.region_states.get(region, character.get("territory_state_id"))
        fingerprint = tuple(
            character.get(key) for key in ("map_id", "instance_id", "x", "y", "z")
        )
        identity = self._identity(character, generation, peer)
        with self.lock:
            observed = self.health_observations.get(identity)
        evaluated = (
            observed is not None
            and observed[0] is snapshot
            and observed[1:] == (fingerprint, region, state)
        )
        comparison = dict(bonuses)
        if evaluated:
            applied = character.get("territory_health_projection")
            if applied is not None:
                comparison[1] = applied["applied_flat"]
        # Fresh preparation already reads current policy. Equal raw amounts
        # therefore need no owner SQL, even when the snapshot object is new.
        # Only a previously reconciled in-flight proposal uses committed HP.
        if (
            character.get("_published_territory_stat_bonuses") == comparison
            and character.get("_published_territory_state_id") == state
            and (state is None or "_published_territory_state_id" in character)
        ):
            return []
        from wakfu_server.territory_bonuses import world_packets, reconcile_owned

        if not evaluated:
            if not self._fence(character, generation, peer):
                return []
            canonical = reconcile_owned(
                self.store,
                character["account_id"],
                generation,
                character,
                region={"state_id": state, "territory_id": region},
                bonuses=bonuses,
            )
            # A changed observation checks current policy once. Health is
            # durable before delivery, so a failed send must not leave the
            # owner HP input stale.
            character.update(canonical)
            bonuses = dict(canonical["territory_stat_bonuses"])
            if not self._fence(character, generation, peer):
                return []
            received_after = self.clock() - 10
            with self.lock:
                self.health_observations = {
                    key: value
                    for key, value in self.health_observations.items()
                    if value[0].received_at > received_after
                    and (key[0] != identity[0] or key == identity)
                }
                self.health_observations[identity] = (
                    snapshot,
                    fingerprint,
                    region,
                    state,
                )
        else:
            applied = character.get("territory_health_projection")
            if applied is not None:
                # An already evaluated cached proposal cannot repeatedly publish
                # its older HP policy value after canonical reconciliation.
                bonuses[1] = applied["applied_flat"]
        if (
            character.get("_published_territory_stat_bonuses") == bonuses
            and character.get("_published_territory_state_id") == state
            and (state is None or "_published_territory_state_id" in character)
        ):
            return []
        if not self._fence(character, generation, peer):
            return []
        stats_packets = world_packets(character)
        fingerprint = tuple(
            character.get(key) for key in ("map_id", "instance_id", "x", "y", "z")
        )
        with self.lock:
            pending = self.pending.get(self._identity(character, generation, peer))
        if (
            pending is not None
            and pending[0] is snapshot
            and pending[1] == fingerprint
            and pending[2] == bonuses
            and pending[4] == region
            and pending[5] == state
            and pending[6] == stats_packets
            and pending[7] == character.get("_published_territory_state_id")
        ):
            # A failed socket write retries the identical native actions. Never
            # allocate a second icon application for the same pending batch.
            return list(pending[3]) if self._fence(character, generation, peer) else []
        from wakfu_server.territory_bonus_wire import delta

        packets = (
            *stats_packets,
            *delta(
                character["id"], character.get("_published_territory_state_id"), state
            ),
        )
        if not self._fence(character, generation, peer):
            return []
        with self.lock:
            self.pending = {
                key: value
                for key, value in self.pending.items()
                if self.clock() - value[0].received_at <= 10
                and (
                    key[0] != character["id"]
                    or key == self._identity(character, generation, peer)
                )
            }
            self.pending[self._identity(character, generation, peer)] = (
                snapshot,
                fingerprint,
                bonuses,
                packets,
                region,
                state,
                stats_packets,
                character.get("_published_territory_state_id"),
            )
        return list(packets)

    def acknowledge(self, character, generation, peer, packets):
        """Commit only an exact successfully sent batch for the captured lease."""
        identity = self._identity(character, generation, peer)
        with self.lock:
            pending = self.pending.get(identity)
        if pending is None or tuple(packets) != pending[3]:
            return False
        (
            snapshot,
            fingerprint,
            bonuses,
            _,
            region,
            state,
            stats_packets,
            prior_state,
        ) = pending
        if character.get("_published_territory_state_id") != prior_state:
            return False
        if fingerprint != tuple(
            character.get(key) for key in ("map_id", "instance_id", "x", "y", "z")
        ) or not self._fence(character, generation, peer):
            return False
        with self.lock:
            if self.snapshots.get(snapshot.scope) is not snapshot:
                return False
        if snapshot.observed_at <= character.get("_territory_context_refreshed_at", 0):
            return False
        from wakfu_server.territory_bonuses import world_packets

        # Sending normally stays on the owner session thread, but reject a
        # changed HP/build/equipment projection if a caller breaks that rule.
        if (
            world_packets(dict(character, territory_stat_bonuses=bonuses))
            != stats_packets
        ):
            return False
        # The world projection method merges derived fields only. It must fence
        # the exact generation, peer and coordinates without writing sockets.
        if not self.world.update_territory_projection(
            generation, character, peer=peer, bonuses=bonuses, regional_state_id=state
        ):
            return False
        character["territory_stat_bonuses"] = dict(bonuses)
        character["_published_territory_stat_bonuses"] = dict(bonuses)
        character["territory_state_id"] = state
        character["_published_territory_state_id"] = state
        with self.lock:
            self.pending.pop(identity, None)
        return True
