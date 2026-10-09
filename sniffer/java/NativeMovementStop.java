/** Preserve native finish animations; restore actual idle only if finish is unavailable. */
public final class NativeMovementStop {
    private NativeMovementStop() {}
    private static final java.util.concurrent.atomic.AtomicLong ATTEMPTS = new java.util.concurrent.atomic.AtomicLong();
    private static volatile java.util.Map<String,Object> lastFallback = java.util.Map.of("attempts", 0L);

    public static java.util.Map<String,Object> diagnostic() { return lastFallback; }

    static boolean canRestoreIdle(Object actor, Object owner, Object path,
                                  boolean moving, String finish, String idle) {
        return actor != null && actor == owner && path == null && !moving
            && idle != null && !idle.isEmpty() && !idle.equals(finish);
    }

    public static boolean finish(acX actor, String animation) {
        boolean accepted = actor.eg(animation); // Original adf.b invocation, exactly once.
        if (accepted) return true;
        if (!(actor instanceof acS movement)) return false;
        biB player = aTx.cWt().cWu();
        if (player == null) return false;
        String idle = actor.bpT();
        if (!canRestoreIdle(actor, player.dhw(), movement.cjr,
                            movement.cjv, animation, idle)) return false;
        boolean restored = actor.eg(idle);
        lastFallback = java.util.Map.of(
            "attempts", ATTEMPTS.incrementAndGet(),
            "time", java.time.Instant.now().toString(),
            "actor_id", player.Sn(),
            "finish", animation == null ? "" : animation,
            "idle", idle,
            "idle_accepted", restored);
        return restored;
    }
}
