import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Bounded, read-only native QI occupancy and hover diagnostics. */
public final class CombatPathDiagnostic {
    private static Object call(Object target, String name, Object... args) throws Exception {
        Class<?> type = target instanceof Class<?> ? (Class<?>) target : target.getClass();
        for (Class<?> cursor = type; cursor != null; cursor = cursor.getSuperclass()) {
            for (Method method : cursor.getDeclaredMethods()) {
                if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
                method.setAccessible(true);
                try { return method.invoke(target instanceof Class<?> ? null : target, args); }
                catch (IllegalArgumentException ignored) { }
            }
        }
        throw new NoSuchMethodException(type.getName() + "." + name);
    }

    private static Object field(Object target, String name) throws Exception {
        for (Class<?> cursor = target.getClass(); cursor != null; cursor = cursor.getSuperclass()) {
            try {
                Field field = cursor.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(target);
            } catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }

    private static void read(Map<String, Object> row, String key, Object target, String method, Object... args) {
        try { row.put(key, call(target, method, args)); }
        catch (Throwable error) { row.put(key + "_error", error.toString()); }
    }

    private static Map<String, Object> actor(Object value, Object fight) {
        Map<String, Object> row = new LinkedHashMap<>();
        if (value == null) return row;
        row.put("class", value.getClass().getName());
        row.put("identity", System.identityHashCode(value));
        for (String method : new String[]{"Sn", "Xi", "bcN", "bcO", "bcP", "bcQ", "bcL", "bcK", "bcz", "bcA", "bcB", "baF", "baG", "baK", "doz", "cmZ"})
            read(row, method, value, method);
        try {
            row.put("registered_fighter_is_same", call(fight, "rj", call(value, "Sn")) == value);
        } catch (Throwable error) { row.put("registered_fighter_error", error.toString()); }
        for (String stat : new String[]{"sgD", "sgE", "sgF", "sgG", "sgH"}) {
            try {
                Field definition = NativeDiagnosticReadiness.initializedClass("ffw").getDeclaredField(stat);
                definition.setAccessible(true);
                read(row, stat, value, "c", definition.get(null));
            } catch (Throwable error) { row.put(stat + "_error", error.toString()); }
        }
        return row;
    }

    private static Map<String, Object> cell(Object qi, int x, int y, short z) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("x", x); row.put("y", y); row.put("z", z);
        for (String method : new String[]{"P", "Q", "R", "Z", "aK", "X", "T"}) read(row, method, qi, method, x, y);
        read(row, "selected_surface_valid", qi, "j", x, y, z);
        try {
            Object surface = call(qi, "i", x, y, z);
            row.put("surface_present", surface != null);
            if (surface != null) {
                row.put("surface_height", field(surface, "bbl"));
                row.put("surface_flags", field(surface, "bLD"));
            }
            Object occupants = call(qi, "U", x, y);
            row.put("occupant_slots", occupants == null ? List.of() : call(occupants, "toArray"));
            int index = ((Number) call(qi, "W", x, y)).intValue();
            short[] masks = (short[]) field(qi, "biD");
            row.put("index", index);
            row.put("mask", index >= 0 && index < masks.length ? masks[index] & 65535 : null);
        } catch (Throwable error) { row.put("error", error.toString()); }
        return row;
    }

    public static Map<String, Object> snapshot() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("time", Instant.now().toString());
        result.put("read_only", true);
        if (!NativeDiagnosticReadiness.ready(result, "aTx", "dba", "dbe", "ffw")) return result;
        try {
            Object dba = call(NativeDiagnosticReadiness.initializedClass("dba"), "fcm");
            Object fight = call(dba, "cXY");
            result.put("fight", String.valueOf(fight));
            Object mover = call(call(fight, "dLW"), "dNG");
            result.put("mover", actor(mover, fight));
            Object own = call(call(NativeDiagnosticReadiness.initializedClass("aTx"), "cWt"), "cWu");
            result.put("selected_player", actor(own, fight));
            Object qi = call(fight, "bad");
            Map<String, Object> bounds = new LinkedHashMap<>();
            for (String method : new String[]{"bgq", "bgr", "getWidth", "getHeight"}) read(bounds, method, qi, method);
            result.put("bounds", bounds);
            List<Map<String, Object>> slots = new ArrayList<>();
            Object[] population = (Object[]) field(qi, "biQ");
            Object topology = field(qi, "biR");
            for (int index = 0; index < Math.min(127, population.length); index++) {
                Object obstacle = population[index];
                if (obstacle == null) continue;
                Map<String, Object> row = actor(obstacle, fight);
                row.put("slot", index);
                read(row, "registered_cell_index", topology, "X", (byte) index);
                slots.add(row);
            }
            result.put("slots", slots);
            result.put("slot_capacity", population.length);
            for (String name : new String[]{"biN", "biO"}) result.put(name, call(field(qi, name), "toArray"));
            Object target = call(dba, "fcn");
            result.put("hover", String.valueOf(target));
            List<Map<String, Object>> cells = new ArrayList<>();
            if (target != null) {
                int x = ((Number) call(target, "getX")).intValue();
                int y = ((Number) call(target, "getY")).intValue();
                short z = ((Number) call(target, "bdn")).shortValue();
                for (int[] offset : new int[][]{{0, 0}, {1, 0}, {-1, 0}, {0, 1}, {0, -1}})
                    cells.add(cell(qi, x + offset[0], y + offset[1], z));
            }
            if (mover != null) cells.add(cell(qi, ((Number) call(mover, "bcz")).intValue(), ((Number) call(mover, "bcA")).intValue(), ((Number) call(mover, "bcB")).shortValue()));
            result.put("cells", cells);
            Object frame = call(NativeDiagnosticReadiness.initializedClass("dbe"), "fcF");
            Object route = field(frame, "okg");
            result.put("cached_route", String.valueOf(route));
            if (route != null) {
                read(result, "cached_path_points", route, "bDT");
                result.put("cached_path", String.valueOf(call(route, "dSl")));
            }
            result.put("frame_active", field(frame, "NO"));
            result.put("frame_mp_cache", field(frame, "okf"));
            result.put("frame_used_steps", field(frame, "oke"));
        } catch (Throwable error) { result.put("error", error.toString()); }
        return result;
    }
}
