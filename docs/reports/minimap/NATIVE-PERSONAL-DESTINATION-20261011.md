> Correction after Hector's manual probe: the `?` and downward-arrow markers
> remain on the big map without requesting text. This is valid native placement,
> not an editor failure. Previous automatic-editor instructions are superseded.
> Hector confirms both are absent from the minimap and produce no compass.

# Personal destination, minimap and compass investigation

## Scope and current result

Hector clarified that the reported action is **dragging a marker from the map
palette**. The original installed UI routes that action to a personal note,
not a compass destination. No server fix, deployment, or graphical acceptance
of the reported missing minimap note is claimed. The absence of a compass on
this exact palette route follows the original native action contract.

The installed original client handles personal destination placement locally.
There is no destination request waiting for a missing server handler in the
verified click-to-registration path. Adding an invented response or a database
migration would not repair this path. Server-originated actor/scene state can
still affect its operation; that possibility requires inspecting the failing
live state rather than assuming the client or server owns the defect.

## Verified native contracts

- `cLa.onMapClick(fUu,fKo)`, mode2, constructs a destination and calls
  `bLc.a(JIFFFJLjava/lang/String;Ljava/lang/Object;Lgby;[FZ)V`. Mode1 separately
  creates a `bUY` note. The later confirmed palette drag selects mode1;
  mode2 must not be assumed to be the reported or an accessible UI action.
- `bLc.a` calls `bLp.a(IJIIILjava/lang/Object;LaeQ;Z)V` and stores a local
  destination marker. `bLp.a` targets the compass widget at
  `aTx.cWt().cWu().dhw()`: the current local actor's world-position model.
- `aeM` stores the destination in its local registry. If its scene field
  `coW` is null, coordinate application is queued in `coZ`. Scene attachment
  and a valid current actor therefore matter independently of server traffic.
- The original `aeM` update removes destinations when XY distance is less than
  four cells. Acceptance must select a destination at least ten cells away.
- `bKM.edB` enables both `setDisplayPoints(true)` and
  `setDisplayCompass(true)` on its map widget. Map filters and scene ownership
  should be inspected before changing any server packet.
- `cLa.applyNote` and `bUZ.esc` persist notes to local `notes.dat`; this distinct
  persistence path is not a destination acknowledgement.
- Original compass icon assets `miscellaneous/compassType/2.tga`,
  `miscellaneous/compass.tga` and `miscellaneous/miniMapPoint.tga` exist in
  `client/contents/gui_jar/gui.jar` and are configured in `client/config.properties`.

Private native disassembly is under `.runtime/local/map-objective-*.javap.txt`.
No installed client class, configuration, preference or asset was modified.

## Executable native evidence

`sniffer/java/ProbeNativeMapObjectives.java` checks the installed bytecode route
and executes the original native compass registry with a rendering-free view.
It verifies registration, delayed projection without a scene, actual coordinates
with an attached projection, and cleanup. Three original note-codec roundtrips
independently establish the distinction from local note persistence. The oracle
uses an offline subclass for projection; it does **not** certify the live GUI,
current map identity, current hero handoff, or minimap rendering.

```sh
javac -proc:none --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
  -classpath 'client/lib/*' -d .runtime/local sniffer/java/ProbeNativeMapObjectives.java
java --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
  -classpath '.runtime/local:client/lib/*' ProbeNativeMapObjectives
```

Result: PASS; native destination registry, absent/attached scene behavior and
cleanup; three native note roundtrips. Independent verification remains assigned
to Luna through the Systems coordinator.

## Remaining investigation and acceptance

Capture the following state immediately after the failing destination click:
current local actor ID and coordinates, `bLp` inherited `coW`, `coZ`, `coX`,
`fJB.uxR` inherited target `uQX`, current actor `dhw()`, `bLc.edI()`, current
actor `arM()`, map/minimap widget visibility, and any native exception. Compare
before and after hero switching. A wrong actor identity, scene attachment or
map identity must be traced back to its actual publication/lifecycle source.

The exact palette and existing-point routes are documented below. Do not close
the issue from the offline oracle alone. Hector has now verified minimap note
rendering after reconnect, while immediate rendering fails. A genuine compass
creator remains a separate graphical acceptance step.

## Read-only live diagnostic and attachment result

`sniffer/java/InspectNativeMapObjectivesDirect.java` reads existing objects on
its attach thread without class transforms, actions, packets or setters. This
avoids blocking the agent on Swing EDT. Its snapshots are explicitly best
effort because UI/render threads may mutate the observed objects concurrently.
The earlier EDT variant remains as a diagnostic reference, not the preferred
live tool.

