# Haven Bag guest access review — 2026-10-09

## Acceptance and confirmed failure

Hector confirmed that the **owner can move between rooms**. The **guest cannot**; the screenshot shows the wheat harvesting tooltip reporting `Esta sala está inaccesible`. Other tested Haven Bag behavior is provisionally accepted. This issue is not an owner movement regression.

This review changed documentation only. It did not change code, stored permissions, or services.

## Evidence

A read-only aggregate query against the current local PostgreSQL runtime found 18 Haven Bags. All 18 have the same configuration: unlocked, group ALL (0), rights 1, no individual overrides. No account or character identities were collected in the output.

The native client was inspected with `javap` against `client/lib/wakfu-client.jar`:

| Room type | Permission mask |
| --- | --- |
| Commerce | 1 |
| Decoration | 2 |
| Craft | 4 |
| Sufokia | 8 |
| Garden | 16 |
| Amakna | 32 |
| Brakmar | 64 |
| Bonta | 128 |

`fvy` builds the mask as `1 << room_type`; `fvz.b(fvy)` checks the corresponding bit. Therefore rights 1 is commerce-only, not a general permission to visit every installed room. The client room/path checks use the room gem type and the visitor's rights. This accounts for the owner/guest difference and the inaccessible garden tooltip.

`server/migrations/003_character_domains.sql` sets the commerce-only default. `server/wakfu_server/items/haven_bag.py` uses the same fallback and serializes saved permissions. Its current SHA256 matches the recorded r59 manifest (`.runtime/local/diagnostics/performance-r59-manifest.json`); this is manifest evidence, not a new inspection of the running image.

## The central console is not the permissions console

Native `bAE` (DimensionalBagAdminConsole, interactive type 34) opens room management (`dat`) and appearance management (`dal`). Permissions are exposed by `bAX` (DimensionalBagLock, interactive type 44), through `dar.fbj()` and `dimensionalBagRoomAdministrationDialog`.

Consequently, the reported inoperative central console and guest permissions are related usability gaps, but should not be treated as the same client action. The permission console's actual scene presence and click behavior still require verification; this review did not drive the graphical client.

## Additional incomplete behavior

- The server handler for permission request 12580 persists settings and sends update 13522 to the owner's connection. It does not republish the exterior discovery snapshot or broadcast the permission update to current guests. Later entry can use stale published owner configuration until the bag is republished.
- `haven_bag_garden.active_character()` and `room_at()` require the live instance to equal the visiting character's own `instance_id`. A visitor in another account's bag fails this owner-only condition. Harvest preparation calls this path. Opening client room rights alone will therefore not implement guest harvesting.
- `Movement.validate()` checks path continuity and endpoint consistency, not Haven Bag room rights. The authoritative policy needs a shared owner/visitor resolver rather than relying on client-side room restrictions.
- Existing tests cover lock state, entry, individual denial, shared-account ownership, and permission serialization. They do not establish guest traversal across room types, live rights propagation, or guest garden interactions.

## General implementation proposal

1. Introduce one authoritative Haven Bag context resolving the active bag owner, account ownership, saved layout, and effective individual/group room masks. Reuse it for entry, movement, gathering, planting, and furniture/workshop interactions.
2. Make the native lock/permissions console available and functional; investigate the central room/appearance console separately.
3. Define the intended public default explicitly. Mask 23 grants commerce, decoration, craft, and garden; mask 255 grants all current room types. Do not overwrite explicit individual denials or intentionally restricted owner configuration. Existing commerce-only defaults require a deliberate migration policy if changed.
4. Refresh the published owner configuration and current guests when permissions or layout change, using native updates. Specify what happens when access to a currently occupied room is revoked.
5. Extend garden authorization to guests only when the shared policy grants the room, preserving the visitor's inventory and account ownership. Do not replace the visitor's identity with the bag owner's identity.

## Required verification after implementation

Automated coverage should include every room type, owner and same-account access, explicit visitor overrides, default group rights, locked bags, denied destinations, rights changes while a guest is present, exit/reentry, and guest garden resource operations. Verify workshop access through the same policy.

One complete manual acceptance journey: the owner installs commerce, decoration, craft, and garden rooms; grants guest access using the native permission console; a second-account guest traverses all allowed rooms, uses the workshop, and harvests an adjacent garden plant. The owner revokes garden access and the guest sees the intended update without reconnecting. Exit, reenter, and reconnect both accounts to confirm persistence. The owner remains able to manage their rooms throughout.

Do not ask Hector to repeat the current inaccessible-room probe before a relevant fix is deployed: the failure is already confirmed.
