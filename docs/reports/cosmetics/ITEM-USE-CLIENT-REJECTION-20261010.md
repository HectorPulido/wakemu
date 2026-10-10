# Client-side rejection before native learning requests

Status: reproduced by Hector; root cause pending live native predicate inspection.
No speculative gameplay workaround, deployment or restart was applied.

The reported title scrolls 11431 and 7749 and cosmetic learning items display the
native red utilization-requirements message. The server diagnostic log since
2026-10-10 05:20 UTC contains no 13220 or 12659 request. Decoding the current
05:22 capture likewise finds neither opcode. The source inventory remains
unchanged. This is a client validation failure before the acquisition transaction.
Emotes being playable under the default-unlock policy does not establish that
physical emote scroll learning passes the same item-use gates.

Native catalog inspection confirms:

| Item | Action | Native level | Item USE criterion | Action USE criterion |
| --- | --- | ---: | --- | --- |
| 7749 | bIs | 1 | None | None |
| 11431 | bIs | 1 | None | None |
| 14199 | bIs | 1 | None | None |
| 18299 | bIt | 100 | None | None |
| 18300 | bIt | 100 | None | None |
| 18708 | bIt | 0 | None | None |
| 20820 | bIt | 1 | Present | None |

The full native `bGl.ay` eligibility function checks more than the action's
criterion: inventory-owner lookup, selected actor availability, physical
inventory membership, occupation, item usability and level also apply. `bHu.aQ`
checks `fkH.ak(local.Xi(), item.LV())`; `fkH.ag` searches the owned-actor registry
`fkK.suJ` and each actor's physical inventory. Actor registration and login/actor
ownership keys therefore need inspection. An ownership mismatch remains a
hypothesis, not an established cause.

The generic combat guard in `bHu.aQ` does not explain these actions by itself:
`bHu.dYI()` defaults to true and neither bIs nor bIt overrides it. No client
combat bypass was added.

## Read-only diagnostic prepared

`ItemUseDiagnosticAgent.diagnostic()` invokes the installed client's actual
`bHu.aQ` and `bGl.ay` methods for physical action items and reports their input
gates. It does not execute an action, send a packet or change inventory. The
capture inspector exposes it through authenticated `/item-use-diagnostic`.
The capture agent builds successfully, but currently running clients still have
the previous agent loaded. HotSpot attach failed for both current client JVMs;
the bundled client runtime also lacks the attach module. A normal subsequent
client launch will load the diagnostic endpoint.

After that launch, read `.runtime/local/inspector.json` locally and request
`http://127.0.0.1:<port>/item-use-diagnostic` with its `X-Inspector-Key` header.
Do not publish the inspector secret. Compare ownership key, account key,
owner lookup, availability, physical bag membership, action eligibility and full
eligibility before choosing a server or client bootstrap fix.
