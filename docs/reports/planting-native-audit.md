# Seed planting

> **Corrección del cotejo, implementación actual:** la revisión completa de
> `bJt.d/e` demuestra que la llamada desde `cgN.a(cAZ)` solo muestra
> `item.selfDrop`; no resta cantidad. `cYt.eXi` avanza objetivos y tampoco
> actualiza la pila. La afirmación anterior de que12954 consume visualmente
> era incorrecta. Una prueba GUI registró cinco plantaciones confirmadas desde
> una pila5: PostgreSQL quedó sin el objeto y la interfaz conservó5. El servidor
> ahora emite12470 con UID y delta-1 una sola vez después del ACK; replay y
> cancelación no emiten delta. Validación del cambio gráfico pendiente.


Installed item action `bIi` identifies its own profession, minimum profession level and resource reference. ExportSeedActions produced254actions. Resource definitions `aNl` produced533records and their native stage IDs. `bbO.a` creates `bOh` for `aNl.cvt=true` and `bOk` otherwise. Monster resource `cvv` contains monster FAMILY IDs: client `dev.eEa` resolves them through `bRT.Jp`, whose model `bRQ.cqM` is family identity. These integers must not be used as monster reference IDs.

Examples from installed data (not special implementation branches): Wonejo seed30927/action13427/profession74/resource823/family1113; monster reference5525 has family1113. Herb seed4275/action406/profession72/resource60. Wheat seed1752/action644/profession64/resource23.

Native OUT13220 carries action i32, seed UID i64 and bIi payload x/y i32:20bytes. IN12815 `cyK` is byte mun,short hvY,long actor hvW,profession eii i32,ctQ widened from i32,egY i32,x/y i32. The observed ctQ resembles duration, but no universal duration formula is asserted. IN13135 `cAz→zk→cFL` is protobuf ResourcePartition: reference,x,y,z,stage,boolean,time,extra, fields1..8. Native cFL selects `bOi` for monster seed resources and `bOm` for plants.

Official tutorial capture shows stage1 resource creation for both monster and plant seeds, then success12954. It does not prove immediate creation of a mature NPC group. IN12954 `cAZ` is i64+i32+boolean. Its cgN handler reads the success boolean, advances dev state and calls bJt.d/e to display the loss message. Full inspection of that callee confirms no quantity mutation; a committed consumption also requires inventory12470. Unknown prefix identities are caller-supplied rather than guessed. Native Java parsers validated all three produced packet formats.

`planting.prepare` validates lease, owned seed/action, criteria support, learned profession/minimum level and resource, then invokes caller `authorize_cell` for territory, exact height and ecosystem policy. The callback must reject unknown conditions. CursorX can occur before an outgoing request: dev requires region/ecosystem family records, permissions and profession availability. This helper alone does not initialize those client models.

`planting.complete` atomically consumes the SQL-owned seed and inserts a unique resource plus an idempotent operation receipt in SQLite. A caller may also provide verified monster members from an explicit maturation/outcome policy; their families must match the seed. That group is stored in the same receipt as a durable outbox. `publish_groups` registers it in the selected group backend and marks publication only after success. Redis failure leaves the outbox intact and does not consume another seed. This is recoverable publication, not an atomic Redis+SQLite transaction. A process crash after Redis registration but before the SQL mark retries identical IDs; group registration is idempotent. World broadcasting needs equivalent identity-safe handling.

Do not supply immediate NPC members merely because a seed family is known. Native growth timing, specimen selection/probability, weather and territorial rules remain separate work. The implemented state is persistent stage-qualified resource planting and optional validated group publication; GUI integration and ecology bootstrap remain pending.

Three SQLite tests passed: herb planting/one consumption, duplicate receipt, native monster family and failed publication retry, bad stage/unlearned profession rejection. No runtime server changes or official requests were made.

## Native ecological context (closing current work)

`ExportEcologyRegions` now exports720 installed map definitions from `maps/data.jar!/worlds.lib`, loaded by actual cdH/cdI/cdJ. `ecology-regions.json` contains native region IDs, monster/plant families and capacities. cdK records are preserved as raw native spawn definitions; they are not coordinate polygons and must not be used for geometric region selection.

