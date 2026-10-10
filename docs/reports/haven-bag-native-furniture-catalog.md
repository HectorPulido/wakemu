# Native haven bag furniture catalog and placement semantics

Evidence was extracted from the current `client/lib/wakfu-client.jar` with
`javap -p -c` and its bundled binary data readers. This is static native
behavior evidence, not a visual acceptance claim.

## Reproduce the export

Run from the repository root with JDK 22:

```sh
mkdir -p .runtime/local
javac -proc:none -cp 'client/lib/*' -d .runtime/local server/tools/java/ExportHavenBagFurnitureCatalog.java
java -Djava.awt.headless=true -cp '.runtime/local:client/lib/*' ExportHavenBagFurnitureCatalog .runtime/local/haven-bag-furniture-catalog.json
```

The exporter produces 1,440 portable templates and 1,270 item-reference
mappings. It skips two unrelated Challenge interactive types whose graphics
initializers require native graphics support. The compact output is about
1.11 MB and fits the native catalog Redis cache size limit.

`aLM` supplies native template types, parameter strings, interaction masks and
relative-cell arrays. `aLO.cpW()` supplies item actions. The exporter runs
`bHM.a(action.awM(), foI.Wf(action.cnZ()))`, selects `bIx`, invokes its native
parameter parser `w(action.coa())`, and reads the same mapping `dYY()` that
`bIJ` registers in `fla.H(itemReference, templateId)`.

For portable craft type 33, `aLM.cps()` is the craft definition ID. Native
interaction offsets follow `bEG.dST()`: decode the mask through `QV.aa`, add
`QV.beg()` to the placement direction modulo eight, then use `aAS.dyJ/dyK`.
`QV.bkv` is the origin-cell flag. Native world ground-height adjustment still
occurs in the client. All exported `aLM.cpt()` arrays are empty; they do not
establish larger furniture footprints.

## Room policy

`bAs.dTw()` returns `fvG.tll` (`DECORATION`), while `bDc.dTw()` returns
`fvG.tlp` (`CRAFT_TABLE`). These categories determine capacity, not allowed
gem types:

- `fvw.b(content,x,y)` requires an installed primary gem, checks category
  capacity and delegates bounds/collision checking to `fvm.b`.
- `fvw.f(content)` compares the room's count in `content.dTw()` with
  `content.dTw().tlq * gpz()`.
- `gpz()` counts the non-null primary and secondary gems; it does not inspect
  either gem's reference or room type.
- Capacity per installed gem is 127 decorations, 127 craft tables, 127
  backgrounds, one FX decoration and eight merchant displays. Origin-cell
  occupancy independently limits placement.
- `dap.a(fvm,x,y)`, the placement preview, uses the same category capacity and
  room bounds checks.

Therefore a mandatory crafting gem (4264) for portable craft table placement
or use is a stricter local policy, not a restriction established by this
native placement implementation. Decoration placement in any installed room
matches the native checks inspected here.

## Deployment request identity

The current `cKB` and `cKC` furniture interfaces call
`fla.Vd(itemReference)` to get a template ID and then
`bFz.a(templateId, BiConsumer)`. The callback passes this original long
unchanged into `crM(itemReference, long, x, y, z, direction)`, message 13826.
Consequently the second long is a **template ID in this UI path**, not an
inventory UID.

A separate overload `bFz.a(long, fnR, BiConsumer)` passes `fnR.LV()` instead;
that older inventory-oriented path must not be confused with `cKB/cKC`.

`bpI.a(fvk,vf)` obtains the rendered interactive from `bEC.du(vf.afg)`;
`vf.afg` is a template lookup identity in the native content path. Arbitrary
dynamic instance IDs cannot safely substitute for it without additional
native protocol evidence.

## Catalog publication

Runtime loads `haven-bag-furniture-catalog.json` through the versioned native
catalog service. `server/tools/stage_haven_bag_furniture_catalog.py` clones
the current immutable release and adds/replaces this document. It does not
activate the staged release. Publication and image deployment must be
coordinated with the complete current server checkout.

## Correction from live r55 inventory use

Live world events at 2026-10-09 19:19:06, 19:19:39 and 19:19:46 UTC
show `13220` with a 12-byte body rejected by the seed-only decoder. Native
`cqd.aWH()` emits `i32 action_id + i64 item_uid` for `bIx`; the two test
items resolve to actions 466 (6293) and 4543 (17419). These are learning
items, not direct collection placement requests.

The native server replies are `czi` / 13247 (`i32 count`, item references,
boolean) and account component 13873 kind 11 (`fvr`, length-prefixed `jG`
protobuf). The UI uses the learned collection to issue `crM` / 13826.
Migration 083 persists knowledge and learning receipts; the dispatcher now
routes the short inventory action separately from 20-byte seed actions.
Collection placement creates a virtual furniture instance. Packing it removes
that instance and preserves account knowledge; it does not refund the learning
item. The earlier physical transfer implementation alone did not cover this
native inventory-learning flow.

`server/tools/java/VerifyHavenBagFurnitureLearning.java` checks these packets
with installed client classes `czi`, `fvr`, `cqd` and `crM`.
