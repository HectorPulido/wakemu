import java.nio.file.*;
import java.util.*;
import com.google.gson.*;

/** Export installed stele definitions without inventing server-side mechanics. */
public class ExportSteleDefinitions {
    static List<Object> costs(aNz[] rows) {
        List<Object> result = new ArrayList<>();
        for (aNz r : rows) result.add(Map.of("item_reference", r.cyC(), "quantity", r.cyD(), "kamas", r.cyE()));
        return result;
    }
    static List<Object> rewards(aNA[] rows) {
        List<Object> result = new ArrayList<>();
        for (aNA r : rows) result.add(Map.of("id", r.d(), "item_reference", r.aAi(), "quantity", r.coe(), "flag", r.cyF(), "order", r.cyG()));
        return result;
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Object> result = new ArrayList<>();
        apw.bGL().a(new aNx(), new apB<aNx>() {
            public void load(aNx r) {
                List<Object> levels = new ArrayList<>(), options = new ArrayList<>();
                for (aNy n : r.cyz()) levels.add(Map.of("id", n.d(), "weight", n.aYD(), "state_id", n.LR()));
                for (aNB n : r.cyB()) options.add(Map.of("id", n.d(), "required_weight", n.cyH(), "free_rewards_count", n.cyI(), "dynamic_rewards_count", n.cyJ(), "static_rewards", rewards(n.cyK()), "dynamic_rewards", rewards(n.cyL())));
                result.add(Map.of("id", r.d(), "interaction_category", r.clx(), "randomized_rewards", r.cyv(), "criteria", r.cyw(), "activation_cost", costs(r.cyx()), "option_cost", costs(r.cyy()), "difficulties", levels, "base_rewards", rewards(r.cyA()), "tiers", options));
            }
        });
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Exported installed stele definitions: " + result.size());
    }
}
