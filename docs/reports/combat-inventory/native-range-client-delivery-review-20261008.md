# Range authority and client delivery

## Two independent native writers

`resolve_range` uses live characteristic 11 (`RANGE`) and the independent
`spell_range_modifiers` map keyed by native spell category. It applies category
changes before `fcj` characteristic/carry/property-2 calculation. Category range
changes are not characteristic 11 and cannot be reconstructed from a `tA`
characteristic snapshot.

The fresh owned snapshot evaluates supported equipment and aptitudes once,
installs complete live characteristic metadata, and initializes category maps
empty before passives execute. Unsupported equipment effects reject or enter
an explicitly selected initialization policy; they do not prove range parity.
`actual_actor_stats` serializes the live snapshot rather than replaying equipment.
`snapshot_characteristics` includes characteristic 11's actual signed current
value and native raw bounds. Player, monster and registered summon snapshots
use this same characteristic serializer.

Native category family 1066 (`eZg`) changes the independent category map and
emits application 13497, with outer amount and AdditionalDatas field 10 category.
Removal 13560 preserves that original payload and reverses its exact amount;
the map keeps zero entries, matching native adjust-or-put behavior. Existing
unit tests cover stacking, signed reversal, expiry and the independent AP map.

## Concrete reconnect gap

At investigation time `CombatSessionAdapter.actor_payload` returned
`actor_effects()` (the empty signed-short effect count) for active actors. This
means reconnect/bootstrap characteristic delivery may preserve RANGE11 while
the effect snapshot discards retained category modifiers and state carriers.
The server category map remains populated. This is a concrete general client
parity gap, independent of a particular Cra spell.

`summon_casting` owns the active reconnect producer and adapter correction.
It must use the actual complete retained population and the correct native
snapshot caller contract (`fSp` versus `mv`), including state-first partitioning,
payloads and wall-clock timers. A partial 649 replay or a characteristic-only
fix does not close this gap. Native within-partition `HashMap<Qe,...>` identity
ordering remains a separate source limitation documented in the remote effect
source review.

## Validation boundary

The original wire parity test patched characteristic metadata and compared
primitive calculation/application bytes. It did not establish production
reconnect behavior. A new regression uses actual `build_player_snapshot`,
installed native characteristic metadata, `actual_actor_stats`, and the
production 12873 envelope to verify live signed RANGE11 values without a
mocked native catalog. This tests ordinary characteristic delivery; it does
not claim complete client UI parity or reconnect completion. No service,
database, AI module, or client runtime was changed during this investigation.
