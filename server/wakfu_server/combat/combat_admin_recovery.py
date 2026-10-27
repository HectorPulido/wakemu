"""Bounded administrator cancellation of an offline, unsettled native fight.

This operation cancels an incident; it never certifies victory, rewards or ACKs.
Normal settled fights and live selected owners are deliberately ineligible.
"""
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from psycopg.types.json import Jsonb


class CombatRecoveryRejected(ValueError):
    """A bounded actionable rejection safe to return to the administrator."""


@dataclass(frozen=True)
class AdminHealthCancellation:
    shared: object
    db: object
    operator: int
    checkpoint_revision: int
    participants: tuple
    now: object

    def require(self, shared, db):
        if (
            self.shared is not shared
            or self.db is not db
            or self.participants != _participants(shared)
        ):
            raise ValueError(
                "Administrative cancellation lost its transaction or participant authority"
            )
        row = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s FOR SHARE", (self.operator,)
        ).fetchone()
        checkpoint = db.execute(
            "SELECT revision FROM fight_checkpoints WHERE fight_id=%s FOR UPDATE",
            (shared.fight.id,),
        ).fetchone()
        if (
            row is None
            or not row["is_admin"]
            or checkpoint is None
            or checkpoint["revision"] != self.checkpoint_revision
            or shared.fight.phase != "finished"
            or shared.settlement_ready
            or getattr(shared, "is_duel", False)
            or shared.connected
        ):
            raise ValueError(
                "Administrative cancellation authority or checkpoint changed"
            )
        if db.execute(
            "SELECT 1 FROM sessions WHERE account_id=ANY(%s) AND expires_at>%s LIMIT 1",
            ([owner.account_id for _, owner in self.participants], self.now),
        ).fetchone():
            raise ValueError("Administrative cancellation requires every owner offline")
        for table in (
            "fight_rewards",
            "fight_reward_policy_receipts",
            "rift_settlement_receipts",
        ):
            if db.execute(
                "SELECT 1 FROM " + table + " WHERE fight_id=%s LIMIT 1",
                (shared.fight.id,),
            ).fetchone():
                raise ValueError(
                    "Administrative cancellation cannot rewrite a settlement"
                )
        if db.execute(
            "SELECT 1 FROM fight_health_exits WHERE fight_id=%s AND reason<>'abort' LIMIT 1",
            (shared.fight.id,),
        ).fetchone():
            raise ValueError(
                "Administrative cancellation cannot rewrite a normal return"
            )


@dataclass(frozen=True)
class AdminRecoveryReceipt:
    shared: object
    sequence: int
    participants: tuple
    audit_id: int
    exits: dict


def _participants(shared):
    return tuple(sorted(shared.participants.items()))


def _primary_ids(fight):
    from wakfu_server.combat_terminal_metadata import registered_summon_actor_ids
    from wakfu_server.combat_companions import registered_companion_ids

    excluded = registered_summon_actor_ids(fight) | registered_companion_ids(fight)
    return sorted(
        actor.id
        for actor in fight.actors.values()
        if actor.controlled and actor.id not in excluded
    )


def _rift_destination(character, run):
    from wakfu_server import generic_transports

    destinations = {}
    for obj in run["catalog"]["objects"]:
        if obj["type"] != "Teleporter" or obj["map_id"] != character["map_id"]:
            continue
        source = generic_transports.source(character["map_id"], obj["id"])
        for target in () if source is None else source["destinations"]:
            if (
                target["criterion"].strip()
                or target["cyW"] != 0
                or target["cyX"] != 0
                or target["cyZ"] >= 0
                or target["native_altitude_walkable"] is not True
                or target["map_id"] == character["map_id"]
            ):
                continue
            key = tuple(target[field] for field in ("map_id", "x", "y", "z"))
            destinations[key] = dict(zip(("map_id", "x", "y", "z"), key))
    if len(destinations) != 1:
        raise CombatRecoveryRejected(
            "La instancia no tiene una salida nativa gratuita y única; no se cambió ningún dato."
        )
    return next(iter(destinations.values()))


