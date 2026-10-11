# Native WP deficit investigation

Offline representative:5889 Kralamar, spell2482. Its sealed base actor profile has WP current0/maximum0, ordinary AP8 and no initial states; the native casting table charges AP5/MP0/WP1. AP is sufficient. The resource blocker is WP, not action points or range.

Native bytecode proof:fcN.b(eGj,fyG,fyF) invokes fyF.e for the selected WP cost, reads eGj.e(ffw.sgF).aYS(), and returns cost<=current. Positive-cost branches additionally apply the existing WP-related property penalties (ffe.sdT/sdU/sdV). There is no NPC-type exclusion in this method. fyF.e selects the actual casting table through A and reads ffw.sgF at the actual spell level; fyF.aaj reads the baseline equivalent.

fcO.a(eGj,fyG,aBn,boolean) invokes that WP check at offsets141–154 when its explicit resource-check boolean is true, returning twK on rejection. False skips the entire AP/WP/MP/other-resource check block, not just WP, so it is not evidence that monsters may ignore WP. bPe.a has the same explicit resource-check switch. No source proof was found that ordinary NPC casting selects false; no bypass was implemented.

Two other recorded cases share the base deficit:3928 Lulú/spell4810 has AP8 and WP0, costsAP3/WP1;5112 Miluba/spell7386 has AP10 and WP0, costsWP1. Sealed initial state trees4081,4091 and6174 have only4,4 and7 reachable effects respectively, with no direct fixed-WP family193/194/952 and no characteristic-copy family1001. Their complete reachable effect operands are preserved in the private receipt. This observation does not rule out later encounter triggers or external grants.

Conclusion:keep these references pending under normal casting rules. Distinguish base WP deficit from missing AP, summon-parent-dependent resources, and casting-geometry failures. A valid recovery must demonstrate a native grant/preparation path or source-proven NPC-specific call contract. Fabricating WP, bypassing costs for all NPCs, or calling a resource-check-disabled path is not justified by this evidence.

Evidence: `.runtime/monster-blocker-recovery-20261011/native-wp-cost-proof/` stores actual javap bytecode and client JAR hash; `wp-deficit-state-evidence.json` stores sealed state graph operands and source hash. Root's `static-resource-deficit-audit.json` remains a baseline observation, not a readiness/exclusion decision. No runtime changes, deployment, PostgreSQL access or heavyweight tests were performed for this investigation.
