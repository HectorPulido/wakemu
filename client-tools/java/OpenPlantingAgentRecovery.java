import java.awt.EventQueue;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.IdentityHashMap;
import java.util.Timer;
import java.util.TimerTask;

/** Recovers only the native pre-request movement phase, on the game EDT. */
public final class OpenPlantingAgentRecovery {
    private static final long RETRY_NANOS = 5_000_000_000L;
    private static final IdentityHashMap<Object, Pending> PENDING = new IdentityHashMap<>();
    private static boolean started;
    private static boolean warned;
    private static final class Pending {
        final Object target;
        boolean requested;
        long changed = System.nanoTime();
        String position;
        int retries;
        String reason;
        Pending(Object target) { this.target = target; }
    }
    public static int waitingLimit(Object owner) {
        if (!owner.getClass().getName().equals("dev")) return 98;
        return Math.max(2, Math.min(5000, Integer.getInteger("wakfu.local.plantingQueueLimit", 500))) - 2;
    }
    public static synchronized void pending(Object owner, Object target) {
        if (diagnosticsEnabled()) {
            try { trace("pending owner=" + owner.getClass().getName() + " target=" + (target == null ? null : invoke(target, "eVx")) + " waiting=" + ((java.util.Collection<?>) field(owner, "oaW")).size()); }
            catch (Throwable error) { trace("pending inspection failed: " + error); }
        }
        if (!owner.getClass().getName().equals("dev")) return;
        if (target == null) { trace("clear: native queue exhausted"); PENDING.remove(owner); return; }
        Pending current = PENDING.get(owner);
        if (current == null || current.target != target) PENDING.put(owner, new Pending(target));
        else current.changed = System.nanoTime();
        if (!started) {
            started = true;
            Timer timer = new Timer("Planting-path-recovery", true);
            timer.schedule(new TimerTask() {
                public void run() { EventQueue.invokeLater(OpenPlantingAgentRecovery::recover); }
            }, 1000, 1000);
        }
    }
    public static synchronized boolean beginRequest(Object owner, int x, int y) {
        try {
            Object target = field(owner, "oaX");
            if (target == null || (int) invoke(target, "eXl") != x || (int) invoke(target, "eXm") != y) return false;
            Pending current = PENDING.get(owner);
            if (current == null || current.target != target) {
                current = new Pending(target);
                PENDING.put(owner, current);
            }
            if (current.requested) { trace("request suppressed: already sent target=" + target); return false; }
            current.requested = true;
            trace("request sent target=" + target + " x=" + x + " y=" + y);
            return true;
        } catch (Throwable error) { warn(error); return true; }
    }
    public static boolean acceptCallback(Object callback) {
        try {
            Object owner = field(callback, "obc");
            if (!owner.getClass().getName().equals("dev")) return true;
            boolean accepted = field(owner, "nGo") == callback;
            if (diagnosticsEnabled()) {
                try { trace("path callback accepted=" + accepted + " current=" + field(owner, "oaX") + " waiting=" + ((java.util.Collection<?>) field(owner, "oaW")).size()); }
                catch (Throwable error) { trace("path callback accepted=" + accepted + " inspection failed=" + error); }
            }
            return accepted;
        }
        catch (Throwable error) { warn(error); return true; }
    }
    static synchronized void recover() {
        if (!EventQueue.isDispatchThread()) throw new IllegalStateException("Planting recovery requires the game EDT");
        for (Object owner : PENDING.keySet().toArray()) {
            Pending current = PENDING.get(owner);
            if (current == null) continue;
            try {
                if (field(owner, "oaX") != current.target) { trace("clear: current target changed to " + field(owner, "oaX")); PENDING.remove(owner); continue; }
                ClassLoader loader = owner.getClass().getClassLoader();
                Object application = invoke(Class.forName("aTx", false, loader), "cWt");
                if (!(boolean) invoke(application, "c", owner)) { trace("clear: planting handler inactive"); PENDING.remove(owner); continue; }
                if (current.requested) { reason(current, "waiting for requested action target=" + current.target); continue; }
                Object actor = invoke(application, "cWu");
                Object graphic = invoke(actor, "dhw");
                String position = String.valueOf(invoke(graphic, "bqg"));
                if (!position.equals(current.position)) {
                    reason(current, "movement progress position=" + position);
                    current.position = position;
                    current.changed = System.nanoTime();
                    continue;
                }
                if (invoke(actor, "dtg") != null) { reason(current, "occupation active=" + invoke(actor, "dtg")); current.changed = System.nanoTime(); continue; }
                if (System.nanoTime() - current.changed < RETRY_NANOS) continue;
                current.changed = System.nanoTime();
                current.retries++;
                System.err.println("[PlantingQueueRecovery] retry=" + current.retries + " target=" + invoke(current.target, "eVx") + " position=" + position);
                invoke(owner, "a", current.target);
                // A failed native path must not silently discard the user's selected cell.
                if (PENDING.get(owner) == current && field(owner, "oaX") == null) set(owner, "oaX", current.target);
            } catch (Throwable error) { current.changed = System.nanoTime(); warn(error); }
        }
    }
    private static void reason(Pending current, String reason) {
        if (!reason.equals(current.reason)) { current.reason = reason; trace(reason); }
    }
    public static boolean diagnosticsEnabled() {
        return Boolean.parseBoolean(System.getProperty("wakfu.local.plantingQueueDiagnostics", "true"));
    }
    private static void trace(String text) {
        if (diagnosticsEnabled()) System.err.println("[PlantingQueueRecovery] " + text);
    }
    private static void warn(Throwable error) {
        if (!warned) { warned = true; System.err.println("[Planting-path-recovery] " + error); }
    }
    static Object field(Object owner, String name) throws Exception {
        for (Class<?> type = owner.getClass(); type != null; type = type.getSuperclass()) {
            try { Field field = type.getDeclaredField(name); field.setAccessible(true); return field.get(owner); }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    private static void set(Object owner, String name, Object value) throws Exception {
        for (Class<?> type = owner.getClass(); type != null; type = type.getSuperclass()) {
            try { Field field = type.getDeclaredField(name); field.setAccessible(true); field.set(owner, value); return; }
            catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }
    static Object invoke(Object owner, String name, Object... args) throws Exception {
        Class<?> initial = owner instanceof Class ? (Class<?>) owner : owner.getClass();
        for (Class<?> type = initial; type != null; type = type.getSuperclass()) {
            for (Method method : type.getDeclaredMethods()) {
                if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
                method.setAccessible(true);
                try { return method.invoke(owner instanceof Class ? null : owner, args); }
                catch (IllegalArgumentException ignored) { }
            }
        }
        throw new NoSuchMethodException(name);
    }
}
