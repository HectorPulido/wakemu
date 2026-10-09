import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Native passive definitions distributed to every class by bPS.c(aNr). */
public class ExportCommonPassiveDefinitions {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
            + "/%d.jar!/%d.bin");
        List<Map<String, Object>> rows = new ArrayList<>();
        apw.bGL().a(new aNr(), new apB<aNr>() {
            public void load(aNr spell) {
                if (spell.aXA() == eGE.pIp.aXA() && spell.cwv() == 2) {
                    rows.add(Map.of("id", spell.d(), "breed", (int) spell.aXA(),
                        "unlock_level", (int) spell.cwe(), "kind", "passive",
                        "ui_order", (int) spell.cwt()));
                }
            }
        });
        rows.sort(Comparator.comparingInt(row -> (int) row.get("id")));
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting()
            .create().toJson(Map.of("source", "aNr.aXA()==eGE.pIp.aXA(); bPS.c native universal passive distribution",
                "spells", rows)) + "\n");
        System.out.println("Exported " + rows.size() + " native common passives");
    }
}
