"""Cancel an obsolete encounter atomically with a proven outside company's entry.

The caller owns account/position barriers and the new admission transaction.
No canonical fight, index or delivery queue changes before durable commit.
"""
from contextlib import contextmanager
from copy import copy
from dataclasses import dataclass


def take_entry_recovery(registry, account_id, generation, character_id):
    """Consume a local-controller cleanup notice, never a bootstrap or an ACK."""
    with registry.lock:
        return getattr(registry, "entry_recovery_notices", {}).pop(
            (account_id, generation, character_id), None
        )


def discard_entry_recovery(registry, account_id, generation):
    """Purge only the disconnected/superseded lease's private notices."""
    with registry.lock:
        notices = getattr(registry, "entry_recovery_notices", {})
        for identity in tuple(notices):
            if identity[:2] == (account_id, generation):
                notices.pop(identity, None)


def _validate_proof(proof):
    from wakfu_server.native_entry_authority import OutsideCompanyProof
    from wakfu_server.combat_shared import Session

    if (
        type(proof) is not OutsideCompanyProof
        or type(proof.requester) is not Session
        or not callable(proof.validate_live)
        or not 1 <= len(proof.character_ids) <= 6
        or len(set(proof.character_ids)) != len(proof.character_ids)
        or not proof.owners
        or proof.requester not in proof.owners
        or any(
            type(owner) is not Session or owner.instance_id != 0
            for owner in proof.owners
        )
        or len({owner.account_id for owner in proof.owners}) != len(proof.owners)
    ):
        raise ValueError("Missing exact outside company authority")
    positions = {row[0]: tuple(row[1:]) for row in proof.owner_positions}
    if len(positions) != len(proof.owner_positions) or set(positions) != {
        owner.character_id for owner in proof.owners
    }:
        raise ValueError("Outside company positions differ from selected owners")
    for owner in proof.owners:
        location = positions[owner.character_id]
        if (
            len(location) != 6
            or location[:2] != (owner.map_id, owner.instance_id)
            or owner.character_id not in proof.character_ids
        ):
            raise ValueError("Outside company location authority changed")
    proof.require_live()


def _primary_ids(shared):
    from wakfu_server.combat_terminal_metadata import registered_summon_actor_ids
    from wakfu_server.combat_companions import registered_companion_ids

    excluded = registered_summon_actor_ids(shared.fight) | registered_companion_ids(
        shared.fight
    )
    return {
        actor.id
        for actor in shared.fight.actors.values()
        if actor.controlled and actor.id not in excluded
    }


