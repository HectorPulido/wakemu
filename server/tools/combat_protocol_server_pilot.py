"""Produce actual server serialization inputs for an independent native pilot.

This detached serialization/domain fixture does not claim an owned live cast,
ordinary encounter admission or a full client bootstrap. No resources, native
costs or condition handlers are changed. Catalog reads are strictly offline.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def generate(catalog_bundle, output):
    from wakfu_server.combat_reproduction_catalog import ReplayCatalog

    output = Path(output)
    if output.exists():
        raise ValueError("Use a new private pilot directory")
    output.mkdir(parents=True, mode=0o700)
    producer_files = {}
    with ReplayCatalog(catalog_bundle).install():
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_wire import bootstrap
        from wakfu_server.combat_bootstrap import placement_positions
        from wakfu_server.combat_movement import movement
        from wakfu_server.combat_recovery import recovery_packet
        from wakfu_server.combat_state_carrier import (
            state_carrier_payload,
            state_carrier_application,
        )
        from wakfu_server.combat_effect_removal import running_effect_removal
        from wakfu_server.combat_effect_area_codec import area_payload, area_application
        from wakfu_server.combat_effect_area import (
            native_effect_areas,
            remove_owned_hour_area,
        )
        from wakfu_server.combat_area_contracts import AREA_CONTRACTS
        from wakfu_server.combat_observation_delivery import (
            evaluated_application_from_observation,
        )
        from wakfu_server.combat_native_timing_context import native_time_payload
        from wakfu_server.spell_audit import states_catalog
        from wakfu_server import native_catalog

        # Detached native identity/position fixture, not a resource qualification.
        own = Actor(22, 0, (2, -3, 4), 1, 0, 0, 1, 1, 77, True)
        target = Actor(-33, 1, (5, -3, 4), 1, 0, 0, 0, 1)
        cells = {(x, -3, 4) for x in range(2, 6)}
        fight = Fight(
            99, [own, target], cells, {0: {own.position}, 1: {target.position}}
        )
        packets = {}

        def save(name, opcode, body):
            packets[name] = dict(opcode=opcode, sha256=hashlib.sha256(body).hexdigest())
            (output / (name + ".bin")).write_bytes(body)

        # Existing compact/reconnect envelope represents previously known actors;
        # native proof supplies detached original registry context independently.
        save(
            "12847",
            12847,
            bootstrap(
                dict(
                    fight_id=fight.id,
                    kind=2,
                    bqh=1134,
                    myo=0,
                    myp=0,
                    myD=b"",
                    myG=b"",
                    myI=own.id,
                    myJ=target.id,
                    compact=True,
                    participants=[
                        dict(
                            actor_id=a.id,
                            myB=0 if a.controlled else 1,
                            myn=a.team,
                            myC=0,
                        )
                        for a in fight.actors.values()
                    ],
                )
            ),
        )
        save("13652", 13652, placement_positions(fight))
        initial_positions = {
            a.id: dict(cell=list(a.position), direction=None)
            for a in fight.actors.values()
        }
        path = [own.position, (3, -3, 4), (4, -3, 4)]
        opcode, body = movement(fight.id, 7, own.id, path, 1)
        save("13624", opcode, body)
        save("13420", 13420, struct.pack(">i", fight.id))

        # Real server ledger determines retained state reference/level/ownership;
        # the serializer is the implementation under test, never the oracle.
        change = target.state_ledger.apply(
            states_catalog(),
            3442,
            1,
            caster_id=own.id,
            uid=2345,
            applying_effect_has_delay=False,
        )
        entry = change.applied
        if entry is None or not entry.retained:
            raise ValueError(
                "Published native state3442 does not satisfy pilot retention"
            )
        state = state_carrier_payload(
            uid=entry.uid,
            base_uid=1234,
            caster_id=entry.caster_id,
            target_id=entry.target_id,
            state_id=entry.reference,
            level=entry.level,
            native_turn_clock=entry.duration,
            native_realtime_remaining=entry.realtime_duration,
            timing_payload=native_time_payload(),
        )
        save(
            "12613-state310",
            12613,
            state_carrier_application(
                fight.id,
                8,
                uid=entry.uid,
                target_id=target.id,
                running_effect_payload=state,
            ),
        )
        save(
            "13560-state310",
            13560,
            running_effect_removal(
                fight.id,
                10,
                effect_class=310,
                target_id=target.id,
                uid=entry.uid,
                running_effect_payload=state,
            ),
        )

        def current_states():
            return {
                retained.uid: dict(
                    state_id=retained.reference,
                    level=retained.level,
                    caster=retained.caster_id,
                    target=retained.target_id,
                    base_uid=1234,
                    container_type=None,
                    container_id=None,
                )
                for actor in fight.actors.values()
                for retained in actor.state_ledger.entries
            }

        state_projection = current_states()

        # Area definition123 is a serialization fixture identifier. It is not
        # admitted content: the independent consumer binds native eVJ explicitly.
        # Prototype1474 and its behavior are actual native bdata in the oracle.
        row = dict(
            uid=7002,
            reference=1474,
            owner_id=own.id,
            level=1,
            cell=(2, -3, 4),
            direction=None,
            native_area_contract=AREA_CONTRACTS[native_effect_areas()["1474"]["type"]],
        )
        fight.native_effect_areas[row["uid"]] = row
        arguments = dict(
            uid=15002,
            base_uid=1234,
            effect_reference=123,
            area_reference=row["reference"],
            area_uid=row["uid"],
            level=row["level"],
            keep_after=False,
            direction=row["direction"],
            caster_id=row["owner_id"],
            cell=row["cell"],
            timing_payload=native_time_payload(),
        )
        area = area_payload(**arguments)
        opcode, observation = area_application(
            fight.id, 11, effect_class=315, **arguments
        )
        if opcode != 13497:
            raise ValueError("Unexpected server evaluated-area observation route")
        save(
            "12613-area315",
            12613,
            evaluated_application_from_observation(observation, execute=False),
        )
        save(
            "13560-area315",
            13560,
            running_effect_removal(
                fight.id,
                12,
                effect_class=315,
                target_id=own.id,
                uid=15002,
                running_effect_payload=area,
            ),
        )

        def current_areas():
            return {
                registered["uid"]: dict(
                    prototype=registered["reference"],
                    level=registered["level"],
                    caster=registered["owner_id"],
                    cell=list(registered["cell"]),
                    direction=-1
                    if registered["direction"] is None
                    else registered["direction"],
                )
                for registered in fight.native_effect_areas.values()
            }

        area_projection = current_areas()
        # Compute the post-removal oracle from actual server domain mutations,
        # independently of the removal serializers and reconstruction model.
        if target.state_ledger.remove(entry.uid) is None:
            raise ValueError(
                "Server state removal did not remove the installed carrier"
            )
        if len(remove_owned_hour_area(fight, row["uid"])) != 1:
            raise ValueError(
                "Server area removal did not unregister the installed area"
            )
        removed_states = current_states()
        removed_areas = current_areas()

        # These projections are deliberately explicit domain fields. They do
        # not decode bytes, import the reconstruction component, or call an
        # existing server projection/serialization helper to determine expected.
        projection = dict(
            recipient=dict(role="participant", generation="server-pilot-generation"),
            entities={
                a.id: dict(kind=0 if a.controlled else 1, team=a.team, extra=0)
                for a in fight.actors.values()
            },
            initial_positions=initial_positions,
            movement_positions={
                **initial_positions,
                own.id: dict(cell=list(path[-1]), direction=1),
            },
            installed_states=state_projection,
            removed_states=removed_states,
            installed_areas=area_projection,
            removed_areas=removed_areas,
        )
        fight.ready(77)
        opcode, body = recovery_packet(
            fight, struct.pack(">i", fight.id), deadline_ms=31000
        )
        save("12053-recovery", opcode, body)
        sources = [
            "combat_wire.py",
            "combat_bootstrap.py",
            "combat_movement.py",
            "combat_state_carrier.py",
            "combat_effect_area_codec.py",
            "combat_effect_removal.py",
            "combat_observation_delivery.py",
            "combat_state_ledger.py",
            "combat_effect_area.py",
            "combat_area_contracts.py",
            "combat_state_managers.py",
            "combat_recovery.py",
        ]
        source_root = Path(__file__).resolve().parents[1] / "wakfu_server/combat"
        producer_files = {
            name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
            for name in sources
        }
        catalog_revision = native_catalog.release()
    (output / "server-projection.json").write_text(
        json.dumps(projection, indent=2) + "\n"
    )
    report = dict(
        schema="wakemu-server-protocol-pilot-v1",
        packets=packets,
        source=producer_files,
        catalog_revision=catalog_revision,
        projection_sha256=hashlib.sha256(
            (output / "server-projection.json").read_bytes()
        ).hexdigest(),
        scope="actual server serialization and retained ledger inputs; detached native context, not live cast/encounter/client qualification",
    )
    (output / "server-pilot.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = generate(args.catalog_bundle, args.output)
    print(
        json.dumps(
            dict(
                packets=len(report["packets"]),
                catalog_revision=report["catalog_revision"],
            )
        )
    )


if __name__ == "__main__":
    main()
