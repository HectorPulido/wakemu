import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Export installed flora definitions and their native per-stage actions. */
public class ExportPlantResources {
  public static void main(String[] args) throws Exception {
    Path bdata = Path.of("client/contents/bdata").toAbsolutePath();
    Path output = args.length == 0
        ? Path.of("server/protocol/plant-resources.json")
        : Path.of(args[0]);
    apw.bGL().dd("jar:file:" + bdata + "/%d.jar!/%d.bin");

    List<Object> rows = new ArrayList<>();
    int[] totals = new int[2];
    apw.bGL().a(new aNl(), new apB<aNl>() {
      @Override
      public void load(aNl resource) {
        Map<String, Object> row = new LinkedHashMap<>();
        List<Integer> stages = new ArrayList<>();
        List<Object> stageDefinitions = new ArrayList<>();

        for (aNm stage : resource.cvw()) {
          int stageId = stage.wp();
          stages.add(stageId);
          Map<String, Object> stageDefinition = new LinkedHashMap<>();
          stageDefinition.put("stage_id", stageId);

          List<Object> actions = new ArrayList<>();
          for (aNn raw : stage.cvz()) {
            Map<String, Object> action = new LinkedHashMap<>();
            action.put("action_id", raw.d());
            action.put("profession_id", raw.ckL());
            action.put("minimum_level", raw.csM());
            action.put("duration_ms", raw.getDuration());
            action.put("item_reference", raw.csP());
            action.put("product_references", raw.cvJ());
            action.put("criteria", raw.clT());

            // These values are preserved from the native definition, but their
            // gameplay meaning has not been verified and must not be guessed.
            Map<String, Object> rawGetters = new LinkedHashMap<>();
            rawGetters.put("cvF", raw.cvF());
            rawGetters.put("cvG", raw.cvG());
            rawGetters.put("csN", raw.csN());
            rawGetters.put("cvK", raw.cvK());
            rawGetters.put("cvI", raw.cvI());
            rawGetters.put("cvH", raw.cvH());
            rawGetters.put("bwX", raw.bwX());
            rawGetters.put("csR", raw.csR());
            rawGetters.put("cmI", raw.cmI());
            action.put("raw_getters", rawGetters);
            actions.add(action);
          }
          totals[1] += actions.size();
          stageDefinition.put("actions", actions);
          stageDefinitions.add(stageDefinition);
        }

        row.put("stages", stages);
        row.put("resource_reference", resource.d());
        row.put("monster_resource", resource.cvt());
        row.put("monster_family_ids", resource.cvv());
        row.put("family_id", resource.aeV());
        row.put("kind", resource.cvn());
        row.put("parameter_cvx", resource.cvx());
        row.put("parameter_cvu", resource.cvu());
        row.put("cvo", resource.cvo());
        row.put("cvp", resource.cvp());
        row.put("parameter_aLj", resource.aLj());
        row.put("stage_definitions", stageDefinitions);
        rows.add(row);
        totals[0]++;
      }
    });

    Files.writeString(
        output,
        new GsonBuilder().setPrettyPrinting().create().toJson(rows) + "\n");
    System.out.printf(
        "Wrote %d resource definitions, %d stages, %d actions to %s%n",
        totals[0],
        rows.stream().mapToInt(row -> ((List<?>) ((Map<?, ?>) row).get("stages")).size()).sum(),
        totals[1],
        output);
  }
}
