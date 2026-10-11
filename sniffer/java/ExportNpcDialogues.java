import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Read-only native dialogue node export; choice transitions are server data. */
public class ExportNpcDialogues {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Object> nodes = new ArrayList<>();
        apw.bGL().a(new aKO(), new apB<aKO>() {
            public void load(aKO row) {
                Map<String, Object> node = new LinkedHashMap<>();
                node.put("id", row.d());
                node.put("native_cmT", row.cmT());
                node.put("native_cmU", row.cmU());
                node.put("criteria", row.clT());
                List<Object> choices = new ArrayList<>();
                for (aKP choice : row.cmV()) {
                    Map<String, Object> item = new LinkedHashMap<>();
                    item.put("id", choice.d());
                    item.put("criteria", choice.aHe());
                    item.put("type", choice.aeV());
                    item.put("native_cmW", choice.cmW());
                    choices.add(item);
                }
                node.put("choices", choices);
                nodes.add(node);
            }
        });
        nodes.sort(Comparator.comparingInt(value -> ((Number)((Map<?, ?>)value).get("id")).intValue()));
        List<Object> speakers = new ArrayList<>();
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb row) {
                List<Object> actions = new ArrayList<>();
                for (aMg action : row.csj()) {
                    if (action.aGJ() == 4) {
                        actions.add(Map.of("id", action.d(), "criteria", action.clT(), "type", 4));
                    }
                }
                if (!actions.isEmpty()) {
                    speakers.add(Map.of("ref", row.d(), "min_level", row.cqN(), "max_level", row.cqO(), "visual_id", row.aHf(), "actions", actions));
                }
            }
        });
        Map<String, Object> result = Map.of("nodes", nodes, "speakers", speakers);
        Files.writeString(Path.of(args[0]), new GsonBuilder().serializeNulls().create().toJson(result));
        System.out.println("dialogue_nodes=" + nodes.size());
    }
}
