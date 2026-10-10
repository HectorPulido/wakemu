# 43 — Exploration secrets without quests

**Status: deployed separately in world r63; manual acceptance pending.** Read-only verification matched the running implementation to current source. This agent did not restart services.

Hector requested all exploration secrets for existing and new characters
because quest progression is unavailable. The screenshots show eleven artifacts;
the installed client's native table133 defines exactly eleven.

Migration `091_exploration_secret_access.sql` creates
`settings.exploration_secret_access_policy`, initially
`{"version":1,"unlock_all":true}`. It applies to all accounts and characters
without granting XP, quest rewards, or completed achievements.

The correct inventory is **ACCOUNT_QUEST**, type21. The secrets UI checks
account ownership through `flX.aj`; the character QUEST loader explicitly
skips these items. The server publishes an absolute eleven-item account
snapshot through13873/section4. The local server currently has no independent
account quest-item progression authority to merge into this snapshot; future
quest progression must preserve and merge legitimate account entries here.

Characters also receive exactly four native exploration properties:
jump85, climb105, cloud117, and swim118. Their native readers enable the
corresponding pathfinder capabilities. All four have no fight-property
fallback. The combat engine is unchanged. PostgreSQL policy is read with every
canonical character load; the owned serializer publishes native world-property
components in both initial and remote actor snapshots.

Movement and protocol evidence:
[EXPLORATION-GAP-PROTOCOL.md](../../reports/dungeons/EXPLORATION-GAP-PROTOCOL.md).
`ExportExplorationSecrets.java` extracts the artifact IDs directly from client
data. `VerifyExplorationSecrets.java` and
`VerifyExplorationMovementProperties.java` exercise the installed consumers.

Full manual acceptance remains pending deployment: inspect all eleven secrets
with existing and new accounts; traverse available marked jump, climb, cloud,
and swimming paths; change maps, reconnect, and repeat; confirm no additional
combat stats, XP, or rewards. The Tofu staircase uses ordinary movement capacity
and is distinct from artifact-specific jumps.

## Native artifact catalog

Names below are the installed Spanish localization (content15), not inferred
from screenshots.

| Secret ID | Suggested level | Item reference | Native name |
|---|---:|---:|---|
| 6 | 10 | 18722 | Brújula de travesía |
| 9 | 45 | 20784 | Ocarina dracónica |
| 4 | 50 | 18384 | Cetro excarnado |
| 8 | 65 | 19434 | Patitas de Zurcarák |
| 10 | 80 | 21598 | Varita pitusa |
| 11 | 90 | 21599 | Amuleto luminiscente |
| 1 | 115 | 18103 | Espies rebotis |
| 3 | 120 | 18385 | Awco de apwoximación weal |
| 5 | 140 | 18591 | S.I.D. |
| 7 | 170 | 19113 | Reloj de arena de Xelor |
| 12 | 185 | 22087 | Martillo de Darkli Moon |

The local unlock policy intentionally ignores these suggested acquisition
levels; all artifacts and their exploration powers are available to every
character while it is enabled.

## Item-gated route predicates

Native `eKE.a(eGj,TLongArrayList)` adds ordinary/character-quest item counts,
then adds `flX.aj(accountId, reference)` for each requested reference. The
server's dungeon `GetItemQuantity` predicate now adds the same account artifact
authority, including repeated arguments, signed int32 narrowing, and overflow.
Existing bag quantities remain authoritative. This also covers an artifact
item requirement on an entrance rather than only movement flags. The shared
combat inventory predicate remains unchanged.
