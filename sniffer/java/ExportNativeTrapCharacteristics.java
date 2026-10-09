import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Native fbc eRF allocation/reset and PA.nG bounds; no catalog loading. */
public final class ExportNativeTrapCharacteristics {
    public static void main(String[] args) throws Exception {
        Constructor<bcY> constructor = bcY.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        bcY trap = constructor.newInstance();
        trap.aQc();
        Map<String,Object> characteristics = new TreeMap<>();
        Map<String,Integer> fields = new TreeMap<>();
        for (String name : new String[]{"sgP", "sgQ", "sgR", "sgS", "sgT", "sgU", "shV", "shW", "shX", "shY"}) {
            ffw pc = (ffw) ffw.class.getField(name).get(null);
            int id = pc.aKg() & 255;
            fields.put(name, id);
            if (!trap.a(pc)) throw new AssertionError(name);
            PA value = trap.b(pc);
            Map<String,Object> row = new TreeMap<>();
            row.put("name", pc.name());
            row.put("current", value.aYS());
            row.put("minimum", value.aYW());
            row.put("maximum", value.aYU());
            row.put("hard_minimum", pc.aZo());
            row.put("hard_maximum", pc.aZp());
            List<Map<String,Integer>> observations = new ArrayList<>();
            for (int requested : new int[]{Integer.MIN_VALUE, -5001, -1, 0, 1, 50001, Integer.MAX_VALUE}) {
                value.aYY();
                int returned = value.nG(requested);
                observations.add(Map.of("requested", requested, "returned", returned, "current", value.aYS()));
            }
            row.put("setter_observations", observations);
            characteristics.put(Integer.toString(id), row);
        }
        if (trap.a(ffw.sgC)) throw new AssertionError("Trap invented HP");
        Map<String,Object> out = new TreeMap<>();
        out.put("source", "fbc.rMB/eRF/eRC.f; actual bcY fresh aQc; native PA.nG");
        out.put("fields", fields);
        out.put("characteristics", characteristics);
        out.put("copy_all_property", (fbo.rNy.aKg() & 255));
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(out));
        System.out.println("Actual fbc PCs=" + characteristics.size() + ", setters=" + characteristics.size()*7);
    }
}
