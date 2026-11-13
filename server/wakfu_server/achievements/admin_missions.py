"""Administrator-only mission debugging commands, using owned progress state."""
from copy import deepcopy

from . import mission_progress, rewards, storage, wire
from .service import _owner, drain_rewards


def catalog(db, query="", page=1):
    if type(page) is not int or page < 1:
        raise ValueError("La página debe ser positiva")
    rows = db.execute(
        "SELECT definition_id,data->'title'->>'es' AS title FROM native_quest_metadata_definitions "
        "WHERE revision=(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND data->'native'->>'native_class'='aJM' AND data->'native'->>'aqb'='false' "
        "AND (%s='' OR lower(data->'title'->>'es') LIKE lower(%s) OR definition_id::text=%s) "
        "ORDER BY definition_id LIMIT 11 OFFSET %s",
        (query, "%" + query + "%", query, (page - 1) * 10),
    ).fetchall()
    lines = [
        f"{row['definition_id']}: {row['title'] or '(sin nombre)'}" for row in rows[:10]
    ]
    if len(rows) > 10:
        lines.append(f"Next page: !quests {query} --page {page+1}")
    return "\n".join(lines) if lines else "No se encontraron misiones."


def transition(state, definition, action, now_ms, *, periodic_authorized=False):
    """Plan a forced, individual quest transition without fabricating events."""
    if definition.get("native_class") != "aJM" or definition.get("aqb") is not False:
        raise ValueError("El identificador no corresponde a una misión")
    identity = definition["d"]
    if definition.get("cjU", 0) and not periodic_authorized:
        raise ValueError(
            "Las misiones periódicas requieren su activación y ciclo originales"
        )
    result = deepcopy(state)
    if identity in result["completed"]:
        raise ValueError("La misión ya está completada")
    if action == "assign":
        if identity in result["running"]:
            raise ValueError("La misión ya está activa")
        result["running"] = sorted(set(result["running"]) | {identity})
        mission_progress.auto_track(result, identity)
        return result, [], []
    if action != "complete":
        raise ValueError("Acción de misión inválida")
    if identity not in result["running"]:
        raise ValueError("Primero debes asignar o aceptar la misión")
    objectives = [row["d"] for row in definition["cjJ"]]
    if len(set(objectives)) != len(objectives):
        raise ValueError("La misión tiene objetivos duplicados")
    added = sorted(set(objectives) - set(result["objectives"]))
    result["objectives"] = sorted(set(result["objectives"]) | set(objectives))
    result["running"].remove(identity)
    result["completed"] = sorted(set(result["completed"]) | {identity})
    result["tracking"] = [x for x in result["tracking"] if x != identity]
    result["completion_dates"][str(identity)] = now_ms
    result["recent"] = (result["recent"] + [{"id": identity, "date_ms": now_ms}])[-255:]
    return result, added, deepcopy(definition["cjK"])


def execute(store, account, generation, character, identity, action):
    if type(identity) is not int or identity <= 0:
        raise ValueError("ID de misión inválido")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
        store.lock_character(db, account, generation, character["id"], selected=True)
        current = store.character(account, character["id"], db)
        _owner(db, current)
        row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
            "AND definition_id=%s",
            (identity,),
        ).fetchone()
        if not row:
            raise ValueError("Misión no encontrada")
        definition = row["data"]["native"]
        before = storage.load_locked(db, current["id"])
        now_ms = int(store.now().timestamp() * 1000)
        periodic = bool(definition.get("cjU", 0))
        if periodic and action == "assign" and identity in (1108, 1215):
            from . import recurring_turnin

            packets = recurring_turnin.accept(
                db,
                store,
                current,
                definition,
                {"cycle_policy": "fixed_native_anchor_v1"},
            )
            return (
                packets,
                f"Misión asignada: {row['data']['title'].get('es')} ({identity})",
            )
        hunter = None
        cycle_key = "once"
        if periodic:
            if action != "complete":
                raise ValueError("Esta misión periódica debe aceptarse con su PNJ")
            hunter = db.execute(
                "SELECT * FROM recurring_hunter_acceptances WHERE character_id=%s AND definition_id=%s "
                "AND completed_at_ms IS NULL AND expired_at_ms IS NULL FOR UPDATE",
                (current["id"], identity),
            ).fetchone()
            if hunter is not None:
                from wakfu_server.objectives import (
                    environmental_recurring_storage as recurring,
                )

                source, contract, periodic_rewards = recurring._load(
                    db, identity, hunter["version"]
                )
                if contract.period(now_ms) != hunter["period_index"]:
                    raise ValueError("El ciclo de la misión ya venció")
                prefix = (
                    "modulox-daily:"
                    if source["interpretation_policy"] == recurring.MODULOX_POLICY
                    else "hunter-daily:"
                    if contract.period_ms == 86400000
                    else "hunter-weekly:"
                )
                cycle_key = prefix + str(hunter["period_index"])
            else:
                from . import recurring_turnin

                accepted = recurring_turnin._last(db, current["id"], identity)
                cycle = recurring_turnin._cycle(
                    definition, now_ms, "fixed_native_anchor_v1"
                )
                if (
                    not accepted
                    or accepted["cycle_index"] != cycle
                    or accepted["completed_at_ms"] is not None
                ):
                    raise ValueError("No hay aceptación válida para el ciclo actual")
                cycle_key = f"cycle:{cycle}"
        after, objectives, intents = transition(
            before, definition, action, now_ms, periodic_authorized=periodic
        )
        if hunter is not None:
            intents = [
                dict(
                    d=r["reward_id"],
                    aeV=r["native_type"],
                    ckk=r["native_flag"],
                    ckl=[r["reference"], r["amount"]]
                    if r["native_type"] == 5
                    else [r["amount"]],
                )
                for r in periodic_rewards
            ]
            db.execute(
                "UPDATE recurring_hunter_acceptances SET completed_at_ms=%s "
                "WHERE character_id=%s AND definition_id=%s AND period_index=%s",
                (now_ms, current["id"], identity, hunter["period_index"]),
            )
        elif periodic:
            db.execute(
                "UPDATE character_recurring_mission_cycles SET completed_at_ms=%s "
                "WHERE character_id=%s AND definition_id=%s AND cycle_index=%s AND completed_at_ms IS NULL",
                (now_ms, current["id"], identity, cycle),
            )
        for reward in intents:
            rewards.validate(reward)
            storage.claim_reward(
                db, current["id"], identity, cycle_key, reward["d"], reward
            )
        storage.store(db, current["id"], after)
        packets = wire.changes(
            current["id"],
            before,
            after,
            objectives,
            [identity] if action == "complete" else [],
            now_ms,
        )
        if intents:
            packets.extend(drain_rewards(db, store, current))
        title = row["data"]["title"].get("es") or str(identity)
        return (
            packets,
            f"Misión {'asignada' if action == 'assign' else 'completada'}: {title} ({identity})",
        )
