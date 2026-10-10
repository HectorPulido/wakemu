# Complete mining asset inspection and native harvesting approaches

## Scope and provenance

The inspection enumerates every numeric environment archive and its matching
native topology archive in the installed repository client. It does not modify
client assets, inject gameplay code, publish runtime catalogs, install veins or
restart services. Suitable ground is evidence for a local distribution policy;
it is not an official fixed spawn record.

`NATIVE-MINERAL-METADATA.json` preserves all 51 native profession 73 resource
references and their full stage/action metadata. Reference 643 is not an empty
mineral: its item_reference is 0, but its seven mining actions expose two native
product_references each. For example stage 1/action 1779 requires level 30 and
lists 9797/9787. A server product-selection policy must explicitly resolve that
multi-product contract rather than silently exclude it.

## Decoder evidence and limits

The archive/chunk manifest records byte sizes, SHA256 hashes, environment and
topology headers, missing pairs and independent decode outcomes. Native `ack`
reads one environment header byte, compares it with `ach.bus()` and calls the
native decoder. Native `VF` likewise reads one topology header byte and calls
`VC.ag(header).a(reader)`; `VC.ag` selects the low nibble. The extractor follows
those exact entry points. All inspected environment headers are 0.

The original 1,509 failures were 1,349 topology decode errors, 91 environment decode
errors and 69 chunks whose native surface query rejected a column. Of those 91
environment failures, 84 corresponding topology chunks also fail independently;
7 topology chunks decode independently. These are actual installed-native
exceptions, not an omitted header. Corrupt or incompatible data cannot safely
be made authoritative by padding bytes, guessing a legacy layout or inventing
coordinates. The new extractor continues after individual rejected columns,
retaining later valid columns and recording each rejected query explicitly.

## Correct native collection geometry

Requiring an incoming movement edge to the resource itself was incorrect.
Repository-client `cWn.gu` applies the actor exploration profile and calls
`VF.a(resourcePosition,1,fyk.aaa(profession),false,predicate)`. For profession 73,
`fyk.aaa` returns1 and `VF` enumerates cardinal neighboring positions, resolves
native walkable altitude with `VF.w`, and applies the native height predicate.
`ExportMiningNavigation.java` invokes those actual methods with the player
profile(height 6,type 0,jump 4), separately from combat movement. Resource targets
may therefore be nonwalkable or higher than the adjacent collection surface.

A verified example is map 527 resource position (74,-53,3), ground 161. Native
collection approaches are (75,-53,0), (73,-53,0), (74,-54,0). The former requirement
for a movement edge ending at (74,-53,3) incorrectly rejected this usable target.

Navigation output is under `.runtime/local/mining-full/world-navigation/` and
contains complete native map cells and directed cardinal exploration edges,
plus `resource_approaches` records with position, actual native approaches,
ground_id and eligible_refs. Its manifest distinguishes processed maps from
fully usable targets. Native failures remain explicit; an empty approach list
must never be imported as an accessible vein.

## Reproduction

From the repository root, with existing read-only native catalog DB environment
variables configured:

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 22)
PYTHONPATH=server .runtime/local/verification-venv/bin/python \
  client-tools/inspection/export-mining-surfaces.py \
  docs/reports/mining/NATIVE-MINING-SURFACES-COMPLETE.json \
  --metadata-output docs/reports/mining/NATIVE-MINERAL-METADATA.json \
  --navigation-dir .runtime/local/mining-full/world-navigation
PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python \
  -m unittest test_mining_surface_inspection
```

The wrapper compiles only inspection tools into a temporary directory. No
runtime DB installation occurs. Five existing inspection/planner regression
tests pass; independent native approach and evidence validation is delegated
to Luna. Final extraction totals and manifest hashes are recorded separately
in `NATIVE-MINING-COMPLETE-AUDIT.json` after the scan finishes.