@dataclass
class PreparedEntryRecovery:
    store: object
    registry: object
    proof: object
    shared: object
    groups: object
    sequence: int
    participants: tuple
    exits: object = None
    revision: object = None
    retired: bool = False

    def _validate(self):
        _validate_proof(self.proof)
        shared = self.shared
        with self.registry.lock:
            if self.registry.fights.get(shared.fight.id) is not shared:
                raise ValueError("Obsolete entry encounter changed before recovery")
        if (
            shared.sequence != self.sequence
            or tuple(sorted(shared.participants.items())) != self.participants
            or shared.fight.phase not in ("placement", "active", "finished")
            or shared.settlement_ready
            or getattr(shared, "is_duel", False)
            or shared.returned
            or shared.withdrawals
            or _primary_ids(shared) != set(self.proof.character_ids)
            or set(shared.participants)
            != {owner.account_id for owner in self.proof.owners}
        ):
            raise ValueError(
                "Obsolete encounter differs from the complete outside company"
            )
        for owner in self.proof.owners:
            actor = shared.fight.actors.get(owner.character_id)
            if (
                actor is None
                or not actor.controlled
                or actor.owner_id != owner.account_id
            ):
                raise ValueError(
                    "Outside selected owner is foreign to the obsolete encounter"
                )

    def commit(self, db):
        """Stage health, abort and checkpoint in the caller's admission transaction."""
        from wakfu_server.fight_store import (
            _require_transaction,
            _takeover_account_memberships,
        )
        from wakfu_server.combat_command_recovery import CommandCancellation
        from wakfu_server.combat_health import persist_aborted_shared_fight
        from wakfu_server.fight_checkpoint_store import snapshot
        from psycopg.types.json import Jsonb

        _require_transaction(db)
        self._validate()
        if self.exits is not None:
            raise ValueError("Entry recovery was already staged in this transaction")
        # Current selection, human ownership and previous generations all fence
        # the same transaction as the replacement entry; no earlier takeover.
        for owner in sorted(self.proof.owners, key=lambda item: item.account_id):
            db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (owner.account_id,)
            ).fetchone()
            self.store.lock_character(
                db, owner.account_id, owner.generation, owner.character_id
            )
        checkpoint = db.execute(
            "SELECT revision,status FROM fight_checkpoints WHERE fight_id=%s FOR UPDATE",
            (self.shared.fight.id,),
        ).fetchone()
        if (
            checkpoint is None
            or checkpoint["status"] == "aborted"
            or self.shared.checkpoint_revision not in (None, checkpoint["revision"])
        ):
            raise ValueError(
                "Obsolete encounter checkpoint changed before entry recovery"
            )
        rows = db.execute(
            "SELECT id AS character_id,account_id,map_id,instance_id FROM characters "
            "WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
            (list(self.proof.character_ids),),
        ).fetchall()
        by_account = {owner.account_id: owner for owner in self.proof.owners}
        if {row["character_id"] for row in rows} != set(
            self.proof.character_ids
        ) or any(
            row["account_id"] not in by_account
            or (row["map_id"], row["instance_id"])
            not in (
                (self.shared.map_id, self.shared.instance_id),
                (
                    by_account[row["account_id"]].map_id,
                    by_account[row["account_id"]].instance_id,
                ),
            )
            for row in rows
        ):
            raise ValueError(
                "Obsolete encounter's durable outside-repair origin changed"
            )
        if any(
            self.shared.fight.actors[row["character_id"]].owner_id != row["account_id"]
            or row["account_id"] not in by_account
            for row in rows
        ):
            raise ValueError("Obsolete durable company contains a foreign owner")
        run = db.execute(
            "SELECT members,status,fight_id FROM rift_instances WHERE instance_id=%s FOR UPDATE",
            (self.shared.instance_id,),
        ).fetchone()
        if run is not None and (
            set(run["members"]) != set(self.proof.character_ids)
            or run["fight_id"] != self.shared.fight.id
            or run["status"] != "running"
        ):
            raise ValueError(
                "Obsolete rift binding differs from the complete outside company"
            )
        for owner in self.proof.owners:
            previous = self.shared.participants[owner.account_id]
            _takeover_account_memberships(
                db,
                self.shared.fight.id,
                owner.account_id,
                owner.generation,
                previous.generation,
            )
        staged = copy(self.shared)
        staged.participants = by_account
        authority = CommandCancellation(
            staged, db, self.proof.requester, tuple(sorted(staged.participants.items()))
        )
        exits = persist_aborted_shared_fight(
            self.store,
            staged,
            groups=self.groups,
            requesting_session=self.proof.requester,
            db=db,
            administrative_cancellation=authority,
        )
        updated = db.execute(
            "UPDATE fight_checkpoints SET status='aborted',snapshot=%s,revision=revision+1,updated_at=%s "
            "WHERE fight_id=%s AND revision=%s RETURNING revision",
            (
                Jsonb(snapshot(self.shared.fight, runtime=self.shared.runtime)),
                self.store.now(),
                self.shared.fight.id,
                checkpoint["revision"],
            ),
        ).fetchone()
        if updated is None:
            raise ValueError("Obsolete entry checkpoint lost its durable fence")
        self.exits, self.revision = exits, updated["revision"]
        return dict(
            fight_id=self.shared.fight.id,
            exits=exits,
            old_scope=(self.shared.map_id, self.shared.instance_id),
        )

    def retire(self):
        """Retire only this obsolete encounter, after its real durable commit."""
        if self.retired:
            return False
        if self.exits is None:
            raise ValueError(
                "Entry recovery has not committed its health and checkpoint"
            )
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT f.status,c.status AS checkpoint_status,c.revision FROM combat_fights f "
                "JOIN fight_checkpoints c ON c.fight_id=f.id WHERE f.id=%s",
                (self.shared.fight.id,),
            ).fetchone()
        if (
            receipt is None
            or receipt["status"] != "aborted"
            or receipt["checkpoint_status"] != "aborted"
            or receipt["revision"] != self.revision
        ):
            raise ValueError(
                "Entry recovery cannot retire before its transaction commits"
            )
        shared, fight_id = self.shared, self.shared.fight.id
        with self.registry.lock:
            if self.registry.fights.get(fight_id) is shared:
                self.registry.fights.pop(fight_id)
                for index in (self.registry.by_actor, self.registry.by_character):
                    for identity, registered in tuple(index.items()):
                        if registered == fight_id:
                            index.pop(identity, None)
                for identity, fights in tuple(self.registry.join_aliases.items()):
                    fights.discard(fight_id)
                    if not fights:
                        self.registry.join_aliases.pop(identity, None)
                shared.join_aliases.clear()
            for session, pending in tuple(
                getattr(self.registry, "command_cancellations", {}).items()
            ):
                if pending is shared:
                    self.registry.command_cancellations.pop(session, None)
            notices = getattr(self.registry, "entry_recovery_notices", None)
            if notices is None:
                notices = self.registry.entry_recovery_notices = {}
            current = {
                (owner.account_id, owner.generation, owner.character_id)
                for owner in self.proof.owners
            }
            accounts = {identity[0] for identity in current}
            for identity in tuple(notices):
                if identity[0] in accounts and identity not in current:
                    notices.pop(identity, None)
            for identity in current:
                notices[identity] = fight_id
        shared.connected.clear()
        for outbox in shared.outboxes.values():
            outbox.clear()
        shared.checkpoint_revision = self.revision
        shared.checkpoint_terminal = True
        shared.publication_recovery_aborted = self.exits
        # The entire company is already in a genuinely loaded world scene.
        # New admission owns its next bootstrap; never queue an obsolete return.
        self.retired = True
        return True


@contextmanager
def prepare(store, registry, proof, *, groups=None, checkpoint_writer=None):
    """Drain before Fight, then pin a complete obsolete cohort until postcommit."""
    _validate_proof(proof)
    with registry.lock:
        fight_ids = {
            registry.by_character[identity]
            for identity in proof.character_ids
            if identity in registry.by_character
        }
    if not fight_ids:
        yield None
        return
    if len(fight_ids) != 1:
        raise ValueError("Outside company belongs to different retained encounters")
    fight_id = next(iter(fight_ids))
    if checkpoint_writer is not None and not checkpoint_writer.flush_fight(
        fight_id, timeout=10
    ):
        raise ValueError("Obsolete encounter checkpoint is still pending before entry")
    with registry._locked_fight(fight_id, registry=False) as shared:
        if shared is None:
            raise ValueError("Obsolete entry encounter changed while draining")
        prepared = PreparedEntryRecovery(
            store,
            registry,
            proof,
            shared,
            groups,
            shared.sequence,
            tuple(sorted(shared.participants.items())),
        )
        prepared._validate()
        yield prepared
