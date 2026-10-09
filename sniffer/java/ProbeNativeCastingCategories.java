import java.lang.reflect.Field;
import java.util.LinkedHashMap;
import java.util.Map;
import com.google.gson.Gson;

/** Exact enum identities used by fcO range/LOS overrides; no catalogs. */
public class ProbeNativeCastingCategories {
    public static Map<String, Object> metadata() throws Exception {
        Field id = fyU.class.getDeclaredField("tye");
        id.setAccessible(true);
        Map<String, Integer> categories = new LinkedHashMap<>();
        for (String name : new String[]{"txX", "txZ", "tya", "tyb"})
            categories.put(name, id.getInt(fyU.class.getField(name).get(null)));
        Map<String, Integer> areas = new LinkedHashMap<>();
        for (String name : new String[]{"rNX", "rNI"})
            areas.put(name, ((fbp) fbp.class.getField(name).get(null)).aIc());
        return Map.of("categories", categories, "area_types", areas);
    }
    public static void main(String[] args) throws Exception {
        System.out.println(new Gson().toJson(metadata()));
    }
}
