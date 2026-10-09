import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import com.google.gson.Gson;

/** Class spell root fKX collision geometry, distinct from aZP effect area. */
public class ExportNativeCastingRoots {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
                     + "/%d.jar!/%d.bin");
        Map<String, Object> roots = new TreeMap<>();
        for (String text : Files.readAllLines(Path.of(args[0]))) {
            int reference = Integer.parseInt(text);
            eVn effect = bcA.dcX().AH(reference);
            if (effect == null) throw new IllegalStateException("Missing native root " + reference);
            Map<String, Object> row = new LinkedHashMap<>();
            anc collision = effect.fKX();
            Object area = null;
            if (collision != null) {
                Map<String, Object> shape = new LinkedHashMap<>();
                shape.put("area_class", collision.getClass().getName());
                shape.put("area_native", collision.bEm());
                if (collision instanceof anE || collision instanceof anJ) {
                    List<List<Integer>> points = new ArrayList<>();
                    for (int[] point : collision.bEl())
                        points.add(List.of(point[0], point[1]));
                    shape.put("native_area_points", points);
                }
                area = shape;
            }
            row.put("native_casting_collision_area", area);
            amS selector = effect.aZF();
            row.put("native_selector_present", selector != null);
            Object selectorData = null;
            if (selector != null) {
                Map<String, Object> selected = new LinkedHashMap<>();
                selected.put("class", selector.getClass().getName());
                if (selector instanceof fcE) {
                    var field = fcE.class.getDeclaredField("rXt");
                    field.setAccessible(true);
                    selected.put("mask", field.getLong(selector));
                }
                selectorData = selected;
            }
            row.put("native_target_selector", selectorData);
            roots.put(text, row);
        }
        Map<String, Object> document = new LinkedHashMap<>();
        document.put("schema", "native-class-casting-roots-v1");
        document.put("source", "Original class spell roots eVn.fKX/aZF, independent aZP");
        Map<String, Integer> properties = new LinkedHashMap<>();
        for (String name : List.of("sdG", "sdR", "sdO", "sdD", "sdC", "sex")) {
            ffe property = (ffe) ffe.class.getField(name).get(null);
            properties.put(name, property.aKg() & 255);
        }
        document.put("fight_properties", properties);
        document.put("normal_casting_overrides", ProbeNativeCastingCategories.metadata());
        document.put("roots", roots);
        Files.writeString(Path.of(args[1]), new Gson().newBuilder().serializeNulls().create().toJson(document));
        System.out.println("Exported native casting metadata for " + roots.size() + " class roots");
    }
}
