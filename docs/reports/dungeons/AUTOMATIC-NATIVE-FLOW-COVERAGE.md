# Automatic native dungeon flow coverage

Offline extraction on 2026-10-10 applies the Tofullero method to every native
entry route in the inventory. No runtime configuration was installed, and no
server was restarted. Secrets are outside this work.

| Result | Entry routes/maps | Meaning |
| --- | ---: | --- |
| Directed physical linear chain proved | 52 | Exact native arrival, separator doors and native directed paths establish a linear physical traversal. All later doors prevent reaching the selected final exit. |
| Mixed physical gates and internal transport | 4 | A walking chain exists, but literal internal teleports may bypass it; no automatic topology candidate is emitted. |
| Native internal transport graph needs review | 29 | Literal native teleport endpoints and criteria are available; ordering/unlock authority is not established. |
| Open geometry without separator doors | 30 | No physical door separates regions. This does not prove boss bindings, complete connectedness or official encounter order. |
| Physical flow needs review | 24 | Doors exist but no unambiguous full directed entry-to-final-exit chain is proved. |

There are 139 actual entry routes/maps. The inventory has 156 definitions;
17 have no entry route and are enumerated separately in the JSON report. These
counts differ from the earlier 151-map inventory geometry scan because that
scan includes native maps without a usable exterior entry route.

For all resolved arrivals, the extractor flood-fills **directed** native player
movement (height 6, movement type 0, jump capacity 4), with every physical door
cell blocked. It exports the exact first encounter reachable cells to prevent
placing the first group behind a gate. Nonwalkable arrivals are never replaced
by guessed nearby coordinates. Teleport item costs/criteria remain in the full
native records and must be checked before runtime integration.

The 52 proved chains also generate frozen topology candidates containing room
cells, candidate anchors, physical gate order and native exploration geometry.
They are deliberately not installable configurations: roster authority,
first-group engagement, six-player combat formation, safe exterior return and
encounter unlock policy still require validation. Candidate anchors remain
subject to the independent roster/formation validator. Combat and spell
geometry are unchanged. The accepted Tofullero configuration is unchanged;
the general extractor independently recovers gates 26874 then 26875.

Reproduce from the repository root:

```sh
PYTHONPATH=server python3 server/tools/extract_all_dungeon_flows.py \
  --geometry-dir .runtime/local/all-native-dungeon-exploration \
  --templates-dir .runtime/local/native-physical-topology-candidates \
  --output .runtime/local/all-native-dungeon-flows.json
python3 -m unittest discover -s server/tests -p test_all_dungeon_flow_extraction.py
```

The native exporter classes must already be compiled from
`sniffer/java/ExportNativeExplorationMap.java` in the default classes directory,
or supplied through `--classes`. Full cell/path evidence remains in `.runtime`;
the committed JSON summarizes every definition, coverage, native hashes,
directed path lengths and candidate gate chains.
