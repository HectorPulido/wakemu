# Deep native NPC location evidence

## New recoverable coordinates

The client does contain useful named NPC target coordinates beyond decorative
actors. The general quest-target audit now extracts **196 named target records**
across **68 maps**, representing **131 candidate conversational breeds**. Their
XYZ/map values come directly from native objective markers, not generated or
guessed coordinates. The breed association is explicitly inferred from the
localized objective subject (“Talk to <name>”), since the native objective schema
does not contain a direct breed field.

Of the 196 records, 119 have a unique native speaker name in the conversational
catalog. 21 have one or more compatible unconditional dialogue portrait nodes.
Names alone still do not choose the actual initial root or visibility policy.

A read-only geometry crosscheck against the prior installed-client VB/Vy export
found 183 exact walkable cells, 11 markers not on an exact exported walkable cell
and 2 maps without geometry in that snapshot. 110 records combine a unique speaker
name with an exact walkable cell. These checks are retained as separate evidence,
not used to silently move an invalid marker to a guessed nearby cell.

Strong examples:

| Named native objective target | Breed candidate | Map | XYZ | Evidence |
| --- | --- | --- | --- | --- |
| Kabrok | 3580 | 943 | (-155,12,-50) | Quest2547/objective5065 and quest2548/objective5064 independently share the marker; both texts name Kabrok. Cell is walkable. |
| Arh Kayuh | 2986 | 794 | (4,-24,4) | Quest4995/objective10297 names Arh Kayuh. Cell is walkable. |
| Viejo amnésico | 5904 | Multiple | Preserved per objective | Several story-stage markers; cannot collapse into one permanent unconditional actor. |

The Kabrok portrait-compatible unconditional nodes include7279,7281,7283,7293
and7294. Arh Kayuh has6274 and 6275. The marker/name pair does not prove which
node begins the original conversation. The four currently configured local
conversations are still separate local placements, not native-world coverage.

One marker for the old amnesiac uses very large coordinates(8364,8362,0) on
map1211. This illustrates why extraction must preserve invalid/placeholder or
special-scope evidence without automatically enabling every candidate.

## Reproducible generalized extraction

`sniffer/java/AuditNpcQuestTargetAnchors.java` reads the complete native quest
export and extracted conversational catalog. It matches only the subject
immediately following the Spanish native talk objective prefix, using native
breed names and an explicit word boundary. It does not match a name merely
mentioned later in a location description; for example, “talk to the old
amnesiac in Kabrok's shop” cannot be incorrectly assigned to Kabrok.

The matcher is case-insensitive because localized objective subjects can use
lowercase names. All ambiguous matching breeds and possible portrait roots are
retained, along with questID/objectiveID/native marker and the source text.
This is a candidate-evidence exporter, not a runtime spawn importer.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/AuditNpcQuestTargetAnchors.java
java -cp '.runtime/local/classes:client/lib/*' AuditNpcQuestTargetAnchors .runtime/local/native-quest-definitions.json server/protocol/npc-dialogues.json.gz .runtime/local/native-npc-quest-target-candidates.json
```

Artifacts:

- `.runtime/local/native-npc-quest-target-candidates.json`:196 complete records.
- `.runtime/local/native-npc-quest-target-candidates-geometry.json`: same records
  with explicit `exact_walkable`, `not_exact_walkable` or `geometry_missing`.

## All 90 previously unsupported environment chunks

The expanded audit preserves each error and stack. All 90 are
`BufferUnderflowException`: 84 while decoding `acq` interactive-element payloads
in `ach.i`, and 6 in the map grid section `ach.h`. The actor array is read later
by `ach.j`, so ignoring the exception cannot recover an already-decoded complete
actor collection.

All 31,238 installed environment chunk headers contain version0. The original
`ack` loader invokes the same `ach.a(aoG)` decoder; this audit did not miss a
separate version-selected actor decoder. The 90 failures occur only in maps149,
189,219,319,368,489,499 and819. Neither the Kabrok map943 nor Arh Kayuh map794
is affected. The failures remain explicit; no byte-scanning heuristic was used
to fabricate actor records from trailing arbitrary data.

Private detailed output: `.runtime/local/native-npc-placement-audit-deep.json`.
Native original loader evidence: `.runtime/npc-environment-loader-deep.txt` and
`.runtime/npc-ach-deep.txt`.

## Scenario definitions are a different, absent source

The native table enum `eED` identifies SCENARIO/table62 and
SCENARIO_CHALLENGE/table63. Native `Bl/Bp` serializers and `Bm/Bn` event/action
records exist in the installed client JAR. However, neither 62.jar nor 63.jar is
present among the 113 installed bdata archives. The installed Lua callbacks do
not replace those missing original event/action definitions. This distinguishes
“the client has scenario execution classes” from “the client includes all server
scenario parameters.” Evidence: `.runtime/npc-scenario-binary-deep.txt` and
`.runtime/npc-native-table-enum.txt`.

## Safe use of this evidence

A general population importer can use these native named target markers as a
reviewable proposed location ledger, keeping the name inference, original
quest/story stage, geometry result and root-selection provenance explicit.
Permanent exact NPC placements still require validating whether the compass
marker is the actor cell or an approach/area target, and which story conditions
control visibility. That qualification does not erase the recovered coordinates.

No server/client file, service, image or runtime database was modified during
this audit. Only offline Java tools, reports and private evidence were written.

## Activation qualification follow-up

`sniffer/qualify_native_npc_placements.py` now produces a machine-readable qualification manifest from the 196 geometry-checked target records. Run:

```sh
python3 sniffer/qualify_native_npc_placements.py .runtime/local/native-npc-quest-target-candidates-geometry.json .runtime/local/native-npc-placement-qualification.json
```

No record currently qualifies as an accredited native actor spawn with a bound initial dialogue. All 196 lack a unique initial root and a direct native actor identity/spawn/visibility join; 77 additionally have ambiguous speaker identities and 13 lack exact walkable geometry. Ten records (nine distinct cells) meet the weaker combination of a unique localized breed name, exact walkable marker, and at least one compatible unconditional portrait root:

- Kabrok3580: map943 `(-155,12,-50)`, objectives5065/5064; five possible roots.
- Arh Kayuh2986: map794 `(4,-24,4)`, objective10297; two possible roots.
- Viejo amnésico5904: seven records across story maps1360,1209,1211,944,1210,1137; six possible roots. Multiple appearances and quest completion wording make unconditional activation especially unsupported.

These cells come directly from native compass markers. Choosing one of their multiple portrait roots or exposing their story actors unconditionally would introduce additional local behavior. The four existing explicitly local initial actors remain the only configured conversational placements; this audit does not represent them as native world coverage. The qualifier is read-only and does not insert or enable database records. Future extraction can add explicit native spawn, breed, initial-root and visibility contracts, at which point the same general qualification path can admit records without map-specific exceptions.
