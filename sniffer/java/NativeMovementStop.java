/** Record native stop transitions while preserving the deployed selected-owner fallback. */
public final class NativeMovementStop {
    private NativeMovementStop() {}
    private static final java.util.concurrent.atomic.AtomicLong ATTEMPTS = new java.util.concurrent.atomic.AtomicLong();
    private static volatile java.util.Map<String,Object> lastFallback = java.util.Map.of("attempts", 0L);
    private static final java.util.LinkedHashMap<Long,java.util.Map<String,Object>> EVENTS = new java.util.LinkedHashMap<>();
    private static final java.util.concurrent.atomic.AtomicLong EVENT_SEQUENCE = new java.util.concurrent.atomic.AtomicLong();

    public static java.util.Map<String,Object> diagnostic() { return lastFallback; }

    public static synchronized java.util.Map<String,Object> diagnostic(long actorId) {
        return EVENTS.getOrDefault(actorId, java.util.Map.of());
    }

    private static biB selectedPlayer() {
        try {
            Class<?> game = NativeDiagnosticReadiness.initializedClass("aTx");
            Object singleton = game.getMethod("cWt").invoke(null);
            return (biB)game.getMethod("cWu").invoke(singleton);
        } catch (Throwable ignored) { return null; }
    }

    private static Object renderField(Object actor, String name) {
        try {
            var field = YF.class.getDeclaredField(name); field.setAccessible(true);
            return field.get(actor);
        } catch (Throwable error) { return error.toString(); }
    }

    private static java.util.Map<String,Object> state(acX actor) {
        java.util.Map<String,Object> result = new java.util.LinkedHashMap<>();
        try {
            result.put("graphic_identity", System.identityHashCode(actor));
            result.put("animation", actor.bkG()); result.put("idle", actor.bpT());
            result.put("finish", actor.bvM());
            for (String name : new String[]{"bHP", "bSD", "bSA", "bSC"})
                result.put(name, renderField(actor, name));
            if (actor instanceof acS movement) {
                result.put("path_present", movement.cjr != null);
                result.put("moving", movement.cjv);
            }
            if (actor instanceof beS graphic && graphic.dgD() != null)
                result.put("actor_id", graphic.dgD().Sn());
            // Never initialize aTx merely to collect diagnostic metadata.
            biB selected = selectedPlayer();
            if (selected != null) result.put("selected_actor_id", selected.Sn());
        } catch (Throwable error) { result.put("diagnostic_error", error.toString()); }
        return result;
    }

    private static synchronized void record(acX actor, String kind, java.util.Map<String,Object> event) {
        try {
            if (!(actor instanceof beS graphic) || graphic.dgD() == null) return;
            long identity = graphic.dgD().Sn();
            java.util.Map<String,Object> row = new java.util.LinkedHashMap<>(EVENTS.getOrDefault(identity, java.util.Map.of()));
            event.put("sequence", EVENT_SEQUENCE.incrementAndGet());
            event.put("time", java.time.Instant.now().toString());
            row.put(kind, java.util.Collections.unmodifiableMap(event));
            EVENTS.remove(identity);
            EVENTS.put(identity, java.util.Collections.unmodifiableMap(row));
            while (EVENTS.size() > 64) EVENTS.remove(EVENTS.keySet().iterator().next());
        } catch (Throwable ignored) { } // A diagnostic must not affect animation execution.
    }

    public static void pathCleared(acS actor) {
        record(actor, "path_clear", state(actor));
    }

    static boolean canRestoreIdle(Object actor, Object owner, Object path,
                                  boolean moving, String finish, String idle) {
        return actor != null && actor == owner && path == null && !moving
            && idle != null && !idle.isEmpty() && !idle.equals(finish);
    }

    public static boolean finish(acX actor, String animation) {
        java.util.Map<String,Object> event = new java.util.LinkedHashMap<>();
        event.put("before", state(actor)); event.put("requested", animation);
        event.put("fallback_attempted", false);
        try {
            boolean changed = actor.eg(animation); // YF.eg means a different requested name, not asset availability.
            event.put("original_return", changed);
            if (changed) { event.put("result", true); return true; }
            if (!(actor instanceof acS movement)) { event.put("result", false); return false; }
            biB owner = selectedPlayer();
            if (owner == null) { event.put("result", false); return false; }
            String idle = actor.bpT();
            if (!canRestoreIdle(actor, owner.dhw(), movement.cjr,
                                movement.cjv, animation, idle)) {
                event.put("result", false); return false;
            }
            event.put("fallback_attempted", true);
            boolean restored = actor.eg(idle);
            event.put("result", restored);
            lastFallback = java.util.Map.of(
                "attempts", ATTEMPTS.incrementAndGet(),
                "time", java.time.Instant.now().toString(),
                "actor_id", owner.Sn(),
                "finish", animation == null ? "" : animation,
                "idle", idle,
                "idle_accepted", restored);
            return restored;
        } catch (RuntimeException | Error error) {
            event.put("original_error", error.toString()); throw error;
        } finally {
            event.put("after", state(actor)); record(actor, "finish_call", event);
        }
    }
}
