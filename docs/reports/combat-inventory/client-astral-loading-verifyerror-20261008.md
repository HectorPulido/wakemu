# Astral transfer loading failure — 2026-10-08

The current local client launches at18:38:57 UTC and18:43:03 UTC both fail during own-character creation. The second launch's primary failure at13:43:58.703 Bogotá is:

```
java.lang.VerifyError: Bad local variable type
bPO.eH(Ljava/lang/String;)Ljava/lang/Object; @2965: aload_0
locals: top, top, top, top, top, top, buH, big, bPO
Type top (locals[0]) is not assignable to reference type
```

The stack reaches bPQ.v, fyR.b, biS.zm and own CharacterInformation processing. The new CaptureAgent spell-availability instrumentation injects `ALOAD0`/`ALOAD1` after a native preflight call in bPO.eH. The original StackMap frame at this callsite no longer carries local0. The injected load therefore fails JVM verification before the player can be initialized.

The subsequent13:43:58.803 opcode13974 NPE (`biB.dtw()` on null) is a consequence of failed own-character initialization, not evidence of a malformed world placement packet. Rewards/result ordering and server movement changes do not account for this JVM VerifyError.

The owner of the spell-availability transformer has been notified to repair the instrumentation's actual operand/frame contract. The movement diagnostic is a separate read-only HTTP method and does not instrument bPO or change its frames. No client or service was closed or restarted by this investigation.
