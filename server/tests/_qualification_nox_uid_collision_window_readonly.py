"""Read the original UID sequence and namespace occupants without allocation."""
import json, sys, unittest
from pathlib import Path


def inspect():
    recipe = sys.modules["test_nox_full_party_early_score"]
    record = recipe.retained_components[0]
    before = recipe.verify_retained_component(record)
    fight = record["case"].fight
    initial = fight.native_effect_uid_next
    low, high = initial, initial + 100
    names = (
        "state_wire_payloads",
        "owned_stat_effects",
        "native_retained_records",
        "native_owned_group_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
        "native_effect_areas",
        "native_retired_area_managers",
    )
    occupied = {}
    at8990 = {}
    for name in names:
        rows = getattr(fight, name, {})
        keys = [k for k in rows if type(k) is int or isinstance(k, str) and k.isdigit()]
        ints = [int(k) for k in keys]
        occupied[name] = dict(
            count=len(rows),
            maximum=max(ints, default=None),
            window={str(k): rows[k] for k in keys if low <= int(k) <= high},
        )
        at8990[name] = rows.get(8990, rows.get("8990"))
    ledgers = [
        dict(
            actor_id=a.id,
            uid=e.uid,
            reference=e.reference,
            level=e.level,
            caster_id=getattr(e, "caster_id", None),
        )
        for a in fight.actors.values()
        for e in a.state_ledger.entries
    ]
    grants = getattr(fight, "native_spell_grants", {})
    grantrows = [
        dict(owner=owner, **row)
        for owner, rows in grants.items()
        for row in rows.values()
    ]
    row = dict(
        table=fight.native_table_turn,
        turn=fight.turn_id,
        current=fight.current.id,
        native_effect_uid_next=initial,
        window=(low, high),
        namespaces=occupied,
        uid8990=at8990,
        state_ledger=dict(
            count=len(ledgers),
            maximum=max((e["uid"] for e in ledgers), default=None),
            window=[e for e in ledgers if low <= e["uid"] <= high],
            at8990=[e for e in ledgers if e["uid"] == 8990],
        ),
        spell_grants=dict(
            count=len(grantrows),
            window=[r for r in grantrows if low <= r["uid"] <= high],
        ),
        actor3_usage=getattr(fight, "native_spell_usage", {}).get("3"),
        failure_reference=209926,
        failure_state_uid=11,
        failed_preview_exact_uid_not_retained=True,
        verification_before=before,
        verification_after=recipe.verify_retained_component(record),
        no_allocations_or_actions=True,
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-original-effect-uid-next-window-and-pv8990-readonly.json"
    ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()
