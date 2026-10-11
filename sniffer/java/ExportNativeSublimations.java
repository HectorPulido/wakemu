import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

/** Export exact bdata item sublimation patterns used by fpK.a(fpI, fpP). */
public final class ExportNativeSublimations {
  private static String quote(String value) {
    return "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"")
        .replace("\n", "\\n").replace("\r", "\\r") + "\"";
  }

  public static void main(String[] args) throws Exception {
    Path root = Path.of("").toAbsolutePath();
    apw.bGL().dd("jar:file:" + root.resolve("client/contents/bdata") + "/%d.jar!/%d.bin");
    List<String> rows = new ArrayList<>();
    List<String> errors = new ArrayList<>();
    apw.bGL().a(new aLO(), new apB<aLO>() {
      @Override public void load(aLO raw) {
        try {
          bJp item = new bIJ().f(raw);
          fpP pattern = item.dHt();
          if (pattern == null || pattern.gkb() == null
              || (pattern.gkb().length == 0 && pattern.dHw() == fpR.sRD)) return;
          List<Integer> colors = new ArrayList<>();
          for (QE color : pattern.gkb()) colors.add((int) color.aKg());
          rows.add("{\"reference\":" + item.d()
              + ",\"item_level\":" + item.cmZ() + ",\"type\":" + quote(pattern.dHw().name())
              + ",\"slot_colors\":" + colors + "}");
        } catch (Throwable failure) {
          errors.add(raw.d() + ":" + failure.getClass().getSimpleName());
        }
      }
    });
    rows.sort(Comparator.comparingInt(row -> Integer.parseInt(row.substring(row.indexOf(':') + 1,
        row.indexOf(',', row.indexOf(':'))))));
    String json = "{\"source\":{\"client_jar\":\"client/lib/wakfu-client.jar\","
        + "\"client_jar_sha256\":\"e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd\","
        + "\"binary_table\":\"aLO.cpY -> aLS.cqj/cqk/cql\","
        + "\"mechanism\":\"bGT.i(aLO) -> fpP(slotColors,type); fpK.a(fpI,fpP) compatibility\","
        + "\"colors\":{\"NONE\":0,\"RED\":1,\"GREEN\":2,\"BLUE\":3,\"WHITE\":4},"
        + "\"compatibility\":\"BASIC: fpK.a(fpI,fpP) ordered contiguous colors, white item slots/NONE pattern entries wildcard; EPIC/RELIC: empty colors, fpR.ax(fnR) exact rarity predicate, independent special slot\"},"
        + "\"count\":" + rows.size() + ",\"items\":[" + String.join(",", rows)
        + "],\"export_errors\":[" + String.join(",", errors.stream().map(ExportNativeSublimations::quote).toList()) + "]}";
    Path output = args.length > 0 ? Path.of(args[0]) : root.resolve("server/protocol/item-sublimations.json");
    Files.createDirectories(output.toAbsolutePath().getParent());
    Files.writeString(output, json + "\n");
    System.out.println("Exported native sublimation patterns: " + rows.size() + ", errors=" + errors.size());
  }
}