`planting_context.bootstrap(map_id, region_id, monster_counts=..., plant_counts=...)` produces12789/cuE with every native family present and owned local population counts (zero when absent). Java cuE.dp accepted the generated1385/93601 packet, family1113 with population0, plus all three plant families. `authorize_family` rejects a seed outside its native ecosystem: Wonejo is allowed by family in1385/93601, but not1134/79001. Do not enable every seed everywhere by inserting invented families.

Integration still requires obtaining the actual region from the native map partition and sending12789 after map entry and region transitions, replacing captured ecology. Learned profession state must also be initialized/persisted; mere level0 is not equivalent to an absent profession. CursorX also requires native ground aIl.U(x,y,z)>0 and ffY.C(resource,family)>0, territorial permission eDy.oQH, static surface restrictions and occupation checks. InspectPlantGround demonstrates native ground0 at1385(3,-13,1); it does not assert every cell in that map is forbidden. General ground/region extraction and permission initialization have not been completed, so no fully working GUI planting claim is made.

Six focused tests passed (planting and context), plus the actual Java ecology parser. No server restart, official connection, GUI interaction or invented growth was performed. Remaining work is explicitly deferred at the user's request to finish current corrections and stop.

## Resumed native surface implementation

ExportPlantCells resolves exact territory with installed cdI.lVH→bMh.dV(x,y), the native UL/Vf territory lookup, independently of account state. It exports all934 geometry maps successfully: each gzip row is x,y,z,ambient-partition-ID,ground-ID,ecological-region-ID. ach.bt is an ambient partition and is explicitly not used as ecological identity. Native aIl.U supplies ground for each native surface. ExportPlantGrounds exports609 aLp definitions; planting_cells.suitability implements ffY.C override precedence and normalized chance.

Integration APIs: planting_cells.position_context(character) yields12789 for the exact current territory. planting_cells.authorize(store,character,request,seed,resource,open_test_policy=True) permits local tests without species territory restrictions, retains native nonzero ground suitability, rejects ambiguous heights and occupied local resources. The caller must still configure client territorial permissions and learned profession bootstrap, owned runtime operation/growth handled separately. This helper does not fabricate climate, species or maturation rules.

Critical native restriction: Jalato resource192 has no positive suitability on any exported1134 surface; Wonejo823 is100% on ground681 in1385. Open server territory policy alone cannot make the client cursor valid on unsuitable ground: dev.am independently reads installed ffY.C. A deliberate client test override would be a separate explicitly identified policy, not native data. Existing1134 grounds instead have positive resource-specific overrides such as186,309,182,294. Native region and ground tests passed; package manifest needs regeneration after catalog updates.

Open-test policy now derives extra monster families from installed resources that actually have positive suitability on existing grounds of the exact territory. `position_context(...,open_test_policy=True)` adds these rows to12789, filters local counts to advertised families and preserves native catalog unchanged. Thus native Tofu family81 is exposed in1134/79101 because its seed resource182 has suitable grounds509/510; Jalato68 remains unavailable because suitability is zero. Server authorize with the same policy relaxes species-territory restriction but still requires native suitable ground, exact unambiguous height and an unoccupied cell. No client probability override is involved. Maps/cells outside exported territory explicitly raise rather than send an arbitrary region. Parent integration should skip ecology initialization for such cells and continue map loading.

Seven context tests pass, including native territory, zero ground, invalid height and open-policy family derivation. Combined initial planting tests total ten; package manifest regeneration remains parent-owned.

## Explicit any-seed/any-place local test override

The user subsequently authorized a broader policy. With open_test_policy=True, authorize omits soil suitability and species restrictions but still selects an installed walkable surface and rejects local resource occupation. Multiple heights are resolved by shortest directed native movement path from the actor; equal-distance ambiguity rejects. prepare additionally omits learned-profession/minimum-level and item criteria gates only in this policy; owned item/action/lease remain mandatory. position_context advertises every installed monster seed family in open mode, with explicitly local counts.

New OpenPlantingAgent is inert unless -Dwakfu.local.openPlanting=true. In open mode it replaces only dev.am(aBn) planting-preview gate with accepted value1 and ffY.C(int,short) suitability with100. It does not edit installed jars, world geometry or general movement. Actual transformed ffY loaded by a separate Java classloader returned100; unrelated classes are untouched. This is a deliberate test override, not a claim about native ecosystem probabilities. Launch/build integration must include the agent and flag and requires a newly launched client; existing clients are unchanged.
