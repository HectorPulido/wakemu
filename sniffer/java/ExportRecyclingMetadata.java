import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import com.google.gson.GsonBuilder;

/** Exports installed native recycling definitions without assigning game rules. */
public final class ExportRecyclingMetadata {
  private ExportRecyclingMetadata() {}

  private static String sha256(Path path) throws Exception {
    MessageDigest digest = MessageDigest.getInstance("SHA-256");
    if (Files.isDirectory(path)) {
      try (var files = Files.walk(path)) {
        for (Path file : files.filter(Files::isRegularFile).sorted().toList()) {
          digest.update(path.relativize(file).toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
          digest.update((byte) 0);
          digest.update(Files.readAllBytes(file));
        }
      }
    } else digest.update(Files.readAllBytes(path));
    return java.util.HexFormat.of().formatHex(digest.digest());
  }

  public static void main(String[] args) throws Exception {
    if (args.length != 1) throw new IllegalArgumentException("output path required");
    apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
    Map<Integer, Object> rows = new TreeMap<>();
    int[] counts = new int[2];
    apw.bGL().a(new aLO(), new apB<aLO>() {
      @Override public void load(aLO raw) {
        counts[0]++;
        try {
          bJp item = new bIJ().f(raw);
          Map<String, Object> row = new LinkedHashMap<>();
          row.put("reference", item.d());
          foh kind = item.gjr();
          row.put("recycling_kind", kind.name());
          row.put("recycling_product_reference", kind.AK());
          row.put("not_recyclable_feature", item.c(foc.sIO));
          row.put("yield_low", item.gjp());
          row.put("yield_high", item.gjq());
          row.put("variable_yield", item.fmq());
          // fnR.ghe() falls back to this template predicate when no identified
          // bonus-slot map is present in the emitted ProtoItem.
          row.put("template_gjv", item.gjv());
          row.put("item_level", item.cmZ());

          List<Integer> slots = new ArrayList<>();
          if (item.dLn() != null) {
            for (fnO slot : fnO.values()) if (item.dLn().v(slot)) slots.add((int) slot.aKg());
          }
          row.put("equipment_slots", slots);
          List<Integer> occupied = new ArrayList<>();
          if (item.dLn() != null && item.dLn().gkp() != null) {
            for (fnO slot : item.dLn().gkp()) occupied.add((int) slot.aKg());
          }
          row.put("equipment_occupied_slots", occupied);

          Map<String, String> rawCriteria = new TreeMap<>();
          String[] pairs = raw.cpz();
          if (pairs != null) for (int i = 0; i + 1 < pairs.length; i += 2) rawCriteria.put(pairs[i], pairs[i + 1]);
          row.put("raw_criteria", rawCriteria);
          List<String> compiledCriteria = new ArrayList<>();
          Iterator<Map.Entry<fnE, amb>> it = item.gjd();
          while (it.hasNext()) compiledCriteria.add(it.next().getKey().name());
          compiledCriteria.sort(String::compareTo);
          row.put("compiled_criteria", compiledCriteria);
          rows.put(item.d(), row);
        } catch (Throwable failure) {
          rows.put(raw.d(), Map.of("reference", raw.d(), "export_error", failure.getClass().getName()));
          counts[1]++;
        }
      }
    });

    Map<String, Object> result = new LinkedHashMap<>();
    result.put("source", "Installed client/lib/wakfu-client.jar: aLO -> bIJ.f -> fpC; recycling kind/product from foh; yields, variable flag, template gjv, level, slots and criteria from fpC/fpY/aLO");
    result.put("client_jar_sha256", sha256(Path.of("client/lib/wakfu-client.jar")));
    result.put("bdata_shards_sha256", sha256(Path.of("client/contents/bdata")));
    result.put("record_count", counts[0]);
    result.put("error_count", counts[1]);
    result.put("items", rows);
    Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result) + "\n");
    System.out.println("rows=" + counts[0] + " errors=" + counts[1]);
  }
}