On 2026-10-11 the coordinator found live client PID76870 (UID501). Both the
coordinator's initial attachment and this worker's Direct attachment failed
before `loadAgent`: HotSpot did not create the attach socket within10500ms.
The full JDK22 expected its native temporary directory socket under
`/var/folders/b5/7jggrq9n5nzdgwcl59ffcz040000gn/T/`. No inspector was loaded, no
snapshot was produced, and no EDT operation was queued. The bundled client
JRE21 lacks `jdk.attach`, so it cannot itself run the attachment launcher.
No client restart, class transformation, configuration or preference change
was performed.

Existing capture logs prove the process remains connected to local world port
15556. Its console also reports missing interactive definitions and duplicate
partition elements on AWT-EventQueue-0; these observations warrant separate
scene investigation but do not establish the cause of the destination failure.
No live actor/compass ownership conclusion can be drawn without a snapshot.

To package the preferred diagnostic with a full JDK:

```sh
mkdir -p .runtime/local/map-objective-direct/classes
javac --release 17 -proc:none -d .runtime/local/map-objective-direct/classes \
  sniffer/java/InspectNativeMapObjectivesDirect.java sniffer/java/AttachAgent.java
printf 'Agent-Class: InspectNativeMapObjectivesDirect\n\n' > \
  .runtime/local/map-objective-direct/MANIFEST.MF
jar cfm .runtime/local/map-objective-direct/inspector.jar \
  .runtime/local/map-objective-direct/MANIFEST.MF \
  -C .runtime/local/map-objective-direct/classes InspectNativeMapObjectivesDirect.class
```

The launcher is `AttachAgent`, with three arguments: live PID, absolute agent
JAR path and absolute output path under `.runtime/`. A successful load observes
existing state only. Repeating attachment without identifying the missing
listener/socket would not supply additional destination evidence.


## Follow-up after main-map identity review

The coordinator separately verified that the primary actor already receives the correct map through13974. The position serializer repair for other actors remains useful but does not prove a repair of the reported primary-character destination failure.

A second installed-bytecode review confirms that `cLa.onMapClick` exits for four event modifier flags (`gRm`, `gRl`, `gRp`, `gRo`) and mode2 does nothing if the selected marker type `npJ` is null. Otherwise it creates the target locally, passes world-map `bLc.edI()` to the map marker and calls the compass path. `bLp.a` immediately targets the current actor's `dhw()` graphics and delegates to `aeM`; its registration path has no map-ID, network-request or server-acknowledgement gate. Therefore map identity alone cannot explain both absent compass registration and absent minimap display without observing the failing runtime state.

The current PID76870 remains open. Read-only inspection of the latest6MB of its console found no exception mentioning `cLa`, `bLc`, `bLp` or `aeM`. Repeated `bRQ.kZl` null exceptions arise in another Xulor model and are not established as the destination cause. No client configuration, preferences, classes or process state were changed during this follow-up. No new server helper or response is justified by the presently verified local-only action contract.

## Confirmed palette gesture and note lifecycle

The installed `cRI` map UI binds its palette to `wakfu.map:onLandMarkDrag`.
`cLa.onLandMarkDrag` always writes mode1 and retains the selected icon.
`cLa.onDrop` case1 calls `bLa.aa(x,y,icon)`, selects the resulting `bUY` and
does not open the note editor: its `eTQ` helper only updates map presentation.
`bLa.aa` supplies localized `desc.landMark.personalNote` text automatically.
Editing that text is optional, via the existing editable-note click route.
`cLa.applyNote` updates edited text, calls `bUZ.esc` for
local persistence and `bLa.c` for the current registry label. None of these
steps calls the native destination placement function. The note editor has no
verified target checkbox or compass action. The mode2 destination branch
exists, but no reachable mode2 setter was found in this investigation.

`bUZ` stores notes per native world locally. Native note-codec roundtrips
preserve XY, text and icon; altitude is not serialized and restores as zero.
This establishes a persistence contract, not successful persistence of Hector's
specific live note. `bKM` constructs a separate `bLa` registry for each map
context. `bLa` adds notes to its own PERSONAL_NOTE group, enables that group,
and resolves their icon through `bKQ`. Missing icon definitions prevent a point
from being added. Loading notes uses `bLa.lE` and the global `bUZ` store. No
immediate cross-registry refresh from a newly saved world-map note to the
minimap was established. Hector now confirms the immediate refresh is missing
and reconnect restores rendering; this must not be described as repaired.

