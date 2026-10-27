"""Opt-in passive native commit diagnosis for the bounded Moon witness."""
from unittest.mock import patch


def run(*, maximum_boss_turns=4):
    from wakfu_ai.native.native_oracle import NativeOracle
    import test_jondo_supreme_mechanisms as witness

    commits = []
    latest = {}
    original_commit = NativeOracle.commit
    original_turn = witness._jondo_boss_turn
    turns = 0

    def primitive(value, depth=0):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if depth >= 6:
            return {"diagnosticType": type(value).__name__}
        if isinstance(value, dict):
            return {str(k): primitive(v, depth + 1) for k, v in value.items()}
        if isinstance(value, (tuple, list, set, frozenset)):
            return [primitive(v, depth + 1) for v in value]
        return {"diagnosticType": type(value).__name__}

    def facts(oracle):
        fight = oracle.runtime.fight
        actors = {}
        registrations = getattr(fight, "native_summon_registrations", {})
        for identity, actor in fight.actors.items():
            monster = oracle.monsters.get(identity, {})
            registration = registrations.get(identity, {})
            authority = registration.get("authority", {})
            actors[str(identity)] = dict(
                hp=actor.hp,
                maximumHP=actor.max_hp,
                team=getattr(actor, "team", None),
                position=primitive(actor.position),
                reference=monster.get("ref", authority.get("breed_id")),
                states=[entry.reference for entry in actor.state_ledger.entries],
                registration=primitive(registration),
            )
        terminal = {
            key: primitive(value)
            for key, value in vars(fight).items()
            if any(
                word in key.lower()
                for word in ("winner", "finish", "reason", "result", "phase")
            )
        }
        return dict(phase=fight.phase, terminal=terminal, actors=actors)

    def observed_commit(oracle, action, **kwargs):
        before = facts(oracle)
        index = len(oracle.runtime.fight.events)
        row = dict(action=primitive(action), before=before)
        try:
            return original_commit(oracle, action, **kwargs)
        except BaseException as error:
            row["error"] = dict(type=type(error).__name__, message=str(error))
            raise
        finally:
            row["after"] = facts(oracle)
            row["events"] = primitive(oracle.runtime.fight.events[index:])
            latest.clear()
            latest.update(row["after"])
            commits.append(row)

    def bounded_turn(*args, **kwargs):
        nonlocal turns
        result = original_turn(*args, **kwargs)
        turns += 1
        if turns >= maximum_boss_turns and args[0].fight.phase == "active":
            raise RuntimeError(
                "Passive diagnostic reached its declared boss-turn bound"
            )
        return result

    with patch.object(NativeOracle, "commit", observed_commit), patch.object(
        witness, "_jondo_boss_turn", bounded_turn
    ):
        result = witness.run_fulmoon(scenario="moon", backend="jondo")
    return dict(
        scope="Passive diagnostic; not a component qualification pass",
        maximumBossTurns=maximum_boss_turns,
        bossTurns=turns,
        nativeCommits=commits,
        latestFight=latest,
        witness=result,
    )
