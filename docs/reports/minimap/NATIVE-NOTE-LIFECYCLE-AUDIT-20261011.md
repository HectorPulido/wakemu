# Native note and compass lifecycle audit

The installed client separates personal notes, map destination markers, and world-scene compass rendering. No server packet defect has been established by this audit.

## Current manual evidence

On2026-10-11 Hector placed both a question-mark marker and a downward-arrow
marker. Neither requested text. Both remained on the full map, did not appear
immediately on the minimap, and appeared there after returning from character
selection. The arrow still did not activate the compass. This verifies local
persistence and minimap reload for his probe; immediate note refresh remains
unresolved under the no-client-change constraint.

Original `bUS` always includes arrow icon34; the silver question mark is30.
Both use the palette's mode1 note route, without a compass call. Text editing
is optional. Their compass absence is consistent with that route and does not
establish failure of a genuine compass destination. Native **Mostrar** and
quest-objective producers remain separate acceptance paths.

## Reachable user actions

The map palette calls `cLa.onLandMarkDrag`, which selects mode 1. Dropping creates a `bUY` personal note through `bLa.aa`; applying it writes the native local notes file through `bUZ.esc`. Coordinates are not published to the server by this path.

Map marker dragging is produced by `fQU`: it requires `fKi.isDragEnabled`, an actual hovered marker, `gbx.gTI()`, and `!isEditable || !gTJ`. Static points of interest default to non-draggable. Personal notes are editable and draggable and select mode 3. Existing compass markers are made draggable by `bLc` and select mode 4, which relocates the existing destination. Calling mode 2 directly does not prove a reachable user action. No mode-2 setter was found in inspected classes or archived interface resources.

A proven native compass producer is the chat name context menu: right-click another locally loaded character's name and select Spanish **Mostrar** (`desc.show`). `cJq` creates `cJA`, which sends local event `dgH` 19498; `cZy` requires the named actor to be visible and calls `bLc.a` with its actual XYZ/world. This is a local event, not a network opcode. The creator tracks the actor with a five-second timer.

Quest objective checkboxes provide another native producer: `cIQ.compassObjective -> bev.a -> bdS.jh(currentWorld) -> bLc.a(type 7)`. The objective must have an asset-defined target in the current world. This is not an arbitrary coordinate-placement interface.

## Notes and minimap

Each `bKM` owns a separate `bLa`. Creating/applying a note updates the full-map instance and local `bUZ` storage. Attaching a world context rehydrates notes through `bKM.a(bLo) -> bLm.a -> bLa.c -> eeg -> lE -> bUZ.mr`. Attaching only the renderer does not reload storage.

`PERSONAL_NOTE` is category 4. The native preference key is `selectedLandMarksFiters`; its default includes 4. Full-map initialization loads saved selections. Minimap initialization `cZX.faf` calls `bLa.eel`, selecting every filter, so the default-false constructor state does not explain a normally initialized minimap. Persisted notes have `erZ=false`; the writer excludes `erZ=true` notes. The flag has not been proven to mean editability.

An earlier saved file was decoded read-only with `DecodeNativePersonalNotes`: version 1, three ordinary notes at `(63,-21,0)`, `(0,0,0)`, `(84,0,0)`, icons 30/34/34, all named `Nota personal`. The middle note was 9.85 cells from actor `(-9,-4)`. This historical file snapshot is distinct from Hector's later manual reload proof above.

## Scene bootstrap and limits

`aHo` registers both `fJB` and `bLp` as scene listeners. `Zi.qX` supplies the actual scene each update; inherited `aeM.a` assigns `coW`. `bLp.a` explicitly sets `fJB`'s target to the local actor visual. `fKi.uBu` filters map marker worlds and does not control world-scene compass attachment. Native compass cleanup removes a target when `aBy.bn(dx,dy) < 4`.

An offline original-class bootstrap succeeds in constructing the actor and its visual when using the embedded JRE, original classpath order, client working directory, and launcher `-Djava.library.path=natives/`. Without that option, JOGL fails to load. With it, original `bLp.a` needs the UI root (`fHc.gDT`); constructing the original `fQC` then reveals its missing `fMY` projection dependency. Executing original `fJB.aWs()` supplies that watcher, after which target placement requires the compass widget layout (`fMZ.uRt` dimensions are absent offline). These are incomplete offline interface bootstrap dependencies, not proven server bugs. No actual Mostrar-to-compass runtime PASS is claimed.

## Reproducible offline checks

`ProbeNativeMapDragContract.java` checks the real palette event contract. `ProbeNativeNoteLifecycle.java` checks native context attachment and note rehydration. Both use installed class bytecode and compile/run with `--add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED` and classpath `client/lib/*`. `DecodeNativePersonalNotes.java` executes the installed `aoG`/`bUY` reader without modifying the file. No client classes, assets, services, or server behavior were changed by this investigation.