A second original relocation branch exists in bytecode: `cLa.onMapDrag` chooses mode4
for an existing map point which is **not** a `bUY` personal note. Later drag-producer inspection proves this
requires an already draggable objective marker; static points of interest do
not reach this branch. Dropping an existing objective calls `bLc.a` and
relocates its compass target. Dragging an existing
personal note selects mode3 and moves that note instead. Native drop validation
can reject a gesture; successful graphical use of mode4 is still pending.

Exact manual acceptance, when Hector is not concurrently using the UI:

1. Outside combat, open the current map with `M`. Open **Marcadores** and drag
   a palette icon onto a reachable cell at least ten cells away. Release it,
   verify that the icon appears on the big map. No text dialog is required;
   do not classify absence of an editor as a rejected drag.
2. Close the map. Check whether the matching note icon appears on the minimap;
   record visibility and the active personal-note filter. A compass is not
   expected from the verified mode1 route. Reopen the map and verify the marker
   cell, then reconnect and verify its local persistence separately.
3. To test a genuine native creator, use **Mostrar** from the right-click
   menu of another visible character's name in chat. The installed action
   creates a target from that actor's actual coordinates. Use only owned
   characters and private messages between those characters for this probe;
   do not send public messages or fabricate a chat author. A target farther
   than ten cells avoids native near-target cleanup.
4. An already created objective can be dragged on the map to relocate it.
   Static points of interest cannot be used to create the initial objective.
   Repeat genuine creation after hero switching and on another map once
   those prerequisites are present. Do not infer reconnect persistence.

These are distinct original gestures. The earlier suggested static-POI
compass bootstrap was disproved by the actual native drag-start gate.
No synthetic server destination command, coordinate hyperlink or ACK was added.
The inspected native `/pos` path prints coordinates; an arbitrary coordinate
link which sets a compass was not proven.

## Independent reachable-drag oracle and live observation limits

`sniffer/java/ProbeNativeMapDragContract.java` verifies the installed UI binding,
mode1 selection, exact note-creation branch, local save calls, separate map
registries and original note coordinates/text. It does not inject mode2.

```sh
mkdir -p .runtime/local/map-drag-oracle
javac --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
  -proc:none -cp 'client/lib/*' -d .runtime/local/map-drag-oracle \
  sniffer/java/ProbeNativeMapDragContract.java
java --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED \
  -cp '.runtime/local/map-drag-oracle:client/lib/*' ProbeNativeMapDragContract
```

Worker and independent Luna result: PASS. Compile/replay log:
`.runtime/local/map-drag-oracle-20261011/oracle.log`. This checks installed
native contracts, not live rendering.
Private disassembly evidence includes `.runtime/local/minimap-drag-ui-consumers.txt`
and `.runtime/local/minimap-cLa-actions.txt`.

The already loaded CaptureAgent inspector subsequently supplied screenshots
without another attachment or client modification. Exploratory palette/map
clicks produced a gold icon visible at the minimap edge, but the exact newly
created note identity and saved text were not established. This observation
**does not** verify the reported drag workflow or fix. No note description was
entered. Screenshots are private under `.runtime/local/minimap-live-*.png`.
The character moved and the map closed while Hector used the client, so all
further UI actions stopped. No inventory, combat, server service, client file
or configuration was changed by this investigation. A possible incidental
local note was not removed because its identity was unconfirmed.

## Exact live palette reproduction and persisted-note decode

A subsequent exclusive UI slot reproduced the confirmed gesture on the live
original client. Two readonly frames showed the same stationary actor and `/d`
chat draft. The map was opened without submitting or deleting that draft.
The second palette icon was dragged from canvas `(1194,94)` to `(1010,600)`.
The new yellow pin appeared on the full map; hovering produced **Nota personal**.
The original local notes file was updated. Closing the map showed no matching
yellow personal-note pin on the minimap in the recorded frame. The actor stayed
at `(-9,-4,-1)` and the `/d` draft was preserved. This establishes the actual
gesture and local persistence, but filter state and minimap refresh still need
isolation before identifying a server repair. A new local note was added; it
has not been removed by editing the client file.

Private screenshots: `.runtime/local/minimap-live-exactdrag.png`,
`minimap-live-exactdrag-hover.png`, `minimap-live-exactdrag-closed.png`.
UI control was then explicitly handed to the Merkasaco worker; no concurrent
clicks were performed. Its native bag entry/return can supply a natural
world-context reset without inventing a protocol message.

`sniffer/java/DecodeNativePersonalNotes.java` reads the original file through
the installed native `aoG` / `bUY` codec without rewriting it. The current
world1134 file contains version1 and three persistent notes:

