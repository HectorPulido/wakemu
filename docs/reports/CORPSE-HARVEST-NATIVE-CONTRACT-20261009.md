# Native corpse harvesting contract

Installed `cXc` is the ordinary monster collection action. Its movement-complete
callback sends `cmC(3, 13481, zc)` with action ID in protobuf field 1 and NPC UID
in field 2. This is the same request as existing `monster_collect.decode_request`.
Existing occupation start 13597 (`cta`) uses occupation kind 6, character UID,
duration in milliseconds, target NPC UID and action ID; completion/cancellation
uses the existing kind-6 occupation-result path.

The published native catalog `monster-encyclopedia.json` preserves per-breed
`collect_actions` with these authoritative fields:

| Field | Meaning |
| --- | --- |
| d | Action reference |
| ckL | Profession reference |
| csM | Required profession level |
| getDuration | Occupation duration in milliseconds |
| csP | Output item reference |
| clT | Native eligibility criterion |

Read-only extraction found 334 actions with exact `IsDead("target")`, all using
profession 74, and 332 with exact `not IsDead("target")`. A further 375 actions
have empty criteria, 11 use `not IsDead()`, and two have quest criteria. Empty or
unknown criteria should not be guessed to authorize corpse collection.

The existing `monster_collect.action` and `validate_action` already resolve the
breed/action pair and enforce level and those exact target-death conditions.
For persisted corpses, the target must explicitly have authoritative HP zero;
their stored original catalog monster describes the living pre-fight instance.

`csR` is true for both living and dead actions and is used by the encyclopedia
indexer `boJ`; it is not evidence that an action consumes a corpse. The client
catalog does not prove output quantity. Any configured quantity must remain an
explicit database policy. User-required corpse disappearance after successful
harvest is the authoritative requested server behavior.

Native visibility is separate: `cXb.bxQ` excludes dead NPCs from living extraction
actions. `cXc` uses its catalog criterion and action availability (`bje.Ds`).
`bje.Ds` checks a disabled action set populated by collection state; blanket
disabling every action would prevent the requested corpse harvest.

Implementation must conserve rewards in one transaction, consume the corpse
only after a successful inventory insertion, and publish native removal to all
peers. Expiry, duplicate completion and concurrent collectors must share the
same durable corpse claim; cancelling or having a full inventory must not
remove the corpse or grant resources.
