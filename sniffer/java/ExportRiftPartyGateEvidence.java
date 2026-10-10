import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Offline rift destination criteria; no live game or database interaction. */
public class ExportRiftPartyGateEvidence {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Set<Integer> destinations = new TreeSet<>();
        apw.bGL().a(new aLF(), new apB<aLF>() {
            public void load(aLF wave) { if (Set.of(3,4,5,6,7,8,19,20,25,37).contains(wave.d())) destinations.add(wave.cpc()); }
        });
        List<Map<String,Object>> rows = new ArrayList<>();
        apw.bGL().a(new aNE(), new apB<aNE>() {
            public void load(aNE value) {
                if (!destinations.contains(value.cpc())) return;
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("destination_id",value.cpc());
                List<Map<String,Object>> gates = new ArrayList<>();
                for (aNF gate : value.cyT()) {
                    if (!gate.clT().isEmpty()) throw new AssertionError("Unexpected native rift destination criterion: " + gate.clT());
                    Map<String,Object> g = new LinkedHashMap<>();
                    g.put("id",gate.cyU());g.put("map_id",gate.cpb());g.put("criterion",gate.clT());
                    g.put("raw_bBK",gate.bBK());g.put("raw_cyV",gate.cyV());
                    g.put("raw_cod",gate.cod());g.put("raw_cyW",gate.cyW());
                    g.put("raw_cyX",gate.cyX());g.put("raw_cvd",gate.cvd());
                    g.put("raw_cyY",gate.cyY());g.put("raw_cyZ",gate.cyZ());
                    gates.add(g);
                }
                row.put("gates",gates);rows.add(row);
            }
        });
        if (rows.size()!=10) throw new AssertionError("Missing exact native rift destination gates");
        Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(rows));
        System.out.println("Exported native criteria for all ten public rift destinations");
    }
}