| XY | Native icon | Text | Distance from current actor |
|---|---:|---|---:|
| 63,-21 | 30 | Nota personal | 73.98 |
| 0,0 | 34 | Nota personal | 9.85 |
| 84,0 | 34 | Nota personal | 93.09 |

All restore altitude0 and `erZ=false`; the native writer persists precisely
entries satisfying `!erZ()`. The newly dragged point is `(84,0)`. The nearby
existing `(0,0)` note helps distinguish clipping from missing registration.

`sniffer/java/ProbeNativeNoteLifecycle.java` verifies the installed lifecycle:
world and minimap contexts have separate note registries; note creation saves
through `bUZ` and updates only its current registry. Attaching the world context
uses `bKM.a(bLo) → bLm.a → bLa.c → eeg → lE → bUZ.mr` to reload saved notes.
Attaching only a renderer does not perform that reload. This is a candidate
explanation for stale minimap registration, not proof that a server reload is
the correct solution or that compass behavior was repaired.

Filter follow-up: `bVa.PERSONAL_NOTE` has native ID4. The native
`selectedLandMarksFiters` default includes4, and the current character has no
contradictory override. More directly, original minimap initialization
`cZX.faf → bLh.edN().eel → bUW.eel` selects all filters and redraws. Thus the
normal native minimap initialization does not support a missing personal-note
filter as the primary explanation. Live object-level filter inspection is not
available through the already loaded inspector endpoints; no agent or client
class was added to obtain it.

The Merkasaco worker returned the actor to `(-9,-4,-1)` at18:39:38Z and
captured `.runtime/haven-zaap-20261011/after-bag-return.png`. That frame still
shows the exterior loading black; it is not a settled rendering result. At
18:41:13Z the next readonly observation already showed the actor inside the
Merkasaco again at `(-6,5,0)`, with the draft preserved. Hector had resumed
play. Consequently no success or failure of note rehydration after the natural
world reset is established from this sequence. No further UI actions occurred.

## Scene bootstrap and compass publication follow-up

Installed `aHo` construction registers both `fJB.uxR` and `bLp.eeY()` as
`aeY` scene listeners. Its inherited `Zi.qX(int)` update invokes each listener's
`a(scene,int)`, supplying the scene to `aeM.coW` automatically. Native
`bLp` placement explicitly targets the currently controlled `biB.dhw()` before
registering a destination. No compass-specific acknowledgement or missing
server bootstrap field was established in this path.

The ordinary13974 handler parses the temporary actor's format28 POSITION,
obtains its native world ID, calls `aTu.fE(world)` and `ciu.nl(world)` leading
to `Wc.a(world,Wa.bnj())`. Current server `haven_bag.map_transition` explicitly
publishes the destination map asset ID, and `wire.position` now similarly
preserves authoritative native map IDs for other actor projections.

Map-marker rendering separately requires `gbx.arM()==fKi.uBu` and rejects an
unset `uBu==-1`. This is a map renderer gate, not the `bLp` scene-compass gate;
a wrong map identity must not be claimed to repair both without evidence.
Compass visibility is toggled during fight entry/exit, which is another
possible runtime boundary if actual destination registration is demonstrated.
The native proximity test is precisely `aBy.bn(dx,dy)<4`; distant targets avoid
ambiguity about that function's distance convention.

## Static-POI probe correction and reachable native creator

The live map tooltip identified **Cuartel general del gobernador** before its
icon was dragged. No compass appeared. Follow-up proves why this is not a
failed destination registration: original drag producer `fQU` requires
`gbx.gTI()==true`. Static POIs are created with that flag false, so the gesture
never emits the mode4 event. `bLc` explicitly enables `pJ(true)` on an existing
objective marker; mode4 relocates that objective. This corrects the earlier
suggestion that a static POI could bootstrap a compass target.

A genuine reachable creator is now established:
right-click another visible character's name in native chat → **Mostrar**
(`desc.show`) → `cJA` → local `dgH`19498 → `cZy` → `bLc.a` → `bLp`.
The handler resolves `bio.mL(name)`, requires visible graphics, and uses the
resolved actor's actual XYZ/world. The menu excludes the current character's
own name. This is distinct from `/follow`, which controls movement and is not
used for the compass probe.

The live roster initially contained only player10, wayo. The coordinator
confirmed existing owned characters8 krozz and9 adaell, allowing a legitimate
owned-hero/private-chat probe. Before any hero addition or message was sent,
a fresh readonly frame showed Hector entering combat, so UI actions stopped.
No public or private test message was sent and no hero roster was changed.
Graphical acceptance of Mostrar remains pending; native creator reachability
is established by installed action and menu consumers.

