# Native casting grammar and predicate denominator

## Scope and original production parser

The input is the complete existing class casting inventory: 851 class/extras/owned-summon references, 968 raw casting expressions and 62 textual function names. It does not expand general monster spells. Every input expression has stable identity `spell:<spell_id>/<location>` and its exact UTF-8 SHA256.

`ExportNativeCastingCriterionAst.java` invokes only the installed original grammar and context-free structural getters. It preserves actual node classes, opcode/type enums, declared argument signatures, literal fields, statement roots and shared node references. It never invokes a context-dependent criterion provider or executes a spell.

The source factory matters: original bPS parses casting criteria with **eQe.tz → eQe.tx → eQd.fGv**. `tx` strips CR/LF; `fGv` supports the complete statement grammar; `tz` combines boolean statements. The older isolated-call exporter used `fGw`, which is useful for isolated expressions but rejects 19 complete assignment scripts. These are valid native scripts, not native parse failures. The new export uses the actual production entry point.

## Results and representation

All **968 original complete expressions parse**. They contain **3,338 lexical call occurrences**, **62 function names**, and **75 structural node classes**. Every textual name maps to one original native predicate class across successful call fragments. Operators, literals, bound variables and selectors remain separate structural classes.

Thirty-two call fragments contain locally bound variables. Parsing such fragments by themselves fails because their bindings are absent; their complete parent scripts parse and contain the bound native structures. These fragment failures are preserved explicitly and are not counted as complete-expression failures.

The native JSONL output is gzip-compressed at `class-casting-native-ast-20261007.jsonl.gz`. Its companion JSON manifest records one-to-one input matching, parser entry point, source/output hashes, observed argument counts, literal strings, native class mapping and local parse comparison. A literal string is not automatically labelled an actor alias. `declared_argument_signatures` comes from original alS.bDC; it is not inferred from observed calls.

The initial stable local parse-only comparison found **961 accepted and seven rejected expressions**, while the original parser accepted all 968. All seven failures are lowercase boolean `true` in `IsOwnArea(true)`, incorrectly treated as an unbound local variable. This is a shared lexical gap affecting 5182, 5183, 5184, 5186, 8505, 8506 and 8507. The parser owner is correcting the generic literal rule; the manifest remains the authoritative versioned comparison after regeneration.

## Reproducible offline command and limits

Run `python3 server/tools/export_native_casting_ast.py` from the repository root. The tool uses one short JVM with a 256 MB maximum heap, parses only the existing scoped expressions, compares the local grammar without providers, and rejects a source-hash change during export. It does not import the runtime effect catalog, connect to a server/database or restart a service.

This proves native parse structure and accepted signatures, not complete semantics of all 62 predicates. A parsed or locally accepted expression can still require an unavailable live provider. Conditional table selection, exact current aliases, state/deck lifecycle, geometry, native call order and client acceptance remain independently tracked contracts.

## Final regenerated comparison

After the generic boolean NAME-token correction, the pinned export was regenerated: **968/968 original and local expressions parse**, and all 968 original parses consume the complete input. The source hashes were stable during the run. The seven lowercase-boolean mismatches are therefore closed at the shared grammar layer, without a spell-specific exception. The parser owner's original Java differential covers 194 cases with zero mismatches.

The final output retains 75 native structural classes and all 62 textual names. Trove short-list fields are expanded as actual primitive values rather than left as opaque structural objects. The 32 isolated bound-variable fragment failures remain expected and explicitly separate from complete-expression acceptance. This is syntax acceptance and native structure evidence; it does not certify all predicate providers or gameplay reachability.
