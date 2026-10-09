# Native area identity and own-deposit predicates — 2026-10-07

Three predicates share the registered area manager but require different target forms. The new dedicated helper is `server/wakfu_server/combat/combat_area_predicates.py`; conditions and the runtime adapter now expose the three predicates through an explicit callback.

## Native contract

The real eQd parser constructs `eNm` for `IsAreaType(number)`, `eOQ` for `IsSpecificArea(number)`, and `eOC` (subclass of `eOz`) for `IsOwnDeposit()` or `IsOwnDeposit(boolean)`. Numeric predicates have exactly one NUMBER argument; no actor selector is accepted. Own-deposit has either no argument or one BOOLEAN argument. Constructors evaluate numeric identity arguments with null context; the optional boolean is stored as `alu`. Integration must not invent selector overloads or numeric-to-boolean coercions.

`eNm.a` compares the long argument against `Qq.aeV()`; `eOQ.a` compares against `Qq.bct()`. For a literal null target, both scan all registered areas. A `Qz` target examines only its `bda()` area, with explicit null returning false. An `aBn` target scans matching areas and invokes `Qq.d(X,Y,Z)`. Other known target forms return -2; `amb.b` treats nonzero results as false. A fighter target is therefore not automatically substituted with its position.

`eOC.fyy()` returns `fbp.rNR`, whose native type identifier is 12 (`ENUTROF_DEPOSIT`); its enum ordinal is 10. `eOz.a` requires a nonnull source. A direct `Qp` target compares its area type and canonical PV owner identity. Literal null targets scan deposits owned by the source PV without geometry filtering. Cell targets scan ownership and geometry; an optional true boolean excludes the area's exact center. `aBn.Y` compares X and Y, not height. That boolean is ignored for direct-area and literal-null target forms.

Owner identity is specifically `eII.aT`: null stays null, an `eGj` resolves through `dpu()`, a `Qp` recursively resolves `bch()`, and a PV is retained. It is not a team, event source, controller numeric ID, or blindly the fighter ID. The helper takes an explicit `pv_owner_query` callback; unresolved actor-owner authority must raise rather than fabricate an identity. Two explicitly null resolved owners compare equal, matching native reference comparison. The adapter must distinguish an explicit null target from a supplied cell and from unavailable target authority.

## Implementation and limits

The helper supports exact native type/prototype filters, selected registered areas, manager-wide null scans, audited area geometry and a canonical PV callback. Missing rows, type fields, geometry or required callback raise ValueError. Known unsupported actor forms reject without consulting the manager. It reuses existing registered-area snapshot validation and geometry. It does not import catalogs, add area types, implement monster combat, or accredit class/client behavior.

## Validation

`sniffer/java/ProbeNativeAreaPredicates.java` runs the actual client parser and constructors. It verifies numeric-only prototypes, the optional-boolean own-deposit prototype, unsupported and null-Qz target results, null caster rejection, and native deposit type 12. Result: PASS. Bytecode evidence also covers manager scans, geometry and PV recursion; these are not represented as full native manager execution in the probe.

Command: `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python -m unittest server.tests.test_combat_area_predicates server.tests.test_combat_local_markers server.tests.test_combat_local_criteria server.tests.test_combat_conditions`

Result: 53 tests passed after integration, including nine new dedicated area tests and four lightweight adapter/condition tests. A further 13 existing area-query/type/ready-area tests passed. Private native evidence is retained under `.runtime/combat-review-20261007/area-predicate-probe/` and `/tmp/wakemu-{eNm,eOQ,eOC,eOz,eII,aBn,fbp}-area-review.txt`.

## Source hashes

- `server/wakfu_server/combat/combat_area_predicates.py`: `f477f4768eeae6ddca981753b920f589868774f8fe7b0a8743b8a8760af75f09`
- `server/tests/test_combat_area_predicates.py`: `2707240f8b52fa5e6c6b8aa8330a6b5a22e2d58f2bde473b146a99d7d0ece1fc`
- `sniffer/java/ProbeNativeAreaPredicates.java`: `eca826392eeb15e8dff8615e513d581def045cf095b751a54b8606da000914a3`
- `client/lib/wakfu-client.jar`: `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`

## Integrated authority producer

The adapter routes a registered target UID as an area, an existing fighter UID as an actor, an absent target plus supplied cell as a cell, and an absent target with no cell as literal null. An unresolved UID raises; it is not treated as an empty cell. Ownership reads only explicit actor authority `targeting.is_eGj` and present `targeting.dpu_id`. A direct fighter `dpu_id` must be null or a registered fighter identity and is returned directly, matching eII.aT. Registered Qp rows recurse through present `owner_id`; cycles and unresolved owners reject. No controller or team inference is introduced. Existing ordinary/summon authority producers already supply dpu metadata; this integration does not change or accredit those producers.

Additional validation command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python -m unittest test_combat_area_type_conditions test_combat_effect_area_queries test_combat_ready_area_conditions`. No world services or catalogs were loaded.

Updated integration source hashes:

- `server/wakfu_server/combat/combat_conditions.py`: `2cf2df08542a29bbad3f2a4eec499d2adb794ba3c1c8087f78c34260ebd30c84`
- `server/wakfu_server/combat/combat_runtime_adapter.py`: `6e714e143d9bb89615a24b59ad89847e8694c31ce9d29cce7b3ec905273c0fe3`
- `server/tests/test_combat_area_predicate_integration.py`: `03c4c8dc87fe8c8af7b20e440f5e527e0926a50328b35adc44195e00527f0e2a`
