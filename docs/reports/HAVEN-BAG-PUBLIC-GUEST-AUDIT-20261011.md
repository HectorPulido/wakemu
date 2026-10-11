# Haven Bag public guest policy audit

The current shared implementation already applies Hector's requested public access policy. This audit introduces no additional gameplay change.

| Boundary | Current authority |
| --- | --- |
| Discovery and entry | `ExteriorBags.resolve` requires an actually published bag, same map/instance, matching height and at most six Manhattan cells. `can_visit` permits every visitor, ignoring historical lock/room restrictions. The owner's bag must currently be published by its active connection. |
| Client permission model | `own_bag` uses `visit_permission_payload`: unlocked and public group0 room mask255. Saving permissions publishes the same effective public policy to the bag instance. Stored owner preferences are preserved independently. |
| Garden | The active visited bag supplies authoritative layout/instance. Planting and harvesting use the requesting visitor's own inventory, profession and identity. Installed garden rooms, reachability, furniture occupancy and plant occupancy remain required. |
| Portable crafting | Uses deployed furniture and native interaction cells from the visited layout. Crafting transactions consume and grant only the requesting character's inventory. |
| Chest | Requires an active owner session and the native chest object/action/proximity. Public room rights do not grant chest ownership. |
| Furniture and gems | Dispatcher requires owner session; transaction layer independently checks the account-owned bag instance and physical item ownership. Visitors cannot pack, move, replace or obtain the owner's items. |
| Bag configuration | Permission, room and appearance handlers require the owner session. Public access is traversal/use, not configuration ownership. |
| Return | `HavenBagSession` retains the visitor's original exterior return point and account state. Leaving restores those values rather than the owner's position or inventory. |

Existing regressions cover historical explicit deny/lock ignored for public entry, private-world/distance/lease discovery, visitor identity and owner transfer denial, guest garden rewards, guest crafting topology, foreign furniture UIDs, chest owner checks and transaction isolation. No service operations or client edits were performed by this audit.

## Zaap scope

The installed map9 has a native bag exit, not a mapped Zaap. No Zaap exists among the1,440 portable furniture templates. The native type70/action76 out-only provider is explicitly Haven World, and synthetic957 attaches its menu;957 is not a verified Haven Bag source or destination. Ordinary native travel correctly rejects private bag instances.

The current `world_static`13984 channel only updates objects already installed in a map; it cannot spawn a missing Zaap. Furniture13664 depends on actual installed dynamic templates. Therefore adding a bag Zaap requires an explicitly selected, verified server-owned source projection plus the full bag-leave/travel lifecycle. Do not globally relax transport instance checks or claim an existing public source on map9. Detailed evidence and all45 ordinary destination coordinates: [native Zaap inventory](HAVEN-BAG-ZAAP-AUDIT-20261011.md).

## Complete manual acceptance

1. Use two accounts. The owner opens their bag from the exterior; the visitor stands near its published entrance and enters.
2. The visitor must enter regardless of historical locked/deny settings and traverse every installed room.
3. In an installed garden, the visitor plants using their own seeds, harvests and receives the output in their own inventory. Owner inventory must remain unchanged.
4. At a deployed portable crafting station, the visitor uses their own profession and materials. Rewards and consumption belong to the visitor.
5. The visitor must be unable to open the owner's chest, rearrange gems, pack/move furniture or change bag configuration. The owner must retain those actions.
6. Both leave and reconnect. Each returns to their own exterior position with their own inventory. Re-entering must preserve the owner's layout and garden resources.

Public guest acceptance and a future bag Zaap are separate: successful ordinary bag exit does not demonstrate a destination selector.
