import com.google.gson.GsonBuilder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Exports native mount food flags and values without assigning policy. */
public final class ExportMountFoodSemantics {
  private static byte[] sha256(byte[] value) throws Exception {
    return MessageDigest.getInstance("SHA-256").digest(value);
  }

  private static String hex(byte[] value) {
    return java.util.HexFormat.of().formatHex(value);
  }

  private static String bdataHash(Path directory) throws Exception {
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    try (var files = Files.walk(directory)) {
      for (Path file : files.filter(Files::isRegularFile).sorted().toList()) {
        digest.update(directory.relativize(file).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        digest.update((byte) 0);
        digest.update(sha256(Files.readAllBytes(file)));
        digest.update((byte) '\n');
      }
    }
    return hex(digest.digest());
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 1) throw new IllegalArgumentException("output path required");
    Path jar = Path.of("client/lib/wakfu-client.jar");
    Path bdata = Path.of("client/contents/bdata");
    apw.bGL().dd("jar:file:" + bdata.toAbsolutePath() + "/%d.jar!/%d.bin");
    List<Map<String, Object>> models = new ArrayList<>();
    List<Map<String, Object>> errors = new ArrayList<>();
    apw.bGL().a(new aMo(), new apB<aMo>() {
      @Override public void load(aMo raw) {
        try {
          fwn model = bbp.a(raw);
          Map<String, Object> row = new LinkedHashMap<>();
          row.put("reference", raw.AK());
          row.put("model_id", model.d());
          row.put("meal_item_refs", model.gqr());
          List<Map<String, Object>> heals = new ArrayList<>();
          if (raw.ctc() != null) for (aMp item : raw.ctc()) {
            heals.add(Map.of("reference", item.aAi(), "health_per_item", item.getValue()));
          }
          List<Map<String, Object>> xpFlags = new ArrayList<>();
          if (raw.ctd() != null) for (aMr item : raw.ctd()) {
            xpFlags.add(Map.of("reference", item.aAi(), "enabled", item.isVisible()));
          }
          row.put("healing_food_values", heals);
          row.put("xp_food_flags", xpFlags);
          row.put("xp_food_refs", xpFlags.stream()
              .filter(flag -> Boolean.TRUE.equals(flag.get("enabled")))
              .map(flag -> flag.get("reference")).toList());
          models.add(row);
        } catch (Throwable error) {
          errors.add(Map.of("model_id", raw.d(), "error", error.getClass().getName()));
        }
      }
    });
    Map<String, Object> source = new LinkedHashMap<>();
    source.put("client_jar", jar.toString());
    source.put("client_jar_sha256", hex(sha256(Files.readAllBytes(jar))));
    source.put("bdata_directory", bdata.toString());
    source.put("bdata_aggregate_sha256", bdataHash(bdata));
    source.put("loader", "aMo -> bbp.a(aMo) -> fwn; aMp -> YH/YJ; aMr -> YI");
    source.put("healing_fields", "aMo.ctc/aMp.aAi+getValue -> fwn.gz -> fwr.YH/YJ");
    source.put("xp_fields", "aMo.ctd/aMr.aAi+isVisible -> fwn.ai -> fwr.YI");
    Map<String, Object> result = new LinkedHashMap<>();
    result.put("source", source);
    result.put("record_count", models.size());
    result.put("error_count", errors.size());
    result.put("errors", errors);
    result.put("models", models);
    Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result) + "\n");
    System.out.println("records=" + models.size() + " errors=" + errors.size());
  }
}
