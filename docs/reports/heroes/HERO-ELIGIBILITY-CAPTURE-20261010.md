# Hero eligibility capture investigation

The account2 / selected character13 capture was inspected offline. Company
packets sent after06:05 UTC consistently contain account2, chief13, nation0,
guild0, XP1 and activated=true. This includes both standalone COMPANY sections
and combined character-roster/COMPANY sections. The observed packets at06:14,
06:16,06:18,06:20,06:26 and06:29 do not reset the company to an inactive state.

The latest23548 roster at06:25:59 contains ten format5 actors, all owned by
account2. The primary12666 entity at06:26:02 is format10 for character13; its
subsequent13713 entity uses format4. Private payload fixtures were extracted
under `.runtime/local/` for actual native consumer verification; no runtime
state was modified.

Native UI predicates use the account's COMPANY component and the roster's
cached nation. Serialized nation and guild values in isolated current-source
23548 and12093 payloads are0. Native COMPANY decoding/registration preserves
nation0, guild0 and activation=true. No nation/guild settings bypass is justified
by the evidence gathered so far. The live UI predicate/error diagnostic and the
actual captured primary/roster consumers determine the remaining cause.

The native `eDP.d(account, bytes)` updates sections individually through
`eDP.a(account, component)`. That method preserves the account's existing
EnumMap and replaces only the component's own `foI()` key. Cosmetic sections8/9
cannot erase COMPANY section1; there is no map-clear operation on this path.

Actual23053 snapshots observed at06:04:49 and06:14:02 contain
heroes.enabled431=true, heroes.forceAddToParty602=true,
companies.enabled603=true and party.max.own.heroes622=2. No later23053 reset was
observed in that capture.

Headless execution of the real `bit` nation/guild property getters returns true
for all ten captured candidates when supplied their native-decoded model, the
actual company packet and account2 context. `VerifyHeroCompanyEligibility.java`
installs parsed model data directly to omit graphics callbacks; it does not
claim to reproduce the full live UI.

Late company metadata has an explicit native refresh path. Startup registers
`aZt` as an account-data listener. Its COMPANY handler binds and invalidates the
company model, then calls `cZT.eZO()`, which constructs fresh hero rows from
the current account's owned actor registry and republishes `heroesList`.
Therefore initial roster-before-company ordering alone does not establish a
stale eligibility cache or justify a packet-order workaround.

## Confirmed live failure and correction

The later account5/main4 live diagnostic reported native main nation30 and
cached nation30 while company nation remained0. Its capture
`2026-10-10T06-50-44.868315Z-8f4c3037` explains the discrepancy: primary12666
establishes nation0, but subsequent15548 frames71 and88 carry native format22
`FOR_GLOBAL_TO_LOCAL_CHARACTER`, whose NATION_ID is30. The native section
decoder verifies NATION_ID bytes1:5 and NATION_SYNCHRO bytes5:32; the complete
entity is46 bytes. Format4/35 bag updates carry no nation component.

The owned15548 adapter now validates its actor/length envelope and clears the
format22 nation and synchronization fields, retaining guild-local and PvP-money
fields unchanged. This preserves the server's existing neutral nation model
through the complete login sequence instead of changing company nationality
to match foreign fixture data. Regression coverage checks identity rewriting,
neutralization, retained unrelated fields, idempotence and malformed lengths.
`test_wire`:30 tests passed. Live UI acceptance remains required after deployment.
