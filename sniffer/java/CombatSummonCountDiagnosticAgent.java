import com.google.gson.Gson;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.*;
import javax.swing.SwingUtilities;

/** Read the original client summon-count inputs without mutating combat. */
public final class CombatSummonCountDiagnosticAgent {
    private static Object call(Object object, String name, Object... args) throws Exception {
        Class<?> type = object instanceof Class ? (Class<?>) object : object.getClass();
        for (Class<?> cursor = type; cursor != null; cursor = cursor.getSuperclass()) {
            for (Method method : cursor.getDeclaredMethods()) {
                if (!method.getName().equals(name) || method.getParameterCount() != args.length) continue;
                method.setAccessible(true);
                try { return method.invoke(object instanceof Class ? null : object, args); }
                catch (IllegalArgumentException ignored) { }
            }
        }
        throw new NoSuchMethodException(name);
    }
    public static void agentmain(String output, Instrumentation instrumentation) throws Exception {
        Map<String,Object> result = new LinkedHashMap<>();
        SwingUtilities.invokeAndWait(() -> {
            result.put("time", Instant.now().toString());
            try {
                Object fight = call(call(Class.forName("dba"), "fcm"), "cXY");
                result.put("fight", String.valueOf(fight));
                if (fight == null) throw new IllegalStateException("No actual client fight");
                List<Map<String,Object>> fighters = new ArrayList<>();
                for (Object actor : (Collection<?>) call(fight, "dLy")) {
                    Map<String,Object> row = new LinkedHashMap<>();
                    row.put("id", call(actor, "Sn"));
                    row.put("class", actor.getClass().getName());
                    for (String getter : new String[]{"dTE", "dsA", "dTB", "aXA", "Xi"}) {
                        try { row.put(getter, call(actor, getter)); }
                        catch (Throwable error) { row.put(getter + "_error", error.toString()); }
                    }
                    Object controller = call(actor, "dpr");
                    row.put("controller", controller == null ? null : call(controller, "Sn"));
                    row.put("controller_same_object", controller == actor);
                    Object property = call(Class.forName("ffe"), "Ua", 103);
                    row.put("property_103", call(actor, "i", property));
                    fighters.add(row);
                }
                result.put("fighters", fighters);
            } catch (Throwable error) { result.put("error", error.toString()); }
        });
        Files.writeString(Path.of(output), new Gson().toJson(result));
    }
}
