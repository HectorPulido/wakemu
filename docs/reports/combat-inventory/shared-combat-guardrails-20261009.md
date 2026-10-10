# Shared combat failure boundaries

The fight97 incident exposed a boundary failure: an NPC serialization exception
escaped the transactional AI runner into the owning socket session. The NPC
candidate was not published, but the healthy player was disconnected and the
remaining owner had no idle callback that retried the NPC turn.

The shared entry now uses `combat_turn_guard.run_shared_npc_attempt` to retain
non-transport preparation failures within combat, emit
`combat_npc_turn_retry_pending`, and retry after two seconds for the same actor
and turn. A changed turn has no inherited cooldown. Transport failures and
resource exhaustion retain their existing cleanup behavior. The guard neither
reconstructs fight state nor synthesizes actions, damage, ACKs or victory. The
existing AI bridge still owns candidate publication and actor/turn claims.

Other implemented boundaries are independent:

- Spell preparation uses a detached candidate; rejected execution does not
  commit the candidate resource/RNG/effect changes.
- Shared idle NPC processing retries only an actual active uncontrolled turn
  with no pending presentation or ACK. Concurrent owners use the existing AI
  turn claim.
- A disconnected recipient is removed from the ACK obligation only when peers
  remain. Every remaining peer still supplies its real ACK; a last-owner
  disconnect preserves the reconnect pause.
- Owned reconnect excludes source-verified withdrawn actors from client
  bootstrap, while retaining server history and rejecting unknown retirement.
- Durable takeover preserves generation fencing; persistence failure does not
  silently transfer ownership. Settlement/reward persistence retains its
  existing transactional receipt contracts; this change adds no reward path.

The guard's regressions cover preparation failure and cooldown, changed-turn
retry, pending ACK exclusion, and propagation of a broken transport. These are
bounded guarantees, not a claim that every combat or persistence failure is
recoverable. A deterministic missing source continues to produce an explicit
retry diagnostic until its underlying implementation is corrected.

## Deployment and verification

Deployed 2026-10-09 as `wakemu-world:combat-guardrails-20261009-r53`,
image SHA256 `3a5134ef1b2ff2d9e2ec260ff20c5a38f0850103f3196e56fd79c5799961aa9b`.
All 624 production file hashes and Python syntax were verified against the build
manifest. The current published catalog compiled successfully. The shared world
container is healthy and its HTTP health endpoint returned success. Ten focused
regressions passed, including concurrent owner callbacks, failure claim release,
cooldown and retry, ACK membership and transport exception propagation.

Manual acceptance: use Cra and Iop in the same PvM fight, ready both, exercise
several full rounds, disconnect one client during an enemy presentation, and
reconnect it. The remaining client must continue after its real ACK; reconnect
must restore the actual roster, spells and current turn. Finish another fight
and verify both leave combat and the dungeon advances once. Repeat a friendly
duel and surrender once from each side. No client should be expelled because
of an NPC preparation error. An unresolved deterministic error must retain
the fight and emit a retry diagnostic rather than fabricate progress.

## Fight 105 regression and coordinated r54 release

The r53 guard used an opaque `object()` claim token. AI context serialization
includes the shared metadata and rejected that token, leaving fight105 at its
NPC turn2 with `Unsupported native context type: object`. The guard prevented
a disconnect but could not repair this deterministic implementation error.
The token is now a unique UUID string. Eight guard/idle tests pass, including
real AI serialization while the claim is held. Diagnostic callback failures
are also isolated while transport/resource failures still propagate.

The full current checkout, including the concurrent external-sword position
correction, was deployed as `wakemu-world:shared-aptitude-recovery-20261009-r54`
(image SHA256 `1aea6b9588210ada788fdd2423f8529c7a7eb5428c9a5fa2c4622c85a3b3e70b`).
All626production file hashes and Python syntax were verified. The complete
catalog revision `b0ed79766ae57e6ef26aa9321d05642522cf4c3d9baf7a22a4ea9d3cefc6f219`
was activated with its matching runtime, and AI was rebuilt from this image.
World and AI are healthy; HTTP health returned success. The catalog compiled
against the staged revision before activation. External marker16tests pass.
Fight105 was already durably abandoned by the user before deployment; no
active-fight recovery or fabricated continuation is claimed. A fresh fight
remains the manual acceptance check for NPC turn progress.
