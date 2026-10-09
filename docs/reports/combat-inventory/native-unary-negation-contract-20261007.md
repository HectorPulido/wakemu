# Native unary exclamation mark

Original eQb tokenizes both `!` and textual `not` as NOT token368. It tokenizes `!=` separately as token369. Original eQd accepts the class criterion `GetEffectCaster() != GetEffectTarget() and not IsCarrying("target") and !IsBreedId("target", 2382)` without needing runtime actors to parse it.

The NOT operand is a native primary expression. Converting `!` into ungrouped Python `not` would change precedence: native `!1 == 2` fails while Python `not 1 == 2` negates the complete comparison. The shared local parser therefore routes both spellings through the same primary-operand handler and emits a grouped negation. Numeric negation operands remain rejected by the existing typed condition validator. Repeated NOT, predicate calls, aliases, grouped comparisons, SHARP expressions and grouped local conditionals preserve the native branch boundary. A bare `!if ... then ... else ...` is rejected, matching original eQd; `!(if ... then ... else ...)` is accepted.

Translation uses actual token boundaries after quote-aware SHARP masking. It never rewrites string contents, quoted exclamation marks or the inequality token. Whitespace ERRORTOKENs produced by Python's tokenizer around its unknown bare `!` character are discarded; the operator itself is handled explicitly. No blind source replacement is used in the parser. Paired synthetic oracle inputs cover both spellings, including numeric/comparison/alias rejection.

`ProbeNativeUnaryNegation.java` executes original eQb/eQd and boolean evaluation without a game catalog or server. `verify_native_unary_negation.py` compares194 paired cases, including truth tables, mixed operators, aliases, markers, local conditionals, malformed typed operands and parse-only real class content: **zero mismatches**. Eleven focused local-criterion tests pass, including existing alias/conditional content and new quote/escape/inequality regressions.

This closes a grammar barrier. It does not make absent predicates, missing actor/cell snapshots, unsupported native branches or unknown providers evaluate false. No services were started or restarted.

## Native boolean literal spellings

Original eQb emits TRUE token390 for both `true` and `True`, and FALSE token34 for both `false` and `False`. Other case forms (`TRUE`, `FALSE`, `tRue`, `fAlse`) are not admitted as boolean literals. The shared parser normalizes only these exact NAME tokens; string tokens and longer identifiers remain unchanged. `IsOwnArea(true)` now parses its actual boolean argument rather than trying to resolve an unbound alias.

All four literal spellings are reserved assignment targets in original eQd. The local parser rejects them explicitly before binding an expression, instead of accepting a meaningless assignment to a Python constant. Actual native differential cases cover all spellings, literal assignments, longer aliases, mixed negation, conditional branches and parse-only area predicates. The combined oracle now contains194 cases with zero mismatches.
