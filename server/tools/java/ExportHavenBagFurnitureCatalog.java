import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Export native furniture mappings using the same item action parser as bIJ. */
public class ExportHavenBagFurnitureCatalog {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Map<Short, String> types = new TreeMap<>();
        for (bEE type : bEE.values()) {
            try {
                bEG object = type.bej().bau();
                if (object instanceof bFp) types.put(type.bei(), type.name());
            } catch (Throwable error) {
                System.err.println("Skipped nonportable type " + type.name());
            }
        }
        Map<Integer, Map<String, Object>> templates = new TreeMap<>();
        apw.bGL().a(new aLM(), new apB<aLM>() {
            public void load(aLM row) {
                if (!types.containsKey(row.cpn())) return;
                Map<String, Object> out = new LinkedHashMap<>();
                out.put("template_id", row.d());
                out.put("type_id", row.cpn());
                out.put("kind", types.get(row.cpn()));
                out.put("parameters", row.cps());
                out.put("interaction_mask", row.bem());
                out.put("blocking", row.cpp());
                List<int[]> footprint = new ArrayList<>();
                for (aLN cell : row.cpt()) footprint.add(new int[]{cell.getX(), cell.getY(), cell.bdn()});
                out.put("relative_cells", footprint);
                List<List<int[]>> interactionCells = new ArrayList<>();
                for (int direction = 0; direction < 8; direction++) {
                    List<int[]> cells = new ArrayList<>();
                    for (QV flag : QV.aa(row.bem())) {
                        if (flag == QV.bkv) cells.add(new int[]{0, 0, 0});
                        else {
                            aAS facing = aAS.wL((direction + flag.beg()) % 8);
                            cells.add(new int[]{facing.dyJ, facing.dyK, 0});
                        }
                    }
                    interactionCells.add(cells);
                }
                out.put("interaction_cells_by_direction", interactionCells);
                if (row.cpn() == 33) {
                    try { out.put("craft_definition_id", Integer.parseInt(row.cps())); }
                    catch (NumberFormatException error) { throw new IllegalArgumentException("Invalid native craft definition " + row.d(), error); }
                }
                templates.put(row.d(), out);
            }
        });
        Map<Integer, Long> mappings = new TreeMap<>();
        Map<Integer, Integer> sourceItems = new TreeMap<>();
        apw.bGL().a(new aLO(), new apB<aLO>() {
            public void load(aLO row) {
                for (aLQ action : row.cpW()) {
                    bHu parsed = bHM.a(action.awM(), foI.Wf(action.cnZ()));
                    if (!(parsed instanceof bIx)) continue;
                    parsed.w(action.coa());
                    for (Map.Entry<Integer, Long> entry : ((bIx) parsed).dYY().entrySet()) {
                        Long previous = mappings.put(entry.getKey(), entry.getValue());
                        if (previous != null && !previous.equals(entry.getValue())) throw new IllegalStateException("Ambiguous native mapping " + entry.getKey());
                        sourceItems.put(entry.getKey(), row.d());
                    }
                }
            }
        });
        List<Map<String, Object>> items = new ArrayList<>();
        for (Map.Entry<Integer, Long> entry : mappings.entrySet()) {
            Map<String, Object> template = templates.get(entry.getValue().intValue());
            if (template == null) continue;
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("item_ref", entry.getKey());
            out.put("template_id", entry.getValue());
            out.put("source_item_ref", sourceItems.get(entry.getKey()));
            items.add(out);
        }
        Map<String, Object> document = new LinkedHashMap<>();
        document.put("schema_version", 1);
        document.put("source", "Native aLM templates and aLO bIx actions; bIJ/fla item-reference mapping");
        document.put("templates", templates.values());
        document.put("items", items);
        Files.writeString(Path.of(args[0]), new GsonBuilder().create().toJson(document) + "\n");
        System.out.println("Exported " + templates.size() + " templates and " + items.size() + " portable item mappings");
    }
}
