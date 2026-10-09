import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;

/** Exact bPO.hasCriticalEffect for scoped summon ability levels 0..Fq. */
public class ExportNativeClassSummonCriticalAvailability {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() { public void load(aKX record) {} });
        Map<String, Object> records = new TreeMap<>();
        int checks = 0;
        for (String text : Files.readAllLines(Path.of(args[0]))) {
            int reference = Integer.parseInt(text);
            bPK definition = bPS.elL().IP(reference);
            if (definition == null || definition.Fq() < 0) throw new IllegalStateException(text);
            List<Integer> critical = new ArrayList<>();
            for (int level = 0; level <= definition.Fq(); level++) {
                boolean expected = false;
                Iterator<eVn> roots = definition.fG((short) level);
                while (roots.hasNext()) if (roots.next().dd(1L)) { expected = true; break; }
                bPO action = new bPO(definition, (short) level, reference, null);
                boolean actual = (Boolean) action.eH("hasCriticalEffect");
                if (actual != expected) throw new AssertionError(text + ":" + level);
                if (actual) critical.add(level);
                checks++;
            }
            records.put(text, Map.of("maximum_level", definition.Fq(), "critical_levels", critical,
                "evaluated_minimum_level", 0, "evaluated_maximum_level", definition.Fq()));
        }
        Files.writeString(Path.of(args[1]), new Gson().toJson(Map.of(
            "source", "Scoped original bPO.hasCriticalEffect, explicit every level 0..native Fq",
            "native_checks", checks, "spells", records)) + "\n");
        System.out.println("PASS scoped native critical checks=" + checks + " spells=" + records.size());
    }
}