## Original target-factory bootstrap limit

A bounded offline probe uses the installed client JRE21, original classpath
order, and launcher native arguments, including `-Djava.library.path=natives/`
from the client directory. It constructs both the original `biB(false)` actor
and its real visual representation. The earlier missing JOGL symbol was a
fixture native-path error and is not evidence of a broken installed client.

Calling the original `bLp.a` then reaches `fMX.setTarget`, but fails because
`fHc.gDT()` is null: this standalone process has no initialized native desktop
root. This is an incomplete offline UI bootstrap, not a demonstrated server
defect or a successful compass creation. Reproducible command/output and
probe source are retained under `.runtime/local/compass-mostrar-bootstrap/`.
No installed client files, libraries, or live-client classes were changed.

The remaining positive graphical test is the original **Mostrar** action on
another visible owned character, using private communication only between
characters of the same account. It must run outside active user combat or
other concurrent input. Native note persistence and native target creation
remain separate acceptance items.

## Per-icon palette contract correction

Native `bUS` always includes `bUT(34)` (downward arrow), then the character
manager's unlocked icon values. Icon30 is the question mark on a silver base;
icon111 is a distinct question mark on a gold base. Native `bUT.byh` resolves
`miscellaneous/poi/<ID>.tga` through `pointsOfInterestIconPath`; a scratch contact
sheet of all129 original assets confirms these identities. Every palette item
uses the same cRI grid binding `wakfu.map:onLandMarkDrag`; there is no per-icon
mode override. `cLa.onLandMarkDrag` stores that `bUT` and sets mode1. Dropcase1
creates `bUY` with its exact icon ID and default localized description, updates
the big-map registry and calls map presentation updates. It does not call mode2
or `bLp` compass creation, and does not automatically open a text editor.

The recorded three-item screenshot contains arrow34 followed by two visually
identical silver-base question marks. The source explains how duplicates are
possible: `fqK.cJ` ignores the Boolean result of set insertion and returns true;
`bUS.cJ` consequently appends an unlocked icon on each call. A direct current
manager-value snapshot would be required to certify all three current numeric
IDs; no live UI or attach action was performed in this audit. A screenshot alone
must not be used to relabel the third icon as a distinct destination mode.

The original note editor is reached by clicking an editable existing map point
through `cLa.onMapItemClick` and `dcH`; that is separate from initial palette
placement. Text is optional at creation. This corrects the earlier interpretation
of `eTQ` as an editor opener; its actual implementation calls only `bLc.eeE` and
`eeA`. Private bytecode/asset evidence is under
`.runtime/local/npc-protector-frontier/` (`cLa-marker.javap`,
`cRI-map-ui.javap`, `palette-icon-definitions.javap`, `palette-unlocks.javap`,
`palette-producers.javap`, `poi-contact-sheet.png`).

## Hector manual acceptance: reconnect restores minimap notes

Hector subsequently reports that leaving the game through character selection
and returning preserves these markers on the big map and makes them appear on
the minimap. The downward-arrow marker still produces no compass. This is
positive evidence of local persistence and context-triggered minimap rehydration,
and negative evidence for immediate minimap refresh after accepted placement.
It supersedes earlier uncertainty about whether the drag created a note at all.

The original bytecode separates the same stages: every `bKM` owns its own `bLa`;
`bLa.aa -> bUZ.a` adds the note to local per-world storage, then `bLa.a(note)`
updates only the creating registry. A world-context attachment executes
`bKM.a(bLo) -> bLm.a -> bLa.c -> eeg -> lE -> bUZ.mr`, loading notes into that
context's registry. Renderer attachment alone does not run that reload.
`PERSONAL_NOTE` is category4; minimap initialization selects every filter.
The successful reconnect rendering also rules out a permanently missing icon
asset or a permanently excluded category for the reported markers.

Arrow34 and question-mark30 palette placements both select native mode1; their
shapes do not change the semantics to a compass destination. This route contains
no `bLp` compass call and no outgoing coordinate request. A server-side repair
would need an accredited incoming refresh that rehydrates the existing minimap
registry after placement without resetting unrelated UI state. No such incoming
refresh has yet been proved, and the server does not receive this local note's
creation coordinates. Reconnect is a demonstrated workaround, not a deployed
server-only fix. No client modification is proposed or performed.

The rendering-free original `bUS` oracle ran with `java -Xmx128m` and returned
`default=[34]`, `one_unlock=[34,30]`, `repeated_unlock=[34,30,30]`. It proves
the duplicate-palette possibility without reading or changing the running
client. Source: private `ProbePaletteIconKinds.java` in the evidence directory.
