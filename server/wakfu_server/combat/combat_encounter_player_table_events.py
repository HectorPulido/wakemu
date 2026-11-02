"""Reviewed round publication for actual NPC-born player state carriers.

The original state installer and retained ancestry own eligibility. This module
never installs a state, changes a grade or substitutes a player/boss recipient.
"""
from copy import deepcopy
from functools import lru_cache


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=1)
def _declarations():
    with _database().connection() as db:
        return tuple(
            dict(row)
            for row in db.execute(
                "SELECT * FROM encounter_player_table_listeners ORDER BY policy"
            ).fetchall()
        )


def _validate_source(row):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from .combat_encounter_source_revision import source_revision_matches

    if not source_revision_matches(
        row["catalog_revision"],
        (
            "combat-state-definitions.json",
            "native-retained-effect-metadata.json",
        ),
    ):
        raise ValueError("Player table listener native source changed")
    state = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json", "states", row["player_state"]
    )
    root = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json", "effects", row["effect_reference"]
    )
    installer = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json",
        "effects",
        row["installer_reference"],
    )
    metadata = native_catalog.record(
        DATA_ROOT / "native-retained-effect-metadata.json",
        "effects",
        row["effect_reference"],
    )
    if (
        row["effect_reference"] not in state.get("effect_ids", ())
        or installer.get("effect_class") != 304
        or installer.get("parameters", [None])[0] != row["player_state"]
        or installer.get("criteria") != 'IsPlayer("target")'
        or root.get("effect_class") != 330
        or root.get("target_masks") != [None, None, None, None, None, [1003], None]
        or metadata.get("subscription") is not True
        or metadata.get("event_global_subscription") is not True
        or metadata.get("event_reverse_subscription") is not False
        or metadata.get("event_caster_code") != 2
        or metadata.get("event_target_code") != 2
        or metadata.get("event_execution_count") != -1
        or metadata.get("event_execution_count_per_level") != 0
    ):
        raise ValueError("Player table listener differs from native player custody")


def freeze_player_table_listeners(fight, actor, reference, receipt):
    """Freeze once with the actual source constructor UID before opening1003."""
    layout = getattr(fight, "native_encounter_scene_layout", None)
    if not isinstance(layout, dict):
        return
    selected = [
        row
        for row in _declarations()
        if row["map_id"] == layout.get("map_id") and row["boss_reference"] == reference
    ]
    if not selected:
        return
    existing = getattr(fight, "native_encounter_player_table_policies", {})
    for row in selected:
        if row["policy"] in existing:
            continue
        _validate_source(row)
        sources = [
            state
            for state in actor.state_ledger.entries
            if state.reference == row["boss_constructor_state"]
            and state.target_id == actor.id
            and state.caster_id == actor.id
        ]
        if (
            actor.controlled
            or receipt.get("initialized") is not True
            or receipt.get("ref") != reference
            or len(sources) != 1
            or not any(
                item["state_id"] == row["boss_constructor_state"]
                for item in receipt.get("resolved_states", ())
            )
        ):
            raise ValueError("Player table listener lacks its actual boss constructor")
        existing = {
            **existing,
            row["policy"]: dict(
                declaration=deepcopy(row),
                boss_id=actor.id,
                constructor_uid=sources[0].uid,
            ),
        }
    fight.native_encounter_player_table_policies = existing


def has_player_table_interest(fight):
    return bool(getattr(fight, "native_encounter_player_table_policies", {}))


def player_table_deliveries(dispatcher):
    """Return only live player Qf roots descended from the admitted boss UID."""
    from .combat_npc_external_event_scope import qualified_npc_uids
    from .combat_retained_source_provenance import state_source_provenance

    fight = dispatcher.native_retention.fight
    policies = getattr(fight, "native_encounter_player_table_policies", {})
    if not policies:
        return []
    qualified = qualified_npc_uids(dispatcher)
    ancestry = state_source_provenance(fight)
    entries = tuple(dispatcher.native_retention.view().entries)
    deliveries = {}
    for frozen in policies.values():
        row = frozen["declaration"]
        boss = fight.actors.get(frozen["boss_id"])
        if boss is None or boss.hp <= 0:
            continue
        if boss.controlled:
            raise ValueError("Player table listener source changed actor kind")
        for actor in fight.actors.values():
            if not actor.controlled or actor.hp <= 0 or actor.team == boss.team:
                continue
            carriers = {
                state.uid
                for state in actor.state_ledger.entries
                if state.reference == row["player_state"]
                and state.target_id == actor.id
            }
            for entry in entries:
                if (
                    entry.uid not in qualified
                    or entry.manager_id != actor.id
                    or entry.generic_effect != row["effect_reference"]
                ):
                    continue
                retained = getattr(fight, "native_owned_group_effects", {}).get(
                    entry.uid, {}
                )
                state_uid = retained.get("invocation", {}).get("state_uid")
                if state_uid not in carriers:
                    continue
                seen = set()
                while state_uid != frozen["constructor_uid"]:
                    if state_uid in seen:
                        raise ValueError(
                            "Player table listener has cyclic source ancestry"
                        )
                    seen.add(state_uid)
                    source = ancestry.get(state_uid)
                    if source is None or source["parent_known"] is not True:
                        break
                    state_uid = source["parent_state_uid"]
                if state_uid == frozen["constructor_uid"]:
                    deliveries.setdefault(actor.id, set()).add(entry.uid)
    return [
        dict(actor_id=identity, eligible_uids=sorted(uids))
        for identity, uids in sorted(deliveries.items())
    ]
