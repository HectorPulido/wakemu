import java.util.Collection;
import java.util.HashSet;
import java.util.Set;

/** UI-only existential preflight; actual target casting remains unchanged. */
public final class NativeSpellAvailability {
    private NativeSpellAvailability() {}
    private static final java.util.concurrent.ConcurrentHashMap<String, Long> LOG_TIMES = new java.util.concurrent.ConcurrentHashMap<>();
    private static void diagnostic(String kind, Object actor, Object book, Throwable error) {
        try {
            String key = kind + ":" + CaptureAgent.call(actor, "Sn") + ":" + CaptureAgent.call(book, "LV");
            long now = System.currentTimeMillis();
            Long prior = LOG_TIMES.putIfAbsent(key, now);
            if (prior != null && now - prior < 30000) return;
            LOG_TIMES.put(key, now);
            System.err.println("[NativeSpellAvailability] " + key + (error == null ? "" : " " + error));
        } catch (Throwable ignored) {}
    }

    public static Object afterPreflight(Object original, Object shortcut, String property) {
        if (!"usable".equals(property) || !(original instanceof Enum<?> status) ||
                !"twV".equals(status.name())) return original;
        try {
            Object player = CaptureAgent.call(CaptureAgent.call(Class.forName("aTx"), "cWt"), "cWu");
            Object fight = CaptureAgent.call(player, "doI");
            Object actor = CaptureAgent.call(CaptureAgent.call(fight, "dLW"), "dNG");
            if (actor == null || !Boolean.TRUE.equals(CaptureAgent.call(actor, "doz"))) return original;
            Object book = CaptureAgent.call(actor, "js", CaptureAgent.call(shortcut, "LV"));
            if (book == null) return original;
            return withNativeContext(original, fight, actor, book);
        } catch (Throwable unavailable) {
            return original;
        }
    }

    public static Object withNativeContext(Object original, Object fight, Object actor, Object book) {
        if (!(original instanceof Enum<?> status) || !"twV".equals(status.name())) return original;
        try {
            if (actor == null || book == null ||
                    CaptureAgent.call(CaptureAgent.call(fight, "dLW"), "dNG") != actor ||
                    !Boolean.TRUE.equals(CaptureAgent.call(actor, "doz"))) return original;
            Object valid = CaptureAgent.field(Class.forName("fyJ"), "twD");
            Set<String> visited = new HashSet<>();
            // Existing PV coordinates preserve their exact native altitude.
            for (Object target : (Collection<?>) CaptureAgent.call(fight, "dLy")) {
                Object cell = CaptureAgent.call(target, "baM");
                if (candidate(fight, actor, book, cell, valid, visited)) { diagnostic("enabled", actor, book, null); return valid; }
            }
            // QI.X is the native selected-surface height, not an invented z.
            Object qi = CaptureAgent.call(fight, "bad");
            int x0 = ((Number) CaptureAgent.call(qi, "bgq")).intValue();
            int y0 = ((Number) CaptureAgent.call(qi, "bgr")).intValue();
            int width = ((Number) CaptureAgent.call(qi, "getWidth")).intValue();
            int height = ((Number) CaptureAgent.call(qi, "getHeight")).intValue();
            if (width <= 0 || height <= 0 || (long) width * height > 20000) return original;
            Object definition = CaptureAgent.call(book, "gtZ");
            int range = ((Number) CaptureAgent.call(definition, "i", book, actor, null,
                    CaptureAgent.call(fight, "bbg"))).intValue();
            int radius = ((Number) CaptureAgent.call(actor, "bcL")).intValue();
            if (range < 0 || radius < 0 || (long) range + radius > 20000) return original;
            Object source = CaptureAgent.call(actor, "baM");
            int sourceX = ((Number) CaptureAgent.call(source, "getX")).intValue();
            int sourceY = ((Number) CaptureAgent.call(source, "getY")).intValue();
            int reach = range + radius;
            var constructor = Class.forName("aBn").getConstructor(int.class, int.class, short.class);
            for (int y = Math.max(y0, sourceY - reach); y < Math.min(y0 + height, sourceY + reach + 1); y++) {
                for (int x = Math.max(x0, sourceX - reach); x < Math.min(x0 + width, sourceX + reach + 1); x++) {
                    short z = ((Number) CaptureAgent.call(qi, "X", x, y)).shortValue();
                    Object cell = constructor.newInstance(x, y, z);
                    if (candidate(fight, actor, book, cell, valid, visited)) { diagnostic("enabled", actor, book, null); return valid; }
                }
            }
        } catch (Throwable unavailable) {
            diagnostic("failure", actor, book, unavailable);
        }
        return original;
    }

    private static boolean candidate(Object fight, Object actor, Object book, Object cell,
                                     Object valid, Set<String> visited) throws Exception {
        if (cell == null) return false;
        String key = CaptureAgent.call(cell, "getX") + ":" + CaptureAgent.call(cell, "getY") +
                ":" + CaptureAgent.call(cell, "bdn");
        if (!visited.add(key)) return false;
        // Same native query checks cost, turn, usage, criteria, range and LOS.
        return CaptureAgent.call(fight, "a", actor, book, cell, true) == valid;
    }
}
