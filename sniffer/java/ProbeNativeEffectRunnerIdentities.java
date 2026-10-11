import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.LinkedHashSet;
import java.util.Set;

/** Resolve requested native effect IDs through actual installed registry objects. */
public final class ProbeNativeEffectRunnerIdentities {
    public static void main(String[] args) throws Exception {
        Set<Integer> requested = new LinkedHashSet<>();
        for (String arg : args) {
            int identity = Integer.parseInt(arg);
            if (identity <= 0 || !requested.add(identity))
                throw new IllegalArgumentException("Invalid or duplicate effect identity");
        }
        if (requested.isEmpty()) throw new IllegalArgumentException("Effect identities required");
        Set<Integer> found = new LinkedHashSet<>();
        for (Field field : eVi.class.getDeclaredFields()) {
            if (!Modifier.isStatic(field.getModifiers()) || field.getType() != eVj.class) continue;
            field.setAccessible(true);
            eVj entry = (eVj) field.get(null);
            if (entry == null || !requested.contains(entry.d())) continue;
            if (!found.add(entry.d())) throw new IllegalStateException("Duplicate native effect identity");
            Object runner = entry.bkv();
            if (runner == null) throw new IllegalStateException("Missing native runner");
            Class<?> type = runner.getClass();
            StringBuilder characteristics = new StringBuilder();
            for (Class<?> owner = type; owner != null; owner = owner.getSuperclass()) {
                for (Field operand : owner.getDeclaredFields()) {
                    if (Modifier.isStatic(operand.getModifiers())
                        || !PC.class.isAssignableFrom(operand.getType())) continue;
                    operand.setAccessible(true);
                    Object value = operand.get(runner);
                    if (!(value instanceof ffw)) continue;
                    if (characteristics.length() > 0) characteristics.append(',');
                    characteristics.append("{\"field\":\"").append(owner.getName())
                        .append('.').append(operand.getName()).append("\",\"id\":")
                        .append(((ffw) value).aKg()).append('}');
                }
            }
            System.out.println("{\"effect_class\":" + entry.d()
                + ",\"registry_field\":\"" + field.getName()
                + "\",\"runner\":\"" + type.getName()
                + "\",\"parent\":\"" + type.getSuperclass().getName()
                + "\",\"characteristics\":[" + characteristics + "]}");
        }
        if (!found.equals(requested)) throw new IllegalStateException("Requested native identity absent");
    }
}
