import com.google.gson.Gson;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import javax.swing.SwingUtilities;

/** Read-only snapshot of the active fight's native Qs/Qq and aJG wrapper registries. */
public final class CombatAreaDiagnosticAgent {
    private static final int MAX_AREAS = 512;
    private static Object call(Object object, String name, Object... args) throws Exception {
        Class<?> type = object instanceof Class<?> ? (Class<?>) object : object.getClass();
        for (Class<?> cursor = type; cursor != null; cursor = cursor.getSuperclass()) {
            for (Method method : cursor.getDeclaredMethods()) {
                if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
                method.setAccessible(true);
                try { return method.invoke(object instanceof Class<?> ? null : object, args); }
                catch (IllegalArgumentException ignored) { }
            }
        }
        throw new NoSuchMethodException(type.getName() + "." + name);
    }

    private static Object field(Object object, String name) throws Exception {
        Class<?> type = object instanceof Class<?> ? (Class<?>) object : object.getClass();
        for (Class<?> cursor = type; cursor != null; cursor = cursor.getSuperclass()) {
            try {
                Field field = cursor.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(object instanceof Class<?> ? null : object);
            } catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(type.getName() + "." + name);
    }

    public static Map<String, Object> snapshot() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("captured_at", Instant.now().toString());
        result.put("read_only", true);
        if (!NativeDiagnosticReadiness.ready(result, "aTx", "dba", "aJG", "YP")) return result;
        try {
                Object fight = call(call(NativeDiagnosticReadiness.initializedClass("dba"), "fcm"), "cXY");
                result.put("fight_class", fight == null ? null : fight.getClass().getName());
                if (fight == null) throw new IllegalStateException("No active native fight");

                Object manager = call(fight, "baf");
                result.put("area_manager_class", manager == null ? null : manager.getClass().getName());
                if (manager == null) throw new IllegalStateException("Fight has no Qs area manager");
                result.put("manager_count", call(manager, "bdl"));

                Object visuals = call(NativeDiagnosticReadiness.initializedClass("aJG"), "cjB");
                Map<?, ?> areaWrappers = (Map<?, ?>) field(visuals, "efb");
                Map<?, ?> actorWrappers = (Map<?, ?>) field(visuals, "efc");
                Object actorRegistry = call(NativeDiagnosticReadiness.initializedClass("YP"), "bqw");
                Map<?, ?> liveActors = (Map<?, ?>) field(actorRegistry, "bUL");

                Collection<?> registered = (Collection<?>) call(manager, "bdm");
                List<Map<String, Object>> rows = new ArrayList<>();
                int seen = 0;
                for (Object area : registered) {
                    if (seen++ >= MAX_AREAS) break;
                    long uid = ((Number) call(area, "Sn")).longValue();
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("uid", uid);
                    row.put("reference", call(area, "aeV"));
                    row.put("class", area.getClass().getName());
                    row.put("cell_x", call(area, "bcz"));
                    row.put("cell_y", call(area, "bcA"));
                    row.put("cell_z", call(area, "bcB"));
                    row.put("manager_dm_is_same", call(manager, "dm", uid) == area);
                    row.put("manager_dn_is_same", call(manager, "dn", uid) == area);
                    row.put("aJG_area_wrapper_present", areaWrappers.containsKey(area));
                    row.put("aJG_actor_wrapper_present", actorWrappers.containsKey(area));
                    row.put("YP_actor_wrapper_by_uid_present", liveActors.containsKey(uid));
                    Object wrapper = actorWrappers.get(area);
                    if (wrapper != null) {
                        try { row.put("wrapper_actor_id", call(wrapper, "Sn")); }
                        catch (Throwable error) { row.put("wrapper_actor_id_error", error.toString()); }
                    }
                    rows.add(row);
                }
                result.put("areas", rows);
                result.put("registered_area_count", registered.size());
                result.put("areas_truncated", registered.size() > MAX_AREAS);
                result.put("area_wrapper_count", areaWrappers.size());
                result.put("combat_actor_wrapper_count", actorWrappers.size());
                result.put("area_wrappers", wrapperRows(areaWrappers, manager, liveActors));
                result.put("combat_actor_wrappers", wrapperRows(actorWrappers, manager, liveActors));
        } catch (Throwable error) {
            result.put("error", error.toString());
        }
        return result;
    }

    private static Map<String, Object> wrapperRows(Map<?, ?> wrappers, Object manager,
                                                    Map<?, ?> liveActors) throws Exception {
        Map<String, Object> result = new LinkedHashMap<>();
        List<Map<String, Object>> rows = new ArrayList<>();
        int seen = 0;
        for (Object area : wrappers.keySet()) {
            if (seen++ >= MAX_AREAS) break;
            long uid = ((Number) call(area, "Sn")).longValue();
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("uid", uid);
            row.put("reference", call(area, "aeV"));
            row.put("class", area.getClass().getName());
            row.put("cell_x", call(area, "bcz"));
            row.put("cell_y", call(area, "bcA"));
            row.put("cell_z", call(area, "bcB"));
            row.put("registered_in_Qs", call(manager, "dm", uid) == area
                || call(manager, "dn", uid) == area);
            row.put("live_actor_wrapper_by_uid_present", liveActors.containsKey(uid));
            rows.add(row);
        }
        result.put("rows", rows);
        result.put("truncated", wrappers.size() > MAX_AREAS);
        return result;
    }

    public static void agentmain(String outputPath, Instrumentation instrumentation) throws Exception {
        AtomicReference<Map<String, Object>> result = new AtomicReference<>();
        SwingUtilities.invokeAndWait(() -> result.set(snapshot()));
        String json = new Gson().toJson(result.get());
        if (json.length() > 1_000_000) throw new IllegalStateException("Area diagnostic output exceeds limit");
        Files.writeString(Path.of(outputPath), json);
    }
}