class CombatAdminRecovery:
    ACTION = "combat.unsettled.abort"

    def __init__(
        self, store, registry, positions, *, groups=None, checkpoint_writer=None
    ):
        self.store = store
        self.registry = registry
        self.positions = positions
        self.groups = groups
        self.checkpoint_writer = checkpoint_writer

    @staticmethod
    def _request(body):
        if not isinstance(body, dict):
            raise CombatRecoveryRejected(
                "Se requiere una petición de recuperación explícita."
            )
        fields = {
            "action",
            "fight_id",
            "character_id",
            "checkpoint_revision",
            "request_id",
            "reason",
        }
        if set(body) - fields or body.get("action") not in ("inspect", "abort"):
            raise CombatRecoveryRejected("Operación de recuperación no permitida.")
        for field in ("fight_id", "character_id"):
            if type(body.get(field)) is not int or body[field] <= 0:
                raise CombatRecoveryRejected(
                    "Indica el combate y un participante exactos."
                )
        if body["action"] == "abort":
            if (
                type(body.get("checkpoint_revision")) is not int
                or body["checkpoint_revision"] < 0
                or not isinstance(body.get("request_id"), str)
                or re.fullmatch(r"[A-Za-z0-9_-]{1,100}", body["request_id"]) is None
                or not isinstance(body.get("reason"), str)
                or not 1 <= len(body["reason"].strip()) <= 300
            ):
                raise CombatRecoveryRejected(
                    "Inspecciona primero el combate e indica revisión, motivo e identificador de petición."
                )
        return dict(body)

    @staticmethod
    def _administrator(db, operator):
        row = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s FOR SHARE", (operator,)
        ).fetchone()
        if row is None or not row["is_admin"]:
            raise PermissionError(
                "La recuperación requiere una cuenta administradora vigente."
            )

    def _previous(self, db, operator, body, fingerprint):
        row = db.execute(
            "SELECT id,before_data,after_data FROM admin_panel_audit WHERE operator=%s "
            "AND action=%s AND before_data->>'request_id'=%s ORDER BY id DESC LIMIT 1",
            (str(operator), self.ACTION, body["request_id"]),
        ).fetchone()
        if row is not None and row["before_data"].get("fingerprint") != fingerprint:
            raise CombatRecoveryRejected(
                "Ese identificador ya pertenece a otra recuperación; conserva la petición original."
            )
        return row

    def execute(self, operator, body):
        from wakfu_server.position_buffer import PositionOwnerBusy

        try:
            return self._execute(operator, body)
        except PositionOwnerBusy as error:
            raise CombatRecoveryRejected(
                "El guardado o la limpieza de posición siguen pendientes. "
                "Espera un momento y reintenta con el mismo identificador de petición."
            ) from error

    def _execute(self, operator, body):
        body = self._request(body)
        if type(operator) is not int or operator <= 0:
            raise PermissionError("Administrador inválido.")
        fingerprint = sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        # An already committed request remains retryable after registry removal.
        with self.store.connection() as db:
            db.execute("SET LOCAL lock_timeout='1000ms'")
            db.execute("SET LOCAL statement_timeout='5000ms'")
            self._administrator(db, operator)
            if body["action"] == "abort":
                previous = self._previous(db, operator, body, fingerprint)
                if previous is not None:
                    self._retire_previous(previous, body)
                    return dict(previous["after_data"], replayed=True)
        try:
            shared = self.registry.lookup(body["fight_id"])
        except ValueError as error:
            raise CombatRecoveryRejected(
                "No existe ese combate retenido en este World; no se cambió ningún dato."
            ) from error
        if self.checkpoint_writer is not None:
            try:
                flushed = self.checkpoint_writer.flush_fight(
                    body["fight_id"], timeout=1
                )
            except ValueError as error:
                raise CombatRecoveryRejected(
                    "El guardado del combate requiere revisión antes de cancelarlo; conserva el identificador del combate."
                ) from error
            if not flushed:
                raise CombatRecoveryRejected(
                    "El guardado del combate sigue en curso. Espera un momento y vuelve a inspeccionarlo."
                )
        if not shared.lock.acquire(blocking=False):
            raise CombatRecoveryRejected(
                "El combate está procesando otra operación. Espera un momento y vuelve a inspeccionarlo."
            )
        try:
            return self._locked(operator, body, fingerprint, shared)
        finally:
            shared.lock.release()

    def _locked(self, operator, body, fingerprint, shared):
        participants = _participants(shared)
        primary_ids = _primary_ids(shared.fight)
        participant_accounts = sorted(
            {session.account_id for _, session in participants}
        )
        accounts = sorted({operator, *participant_accounts})
        if (
            getattr(shared, "is_duel", False)
            or shared.settlement_ready
            or shared.fight.phase != "finished"
            or body["character_id"] not in primary_ids
            or not 1 <= len(primary_ids) <= 6
        ):
            raise CombatRecoveryRejected(
                "Solo se puede cancelar un combate PvE terminado que aún no se ha liquidado; verifica el participante."
            )
        sequence = shared.sequence
        with ExitStack() as barriers:
            if body["action"] == "abort" and self.positions is not None:
                for account in participant_accounts:
                    barriers.enter_context(
                        self.positions.account_barrier(account, blocking=False)
                    )
                for account in participant_accounts:
                    self.positions.flush(account_id=account)
            with self.store.connection() as db:
                db.execute("SET LOCAL lock_timeout='1000ms'")
                db.execute("SET LOCAL statement_timeout='5000ms'")
                for account in accounts:
                    db.execute(
                        "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,)
                    ).fetchone()
                self._administrator(db, operator)
                if body["action"] == "abort":
                    locked = db.execute(
                        "SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS locked",
                        (self.ACTION + ":" + str(operator) + ":" + body["request_id"],),
                    ).fetchone()
                    if not locked["locked"]:
                        raise CombatRecoveryRejected(
                            "Esa recuperación sigue en curso. Reintenta con el mismo identificador."
                        )
                    previous = self._previous(db, operator, body, fingerprint)
                    if previous is not None:
                        return dict(previous["after_data"], replayed=True)
                row = db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE",
                    (shared.fight.id,),
                ).fetchone()
                checkpoint = db.execute(
                    "SELECT revision,status FROM fight_checkpoints WHERE fight_id=%s FOR UPDATE",
                    (shared.fight.id,),
                ).fetchone()
                if (
                    row is None
                    or checkpoint is None
                    or row["status"] not in ("active", "finished", "aborted")
                ):
                    raise CombatRecoveryRejected(
                        "El combate o su checkpoint ya no coincide; vuelve a inspeccionarlo."
                    )
                if any(
                    db.execute(
                        "SELECT 1 FROM " + table + " WHERE fight_id=%s LIMIT 1",
                        (shared.fight.id,),
                    ).fetchone()
                    for table in (
                        "fight_rewards",
                        "fight_reward_policy_receipts",
                        "rift_settlement_receipts",
                    )
                ):
                    raise CombatRecoveryRejected(
                        "El combate ya tiene una liquidación o recompensa: esta recuperación no puede modificarlo."
                    )
                if db.execute(
                    "SELECT 1 FROM fight_health_exits WHERE fight_id=%s AND reason<>'abort' LIMIT 1",
                    (shared.fight.id,),
                ).fetchone():
                    raise CombatRecoveryRejected(
                        "Ya existe un regreso normal del combate; no se puede cancelar su resultado."
                    )
                live = list(
                    db.execute(
                        "SELECT COALESCE(c.name,'cuenta ' || s.account_id::text) AS name "
                        "FROM sessions s LEFT JOIN characters c ON c.id=s.character_id "
                        "WHERE s.account_id=ANY(%s) AND s.expires_at>%s ORDER BY c.id FOR UPDATE OF s",
                        (
                            [session.account_id for _, session in participants],
                            self.store.now(),
                        ),
                    ).fetchall()
                )
                if shared.connected and not live:
                    raise CombatRecoveryRejected(
                        "World aún está cerrando las conexiones del grupo. Espera un momento y vuelve a inspeccionar."
                    )
                inspection = dict(
                    fight_id=shared.fight.id,
                    character_ids=primary_ids,
                    checkpoint_revision=checkpoint["revision"],
                    disconnect_characters=[r["name"] for r in live],
                )
                if body["action"] == "inspect":
                    return dict(
                        inspection,
                        eligible=not live,
                        message="Desconecta estos personajes y vuelve a inspeccionar: "
                        + ", ".join(r["name"] for r in live)
                        if live
                        else "Todos los participantes están desconectados. La cancelación guardará sus heridas y no entregará recompensas.",
                    )
                if live:
                    raise CombatRecoveryRejected(
                        "Desconecta estos personajes antes de cancelar el combate y vuelve a intentarlo: "
                        + ", ".join(r["name"] for r in live)
                    )
                if checkpoint["revision"] != body["checkpoint_revision"]:
                    raise CombatRecoveryRejected(
                        "El checkpoint cambió. Vuelve a inspeccionar y usa su revisión actual."
                    )
                if shared.checkpoint_revision not in (None, checkpoint["revision"]):
                    raise CombatRecoveryRejected(
                        "El checkpoint en memoria y el durable difieren; espera al guardado y vuelve a inspeccionar."
                    )
                # This explicit cancellation is distinct from a victory or a
                # player abandon packet. Existing health persistence still owns
                # complete roster/generation/entry-health CAS validation.
                from wakfu_server.combat_health import persist_aborted_shared_fight
                from wakfu_server.rift_runtime import abort_bound_fight

                exits = persist_aborted_shared_fight(
                    self.store,
                    shared,
                    groups=self.groups,
                    db=db,
                    administrative_cancellation=AdminHealthCancellation(
                        shared,
                        db,
                        operator,
                        checkpoint["revision"],
                        participants,
                        self.store.now(),
                    ),
                )
                abort_bound_fight(db, shared.fight.id)
                destinations = self._depart(db, shared, primary_ids)
                from wakfu_server.fight_checkpoint_store import snapshot

                encoded = snapshot(shared.fight, runtime=shared.runtime)
                if (
                    db.execute(
                        "UPDATE fight_checkpoints SET status='aborted',snapshot=%s,revision=revision+1,updated_at=%s "
                        "WHERE fight_id=%s AND revision=%s",
                        (
                            Jsonb(encoded),
                            self.store.now(),
                            shared.fight.id,
                            checkpoint["revision"],
                        ),
                    ).rowcount
                    != 1
                ):
                    raise CombatRecoveryRejected(
                        "El checkpoint cambió durante el cierre; vuelve a inspeccionar."
                    )
                result = dict(
                    inspection,
                    status="completed",
                    replayed=False,
                    request_id=body["request_id"],
                    checkpoint_revision=checkpoint["revision"] + 1,
                    destinations=destinations,
                    message="Combate cancelado. Se guardaron las heridas de todos, sin victoria ni recompensas. Ya pueden volver a conectar.",
                )
                audit = db.execute(
                    "INSERT INTO admin_panel_audit(operator,action,target,before_data,after_data) VALUES(%s,%s,%s,%s,%s) RETURNING id",
                    (
                        str(operator),
                        self.ACTION,
                        str(shared.fight.id),
                        Jsonb(
                            dict(
                                request_id=body["request_id"],
                                fingerprint=fingerprint,
                                reason=body["reason"],
                                sequence=sequence,
                                participants=[
                                    dict(
                                        account_id=v.account_id,
                                        character_id=v.character_id,
                                        generation=v.generation,
                                        map_id=v.map_id,
                                        instance_id=v.instance_id,
                                    )
                                    for _, v in participants
                                ],
                            )
                        ),
                        Jsonb(result),
                    ),
                ).fetchone()
            shared.checkpoint_revision = checkpoint["revision"] + 1
            shared.checkpoint_terminal = True
            receipt = AdminRecoveryReceipt(
                shared, sequence, participants, audit["id"], exits
            )
            self.registry.retire_admin_recovered_pve(receipt)
            self._retire_travel(shared)
            return result

    def _retire_travel(self, shared):
        from wakfu_server.rift_transition_delivery import supersede_recovered_sessions

        supersede_recovered_sessions(tuple(shared.participants.values()))
        if self.positions is not None:
            for participant in shared.participants.values():
                self.positions.release(
                    participant.account_id,
                    participant.generation,
                    participant.character_id,
                )

    def _retire_previous(self, audit, body):
        from wakfu_server.combat_shared import Session

        sessions = tuple(Session(**row) for row in audit["before_data"]["participants"])
        with ExitStack() as barriers:
            if self.positions is not None:
                for account in sorted({session.account_id for session in sessions}):
                    barriers.enter_context(
                        self.positions.account_barrier(account, blocking=False)
                    )
            return self._retire_previous_locked(audit, body)

    def _retire_previous_locked(self, audit, body):
        from wakfu_server.combat_shared import Session

        try:
            shared = self.registry.lookup(body["fight_id"])
        except ValueError:
            from wakfu_server.combat_shared import Session
            from wakfu_server.rift_transition_delivery import (
                supersede_recovered_sessions,
            )

            sessions = tuple(
                Session(**row) for row in audit["before_data"]["participants"]
            )
            supersede_recovered_sessions(sessions)
            if self.positions is not None:
                for session in sessions:
                    self.positions.release(
                        session.account_id, session.generation, session.character_id
                    )
            return
        if not shared.lock.acquire(blocking=False):
            raise CombatRecoveryRejected(
                "La limpieza de esa recuperación sigue en curso. Reintenta con el mismo identificador."
            )
        try:
            before = audit["before_data"]
            participants = tuple(
                sorted(
                    (row["account_id"], Session(**row))
                    for row in before["participants"]
                )
            )
            exits = {
                identity: {"applied": False}
                for identity in audit["after_data"]["character_ids"]
            }
            self.registry.retire_admin_recovered_pve(
                AdminRecoveryReceipt(
                    shared, before["sequence"], participants, audit["id"], exits
                )
            )
            self._retire_travel(shared)
        finally:
            shared.lock.release()

    def _depart(self, db, shared, primary_ids):
        """Use pinned native exterior facts; preserve the immutable fight roster."""
        rift = db.execute(
            "SELECT * FROM rift_instances WHERE instance_id=%s FOR UPDATE",
            (shared.instance_id,),
        ).fetchone()
        dungeon = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
            (shared.instance_id,),
        ).fetchone()
        if rift is None and dungeon is None:
            return []
        if rift is not None and (
            rift["fight_id"] != shared.fight.id
            or set(rift["members"]) != set(primary_ids)
        ):
            raise CombatRecoveryRejected(
                "La composición de la Brecha cambió; no se puede recuperar otra instancia o grupo."
            )
        rows = list(
            db.execute(
                "SELECT * FROM characters WHERE id=ANY(%s) ORDER BY id FOR UPDATE",
                (primary_ids,),
            ).fetchall()
        )
        if {r["id"] for r in rows} != set(primary_ids) or any(
            (r["map_id"], r["instance_id"]) != (shared.map_id, shared.instance_id)
            for r in rows
        ):
            raise CombatRecoveryRejected(
                "Algún participante ya cambió de ubicación; no se cambió ningún dato."
            )
        if db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.character_id=ANY(%s) AND f.id<>%s AND f.status IN('placement','active') LIMIT 1",
            (primary_ids, shared.fight.id),
        ).fetchone():
            raise CombatRecoveryRejected(
                "Un participante ya pertenece a otro combate activo."
            )
        if dungeon is not None:
            members = list(
                db.execute(
                    "SELECT character_id,session_generation,status FROM dungeon_instance_members "
                    "WHERE instance_id=%s AND character_id=ANY(%s) ORDER BY character_id FOR UPDATE",
                    (shared.instance_id, primary_ids),
                ).fetchall()
            )
            expected_generations = {
                row["id"]: shared.participants[row["account_id"]].generation
                for row in rows
            }
            if (
                {row["character_id"] for row in members} != set(primary_ids)
                or any(
                    row["status"] != "active"
                    or row["session_generation"]
                    != expected_generations[row["character_id"]]
                    for row in members
                )
                or db.execute(
                    "SELECT 1 FROM dungeon_transition_outbox WHERE character_id=ANY(%s) AND status='pending' AND instance_id<>%s LIMIT 1",
                    (primary_ids, shared.instance_id),
                ).fetchone()
            ):
                raise CombatRecoveryRejected(
                    "La membresía o un traslado de la mazmorra cambió; vuelve a inspeccionar."
                )
        destinations = []
        for account, session in _participants(shared):
            cohort = [r["id"] for r in rows if r["account_id"] == account]
            leader = next(r for r in rows if r["id"] == session.character_id)
            roster = db.execute(
                "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
                (account,),
            ).fetchone()
            slots = [
                r["character_id"]
                for r in db.execute(
                    "SELECT character_id FROM account_hero_slots WHERE account_id=%s ORDER BY slot FOR UPDATE",
                    (account,),
                ).fetchall()
            ]
            if (
                roster is not None and set(slots + [roster["leader_id"]]) != set(cohort)
            ) or (roster is None and cohort != [session.character_id]):
                raise CombatRecoveryRejected(
                    "La compañía de un participante cambió; no se modificó otra formación."
                )
            if dungeon is not None:
                from wakfu_server.dungeon_recovery import _recover_exterior

                moved = _recover_exterior(
                    self.store,
                    db,
                    account,
                    session.generation,
                    session.character_id,
                    leader,
                    dungeon,
                    character_ids=cohort,
                )
                destination = moved["destination"]
            else:
                destination = _rift_destination(leader, rift)
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s) AND instance_id=%s",
                    tuple(destination[k] for k in ("map_id", "x", "y", "z"))
                    + (cohort, shared.instance_id),
                )
            destinations.append(
                dict(account_id=account, character_ids=cohort, **destination)
            )
        if dungeon is not None:
            from wakfu_server.player_parties import cleanup_dungeon_solo

            db.execute(
                "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
                (dungeon["party_id"],),
            ).fetchone()
            cleanup_dungeon_solo(db, dungeon["party_id"])
        return destinations
