# Same-account native heroes

The native UI exposes one main slot and two hero slots; configuration622
`party.max.own.heroes` defaults to2. This is independent of character creation
capacity. Each hero is a real character belonging to the same account; it keeps
its own inventory, equipment, characteristics and spell decks. No synthetic
accounts or selected-character sessions are created.

Migration098 stores an account-owned main and two persistent, unique hero slots.
Composite foreign keys enforce ownership. Domain mutations fence the real main
selected session, lock the account, reject foreign/deleted characters and enforce
the native slot limit. Duplicate addition and repeated removal are idempotent.
Combat, active rifts and active dungeon membership freeze roster mutations.

`heroes.load_roster(db,store,account_id,main_character_id)` returns complete
`Store.character` snapshots for the main and heroes. Its caller must fence the
main selected session. `add` and `remove` perform their own fences.
`switch_main` changes the selected session and swaps the old main into the hero's
slot in one transaction. Login selection can use `select_main` to align the saved
roster. The dispatcher must flush buffered main positions before mutations.

Verified native requests: cnY12219 adds one character (`>q`); cnZ12006 switches
main with the same layout. Removal is the existing Ou1074 party/member (`>qq`);
16130 is a local UI command and must not be treated as a network opcode.
Acknowledgment cwC12587 uses eEQ.NO_ERROR=1.

Native entitlement has a verified DEV server-configuration path:
heroes.enabled431=true, heroes.forceAddToParty602=true, companies.enabled603=true,
and party.max.own.heroes622=2. This avoids inventing a booster subscription or
character HEROES permission21. COMPANY must identify the real chief and be
activated. Native23548 already loads full owned character actors; it clears
client registries and therefore must not be replayed on addition. csZ13046
(`>qh` identity/signed-size followed by a full entity blob) refreshes an already
loaded owned hero. `hero_wire.refresh` uses the existing real character serializer.

The dispatcher handles add, remove and exploration main switching, with native
success/error acknowledgments for additions. Initial selection and reconnect
activate persisted heroes through native cue12093. Its three length-prefixed
blocks are the full entity, native build set (eQW), and aptitude registry (eQJ).
Native13046 alone updates an existing actor and does not activate a hero. Switching flushes the old main position,
atomically swaps the selected character and hero slot, and publishes the new
world/control context and inventory. A canonical party stores its real online
mains; native party publications add owned heroes with the same account
association, without creating additional sessions. Both login selection and
native switching transfer the main's canonical party membership.
Virtual hero identity rows set the native fga.dpL flag; main rows keep it false.
The real client uses that flag both for hero controls and to deactivate an owned
hero when the canonical party-removal packet arrives.

Dungeon and rift admission expand each fenced main into its persistent owned
roster. Frozen membership includes the real hero character IDs, while every
hero shares its main's real account lease. Admission co-locates followers in
the same transaction as travel. Native hydration queues and dungeon transition
outboxes address selected mains only. Dungeon room travel and final return move
all frozen characters; individual owner departure also returns that owner's
heroes. Rift start validates inactive heroes against the frozen owned roster,
and exterior return moves the owner's heroes alongside the main. Party capacity
counts heroes as well as ordinary mains. Deleting a saved hero removes its slot;
deleting the saved chief clears the saved roster before a future selection.

Automated verification: seven isolated PostgreSQL roster tests and four lifecycle
regressions pass, including owned-hero rift/dungeon entry, owner exit, main-only
delivery and deletion cleanup. Native activation codec/call-site checks pass.
An actual isolated-PostgreSQL Python12093 payload passes the Java cue, entity,
build-set and aptitude consumers. Party snapshot/wire checks pass seven tests;
the existing travel, return and party regression gate passes69tests. The native
Java protocol and configuration consumer oracles also pass.
Combat integration has separate validation gates. Complete in-client acceptance
remains pending; this source task has not restarted or deployed world or changed
the runtime database.

After the complete server build is deployed, use one account with three real
characters. Select the first, open the native Heroes interface and add the other
two. Expect three native group portraits, two occupied hero slots, no additional
login sessions and a re-enabled interface after each acknowledgment. Attempting
a third hero must fail without changing the group. Switch the active character
in exploration: its inventory and control context must change while position
stays fixed, and the old main must occupy the switched hero slot. Remove a hero
through its native group control, then reconnect: the remaining roster must
persist. Finally enter ordinary combat with the full roster, exercise each
character's own spells and verify individual inventory rewards; test dungeon
and rift entry with the same roster using their separate acceptance checklist.

Owned hero activation and exploration control switching use native format10
from the primary owned-character template. Format11 remains reserved for world
appearances: it omits the spell inventory, decks and shortcuts and previously
left hero controls without their own spellbook. The existing owned serializer
now supplies each hero's breed/level spell records, actor-specific spell UIDs,
saved decks and shortcuts on12093 activation and13046 switching. Regression
coverage checks both dispatch paths and distinct breed spellbooks with saved
decks. Manual acceptance must switch between both heroes and the leader in
exploration and exercise their distinct spells in the following combat.

Repeated native12093 activation replaces the owned actor object, but an already
active ID emits no activation event and therefore does not rebuild the cached
hero rows. Publication now sends all owned actor activations before COMPANY,
whose native listener rebuilds those rows, followed by the party snapshot.
This applies to initial entry, return and roster publication. The native local
switch error about an already selected main also covers a missing active owned
target; absence of an outgoing12006 must be diagnosed as a local registry/control
failure rather than assumed to be a backend switch rejection.

Same-map12006 switching preserves the existing native owned actor objects and
loaded scene. Native `SwitchHeroCommand` changes selected control locally before
sending the request;13256 and13974 instead reset and reposition the original
`aTx.cWu()` master. The switch response therefore updates the selected owned
entity with13046, publishes company/party and inventory state, and rebinds the
server's real world session without map-bootstrap packets or12093 reactivation.
Login and return continue to hydrate heroes normally. Regression coverage checks
that switching emits neither a master scene reset nor duplicate activation.

The complete switch handshake is12006 request, owned13046 refresh, then native
13440 result (`u8 result=0`, `i64 target`). Its asynchronous native handler swaps
the company slots and replaces the master actor. Only afterward does the client
send12054 (`i64 target`). The server defers company/party/inventory publication
until that matching completion under the current real session lease; malformed,
foreign or stale completions cannot publish state. Repeated completion is
idempotent. Omitting13440 previously left selected control and master identity
out of agreement despite successful server-side roster changes.

After matching12054, the server sends the selected actor's native15548
format22 update before world publication. The cinematic also waits for
`GUILD_LOCAL_INFO` (`qH` → `biK` → `bkY` → `dbV.kN(true)`), including a null
guild. The owned format10 snapshot lacks that component. Completing the server
handshake alone therefore left the client black. The update reuses the verified
neutral nation adapter; it does not reset the map or replace owned hero objects.
Visual acceptance remains a manual check.

Owned format10 admission contains an HP scalar but no public/private stat
sheet. Its HP now comes from the real character, and each activation and main
switch receives the existing outside-combat format3 progression snapshot. This
provides effective HP limits, resources, XP and level instead of the capture's
3084 HP and the client's uninitialized maximum. Spell casting rules are unchanged.

Saved companies with heroes restore a missing real private party when joining
or refreshing after a genuine ordinary-party leave/disband. Existing ordinary
parties remain intact; no synthetic member sessions or temporary group identity
rotations are used. This ensures the native party receives legitimate member
addition events even when company slots survived an earlier party disband.
