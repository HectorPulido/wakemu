# Native multiple local markers review — 2026-10-07

The native local criterion grammar accepts independently marked operands such as `#(enemy condition)# or #(ally condition)#`. Treating the complete string as one outer marker loses the grammar boundary and rejects valid class effects. The fix is general and contains no spell exceptions.

## Native evidence

The client lexer `eQb.fzF` emits SHARP token 380 for character 35. Parser `eQd.fGD` consumes SHARP, a full `fGx` expression, and a closing SHARP, then calls `alS.cK(false)` on that expression. Markers therefore wrap individual expression roots. This metadata does not change explicit caster/target predicate arguments. Aggregate localization metadata is not inferred from children.

`sniffer/java/ProbeNativeLocalMarkers.java` exercises the actual client parser using `client/lib/*`. It passes single and multiple operands, Boolean precedence, nested markers, aliases and native conditional expressions. Probe output is retained privately in `.runtime/combat-review-20261007/local-marker-probe/native-proof.txt`.

## Implementation and validation

`combat_local_criteria.py` masks markers outside quoted strings before Python tokenization, parses each balanced marked expression, and unwraps an internal AST node while retaining `native_localization_enabled=False`. Quoted hashes and escaped quotes stay literal. The reserved internal name cannot be supplied by source input. Empty, unbalanced or incomplete marked expressions are rejected. Existing restricted size/token limits remain. Predicate selectors and unknown-authority handling continue through the existing condition evaluator.

Command: `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python -m unittest server.tests.test_combat_local_markers server.tests.test_combat_local_criteria server.tests.test_combat_conditions`

Result: 40 tests passed, including eight new regression tests. These tests verify parsing and evaluation contracts; they do not accredit complete spell execution or client delivery.

## Inventory scope

The previously captured structural class closure has three effect criteria containing at least two marker pairs (effect references 150425, 298328 and 381946); the direct spell tree containing one is 4808. The other two occur below child-effect references. This is a shared grammar repair rather than three individual patches. The count is a structural closure observation, not proof that every branch is reachable or that dynamic sources are exhaustive. No runtime catalog or world service was loaded for this review.

## Source hashes

- `server/wakfu_server/combat/combat_local_criteria.py`: `fcb0b948b8b7c70769f4324a3777ab900c2d71cc07e02008b2f520dfa78e9041`
- `server/tests/test_combat_local_markers.py`: `6be329dd6564d3b023606010f796e6b49d207fafa53ccc1b11d3913e1edc6829`
- `sniffer/java/ProbeNativeLocalMarkers.java`: `7196948febdeae9a5f80662f995930eac70d29515750866f31819b894602ed03`
- `.runtime/combat-review-20261007/class-closure-compact-graph.json`: `cfd7d1dc707426566a378e5ac1b3d445beb247d6afdef2bfa26ba9678386f1b5`
