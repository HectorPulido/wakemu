import gnu.trove.impl.PrimeFinder;
import gnu.trove.map.hash.TLongObjectHashMap;
import java.lang.reflect.Field;
import java.nio.file.Path;
import java.nio.file.Files;
import java.security.MessageDigest;
import java.util.*;

/** Export native default constructor properties and deterministic operation oracle. */
public final class ExportNativeTroveLongMap {
    private static String json(Object value) {
        if (value instanceof String) return "\"" + value + "\"";
        if (value instanceof Number) return value.toString();
        if (value instanceof int[]) {
            List<Integer> list = new ArrayList<>();
            for (int item : (int[]) value) list.add(item);
            return json(list);
        }
        List<String> pieces = new ArrayList<>();
        if (value instanceof Map) {
            for (Object key : ((Map<?,?>) value).keySet())
                pieces.add(json(key) + ":" + json(((Map<?,?>) value).get(key)));
            return "{" + String.join(",", pieces) + "}";
        }
        for (Object item : (Collection<?>) value) pieces.add(json(item));
        return "[" + String.join(",", pieces) + "]";
    }
    private static Object field(Object instance, String name) throws Exception {
        Class<?> type = instance.getClass();
        while (type != null) {
            try {
                Field field = type.getDeclaredField(name);
                field.setAccessible(true);
                return field.get(instance);
            } catch (NoSuchFieldException absent) { type = type.getSuperclass(); }
        }
        throw new NoSuchFieldException(name);
    }
    public static void main(String[] args) throws Exception {
        Field primes = PrimeFinder.class.getDeclaredField("primeCapacities");
        primes.setAccessible(true);
        TLongObjectHashMap<Long> map = new TLongObjectHashMap<>();
        Map<String,Object> contract = new LinkedHashMap<>();
        contract.put("source", "Installed default TLongObjectHashMap constructor and PrimeFinder");
        contract.put("client_jar_sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
            .digest(Files.readAllBytes(Path.of("client/lib/wakfu-client.jar")))));
        Path troveJar = Path.of(TLongObjectHashMap.class.getProtectionDomain().getCodeSource().getLocation().toURI());
        contract.put("trove_jar_name", troveJar.getFileName().toString());
        contract.put("trove_jar_sha256", HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
            .digest(Files.readAllBytes(troveJar))));
        contract.put("prime_capacities", primes.get(null));
        contract.put("initial_capacity", map.capacity());
        contract.put("load_factor", field(map, "_loadFactor"));
        contract.put("auto_compaction_factor", field(map, "_autoCompactionFactor"));
        contract.put("initial_compact_removes", field(map, "_autoCompactRemovesRemaining"));
        Files.writeString(Path.of(args[0]), json(contract));
        Random random = new Random(33920261007L);
        List<Map<String,Object>> rows = new ArrayList<>();
        for (int index = 0; index < 1200; index++) {
            long key = index < 80 ? index - 40 : random.nextInt(170) - 85;
            if (index % 41 == 0) key = Long.MIN_VALUE + index;
            String op = index < 80 || random.nextInt(3) != 0 ? "put" : "remove";
            if (op.equals("put")) map.put(key, key); else map.remove(key);
            Map<String,Object> row = new LinkedHashMap<>();
            row.put("operation", op); row.put("key", key);
            row.put("capacity", map.capacity()); row.put("size", map.size());
            row.put("free", field(map, "_free"));
            row.put("compact_removes", field(map, "_autoCompactRemovesRemaining"));
            row.put("order", new ArrayList<>(map.valueCollection()));
            rows.add(row);
        }
        Files.writeString(Path.of(args[1]), json(rows));
        System.out.println("Exported default contract and " + rows.size() + " operation snapshots");
    }
}
