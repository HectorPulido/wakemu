# Sparse monster descriptor roles

Offline audit only. HP1/AP0 is not proof of an inert object, NPC, beta, or broken monster. It describes the native base descriptor before parent effects. No inventory rows were excluded and no resources were assigned.

| Reference | Descriptor HP/AP | Explicit native parent spell → summon effect | Interpretation |
| --- | --- | --- | --- |
| 1620 Jamajam | 1/0 | 7350 → 326457 (307) | Proven summon reference; parent also applies state7135 to IsOwnSummon(1620). |
| 3251 Doble Sram | 1/0 | 4603 → 120894 (307) | Proven summon reference; parent applies state3667 and1304 to its owned summon. |
| 4559 Wauwau | 1/0 | 6286 → 240997 (307) | Proven summon reference; parent applies state7529 and conditional1304. |
| 5347 Wonejo | 1/0 | 7348 → 327525 (307) | Proven summon reference behind symbiot capacity/state criteria; exact resource setup still requires parent execution. |

All four summon definitions pass level mode-2, whose interpretation remains the existing native summon contract. They cannot be diagnosed as autonomous ordinary monsters from descriptor resources alone.

Sealed state extraction gives concrete resource setup evidence: state3667 contains effect164835 family950 (AP setter, parameters8,0,1,0) and164836 family951 (MP setter6,0,1,0). State7529 contains339842 family950 (AP8),339999 family950 (AP6), and339843 family951 (MP4); their distinct conditional/target branches remain native rules. Both states contain family913 value-dependent chains ending in family16 HP effects. State7135 also contains913→327021 family16 HP. These are explicit parent-dependent state/effect graphs, not permission to fabricate AP or HP values in the ordinary-monster fixture. Jamajam and Wonejo AP recovery is not established by this receipt.

Fight-property symbols are decoded using the existing native catalog:15 CANT_TACKLE,28 CANNOT_BE_SEDUCED,40 CAN_BE_SEDUCED,78 DO_NOT_USE_TIMESCORE_GAUGE,84 DONT_USE_SUMMONING_MASTERY,101 SUMMONER_VISUAL_COPY. None identifies an inert object. Doble Sram101 additionally agrees with existing native summon visual-copy machinery. No property-based exclusion was introduced.

References3928,5889,5112 have native HP/AP195/8,470/8,1132/10 respectively. Their insufficient-resource failures are a separate case; they do not fit this sparse-descriptor pattern.

General reusable tool: `server/tools/audit_monster_zero_resource_roles.py`. It scans explicit reachable307 edges through owned effect graphs, records source hashes and parent spell/effect identities, and labels sparse unreferenced descriptors as role unproven. It never infers resource inheritance, enables monsters, or changes inventory membership. Across2874 extracted descriptors and the two explicitly supplied effect catalogs:12 sparse descriptors have proven incoming summon edges,45 remain role unproven,2817 are outside HP1/AP0. These counts are metadata for this supplied source scope, not activation counts and not proof that absent edges do not exist elsewhere.

Evidence: `.runtime/monster-blocker-recovery-20261011/zero-resource-roles.json` and `zero-resource-parent-state-evidence.json`. Two new offline unit tests pass, including cycle/unreachable-edge checks; original tests were not edited. No runtime guards, services, or databases were changed.
