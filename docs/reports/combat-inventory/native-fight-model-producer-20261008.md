# Native fight model producer

`GetFightModel` (`eKj`) reads `fcb.dLu().eSS()`: the native model identifier, not the enum ordinal. The original client bootstrap proves that Wakemu's existing `kind` byte is this identifier.

The complete decoded route is packet **12847**, `cvb.fk(ByteBuffer)` → inherited fight ID decoding → signed byte `cvb.mrn` → `cvb.eHb()` → `ckP.c(cvb)` → the first integer argument of `buS.a(int,int,QI,TByteHashSet,TByteHashSet,List)`. That overload calls `fcz.Tv(model)`, then constructs `buH(fightId,model,QI,...)`. The constructor chain `buH` → `fbX` → `fcT` → `fcb` preserves the model argument; `fcb` stores it in `rRU`, which `dLu()` returns.

The original `fcz` initializer assigns **PVE = 2**, **TRAINING_FIGHT_WITHOUT_PENALTIES = 14**, and **DUEL = 65**. These are model IDs; enum ordinals differ. Existing Wakemu friendly fights select training model 14 and retain that policy. No replacement with model 65 was made.

Fresh `Fight` construction now explicitly chooses PVE model 2 as Wakemu's ordinary server policy. This closes initialization criteria before placement envelopes are requested, including offline Ready fixtures. It is a server choice using the proved native enum value, not a claim that an unavailable original server caller was recovered. After successful placement serialization, `placement_messages` binds the exact selected byte (2 or 14) to `native_fight_model`, keeping criteria and the client model identical. An invalid placement request leaves the previous model unchanged. Restored objects with absent or explicitly unknown model authority still fail the existing strict predicate guard.

Verification: `test_combat_bootstrap.BootstrapTests.test_selected_native_model_matches_bootstrap_byte` passed. It checks the fresh PVE policy, both accepted wire models, and rejection without mutation. No services, databases, or client sessions were started or restarted.
