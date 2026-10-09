# Current client/server range and tooltip contract

Scope: targeted original-client bytecode, pure original-client probes, current Python producer review and focused wire regressions. No world/client connection, service restart or database access. The earlier7200 boundary and full casting range oracle was not repeated.

## Original common defect and current correction

The original Ocra report identified real ordinary-class casting defects: baseline tables instead of the selected conditional table, absent exported modifiable flag, and missing live RANGE/category/carry/property-cap calculation. Current ordinary and granted casting share the native conditional selector and resolve_range. Native category modifiers are applied before generic RANGE11, with Java int wrap. The native actor snapshot owns RANGE11 and the modifier maps; live serialization consumes that same snapshot instead of replaying equipment after combat effects.

Spell inventory and the server's complete owned spellbook share owned_spell_records. Native decode clamps supplied levels to each definition maximum, with deck cap0 preserved as a real execution level. GetSpellLevel reads this book independently of deck membership. Critical versus ordinary effect roots do not replace the selected casting range table. cwU mandatory empty-cell and cwN traversal option are now distinct metadata, not range additions.

## Tooltip is different from actual casting mask

The original `bPO.elJ` tooltip reads selected fyF.i maximum, including category modifiers. For a bound caster, it adds characteristic RANGE11 if the selected flag is modifiable, then always clamps to at least elK minimum. It does not apply fcj's maximum>=1 gate, the carried extra1, or property2's cap1. With an unbound caster it returns the selected base/category maximum through the local preview source without that bound-caster RANGE addition.

Actual target validation in `fcO.a` instead calls fyF.j/i/d with the actual target and fight, then fcj.a for the effective maximum. Current server effective_range mirrors this branch. Tooltip condition selection also supplies null target, whereas actual casting supplies the selected target. A reported tooltip discrepancy therefore must be distinguished from a target-mask discrepancy; changing authoritative casting to the tooltip formula would introduce new errors.

`ProbeNativeTooltipCastingRange.java` calls original bPO.elJ and original fcj.a with controlled actual native method inputs. Five cases pass:

| Input | Tooltip maximum | Target-mask maximum |
|---|---:|---:|
| minimum2, maximum6, modifiable, RANGE2 |8|8|
| same, carried |8|9|
| same, property2 cap |8|1|
| minimum0, maximum0, modifiable, RANGE2 |2|0|
| minimum2, maximum1, unmodifiable |2|1|

These differences are original-client behavior, not evidence to override server range. The probe does not load catalogs or connect a client. Private targeted disassemblies are `/tmp/wakemu-range-bPO.txt` and `/tmp/wakemu-range-fcO.txt`.

## Live serialization parity

`actual_actor_stats` uses snapshot_characteristics whenever a native actor snapshot exists. RANGE11 is serialized with its live current value and actual native bounds. The runtime condition adapter obtains RANGE from that same live effect_stats population. The category1066/eZg handler separately serializes the actual modifier amount as running-effect value and category as AdditionalDatas field10; its server map receives the same amount. Ordinary removal reverses the owned amount.

New lightweight `test_combat_casting_range_wire_parity` decodes actual characteristic and1066 packet serializers, reconstructs the client inputs, and compares them with server resolve_range. All18 category IDs are exercised at RANGE-2,0,3:54 combinations with no mismatch. A second regression changes live RANGE from1 to-3 and verifies serialization follows the changed snapshot. Two tests passed in0.107 seconds. These are shared producer tests, not a claim to have executed every spell or every class UI.

No additional current range calculation or wire bug was proven in this pass. Remaining full static casting geometry, LOS and terrain work belongs to the common eligibility integration. Actual connected-client mask acceptance must still be manually checked after the complete validated build is deployed; no live result is claimed here.
