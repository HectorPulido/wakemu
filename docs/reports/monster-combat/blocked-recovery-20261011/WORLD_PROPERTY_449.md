# Family 449: world-property mutation

## Native evidence

The installed runner is `eWw extends eZR`. Its `C` phase evaluates parameter zero into `aSg`. Application requires an `eGj` target and a registered `eHQ.Qm(aSg)` property; invalid targets or IDs end the effect through `mu(true)`.

Application adds the mapped `ffe` fight property only when `PN.bag() == 1` and the mapping is non-null, then adds the `eHQ` world property. Removal first removes the mapped fight property whenever it exists, then removes the world property. Removal does not repeat the application-mode condition. A symmetric set-add/set-remove implementation would therefore lose native behavior.

The actor dispatches these property types through separate managers: world properties use `pGI`/type zero, while fight properties use `pGH`/type one. Existing signed-byte property-stack helpers may be reused, but both namespaces must remain distinct.

Installed bytecode is retained privately in `next-family-runners/eWw.txt` under the offline recovery directory.

## Representative scope

Recorded affected definitions include Slimsis (2388, level 4), Ayudante de Nileza (2390, level 115), Escafandra (2391, levels 0–1), Fuego Fatuemporal (3540, level 160), Agua Fuerte (3761, level 15), and Llama Viva (3762, level 15). Names and levels identify investigation candidates; they do not prove ordinary combat eligibility.

## Remaining blocker

`combat_world_properties.py` currently reads an explicitly supplied complete world-property set and an optional activation-age ledger. It does not provide the native mutable world-property manager or its timestamp lifecycle. Registering family 449 against this read-only predicate would falsely advertise execution support.

Further installed-bytecode inspection separates mutation from the age ledger: `eWw` calls `eGj.f/g`, which dispatch directly to `eHN` counters. It does not call `eHC.a(eGj, eHQ)`. That separate helper writes `System.currentTimeMillis()` to the age ledger and then adds the property. Consequently family 449 must not invent an activation timestamp or require this unrelated helper on its direct mutation path.

`eHN` delegates counter changes to `PB` and emits property notifications after add, decrement, and clear operations. World managers are created lazily and discarded when empty. Recover these counter/notification semantics, add an explicit actor producer with separate world/fight namespaces, then implement the runner's asymmetric lifecycle and regression-test stacking, cancellation, invalid IDs, and application modes. No family 449 handler or activation is claimed by this audit.

## Counter mutation is distinct from family 447 side effects

The mapped fight-property operation is `PV.f -> eGj.f -> eHN.c`. It does not execute the separate `eWt` family-447 runner. Reusing that runner's AP/MP, timeline, or QI side effects here would invent behavior. Typed counter mutation and the actual client notification path must remain separate from effect-runner-specific side effects. The six sealed affected definitions share effect 268501 with property 83 (`COMPANION_DISABLED_FOR_FIGHT`), whose mapped fight property is absent; general mapped-property behavior still needs regression coverage.
