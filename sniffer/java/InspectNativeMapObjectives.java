import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import javax.swing.SwingUtilities;

/** One-shot read-only live diagnostics; no transforms, actions, packets or setters. */
public final class InspectNativeMapObjectives {
    private static Object field(Object object, String name) throws Exception {
        for (Class<?> type = object.getClass(); type != null; type = type.getSuperclass()) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(object);
            } catch (NoSuchFieldException ignored) { }
        }
        throw new NoSuchFieldException(name);
    }

    private static Object call(Object object, String name) throws Exception {
        return object.getClass().getMethod(name).invoke(object);
    }

    private static String identity(Object object) {
        return object == null ? "null" : object.getClass().getName() + "@" + Integer.toHexString(System.identityHashCode(object));
    }

    private static void getter(List<String> rows, String key, Object object, String method) {
        try { rows.add(key + "=" + call(object, method)); }
        catch (Exception error) { rows.add(key + "=UNAVAILABLE:" + error.getClass().getSimpleName()); }
    }

    public static void agentmain(String output, Instrumentation instrumentation) throws Exception {
        Map<String, Class<?>> loaded = new HashMap<>();
        for (Class<?> type : instrumentation.getAllLoadedClasses()) loaded.put(type.getName(), type);
        List<String> rows = new ArrayList<>();
        rows.add("read_only=true");
        rows.add("snapshot_consistency=best_effort_EDT_reads_rendering_thread_may_mutate_state");
        rows.add("captured_at=" + java.time.Instant.now());
        SwingUtilities.invokeAndWait(() -> {
            try {
                rows.add("diagnostic_thread=" + Thread.currentThread().getName());
                Object context = loaded.get("aTx").getMethod("cWt").invoke(null);
                Object actor = call(context, "cWu");
                Object graphics = call(actor, "dhw");
                rows.add("local_actor=" + identity(actor));
                rows.add("local_graphics=" + identity(graphics));
                for (String method : List.of("Sn", "arM", "getX", "getY", "NN")) getter(rows, "actor." + method, actor, method);
                for (String method : List.of("getWorldX", "getWorldY", "getAltitude")) getter(rows, "graphics." + method, graphics, method);
                Object compass = loaded.get("bLp").getMethod("eeY").invoke(null);
                Object scene = field(compass, "coW");
                Object pending = field(compass, "coZ");
                Object registry = field(compass, "coX");
                rows.add("compass_scene=" + identity(scene));
                rows.add("pending_projection_count=" + ((List<?>) pending).size());
                getter(rows, "compass_registry_type_count", registry, "bUv");
                getter(rows, "compass_manager_visible", compass, "isVisible");
                Object widget = loaded.get("fJB").getField("uxR").get(null);
                Object target = field(widget, "uQX");
                rows.add("compass_widget_target=" + identity(target));
                rows.add("compass_target_matches_local=" + (target == graphics));
                getter(rows, "compass_widget_visible", widget, "isVisible");
                Object map = loaded.get("bLc").getMethod("eet").invoke(null);
                getter(rows, "world_map_identity", map, "edI");
                Object mapWidget = call(map, "edo");
                rows.add("world_map_widget=" + identity(mapWidget));
                if (mapWidget != null) {
                    for (String method : List.of("isVisible", "isDisplayCompass", "isDisplayPoints"))
                        getter(rows, "world_map_widget." + method, mapWidget, method);
                }
                if (loaded.containsKey("bLh")) {
                    Object minimap = loaded.get("bLh").getMethod("eeQ").invoke(null);
                    getter(rows, "minimap_identity", minimap, "edI");
                    Object miniWidget = call(minimap, "edo");
                    rows.add("minimap_widget=" + identity(miniWidget));
                    if (miniWidget != null) {
                        for (String method : List.of("isVisible", "isDisplayCompass", "isDisplayPoints"))
                            getter(rows, "minimap_widget." + method, miniWidget, method);
                    }
                }
                // Read only existing native destination values; never invoke an action.
                Method count = registry.getClass().getMethod("bUv");
                Method typeAt = registry.getClass().getMethod("vX", int.class);
                for (int index = 0; index < ((Number) count.invoke(registry)).intValue(); index++) {
                    Object points = typeAt.invoke(registry, index);
                    Method size = points.getClass().getMethod("aWk");
                    Method at = points.getClass().getMethod("vX", int.class);
                    int length = ((Number) size.invoke(points)).intValue();
                    rows.add("destination_type_" + index + "_count=" + length);
                    for (int item = 0; item < length; item++) {
                        Object point = at.invoke(points, item);
                        for (String method : List.of("getX", "getY", "NN", "byi", "byh"))
                            getter(rows, "destination_" + index + "_" + item + "." + method, point, method);
                    }
                }
            } catch (Throwable error) {
                rows.add("diagnostic_error=" + error.getClass().getName());
                rows.add("diagnostic_message=" + String.valueOf(error.getMessage()));
            }
        });
        Files.write(Path.of(output), rows);
    }

    public static void main(String[] args) throws Exception {
        com.sun.tools.attach.VirtualMachine vm = com.sun.tools.attach.VirtualMachine.attach(args[0]);
        try { vm.loadAgent(args[1], args[2]); }
        finally { vm.detach(); }
    }
}
