import java.nio.file.*;
import java.util.*;
import com.google.gson.GsonBuilder;

/** Offline export of all native aLO item criteria and template binding. */
public class ExportAllItemExchangeMetadata {
  public static void main(String[] args) throws Exception {
    apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
    Map<String,Object> items = new TreeMap<>();
    int[] counts = new int[3];
    apw.bGL().a(new aLO(), new apB<aLO>() {
      public void load(aLO raw) {
        counts[0]++;
        try {
          bJp item = new bIJ().f(raw);
          Map<String,Object> row = new LinkedHashMap<>();
          row.put("reference", raw.d());
          Map<String,String> criteria = new TreeMap<>();
          String[] pairs = raw.cpz();
          if (pairs != null) {
            if ((pairs.length & 1) != 0) throw new IllegalStateException("odd criterion pair count");
            for (int i=0; i<pairs.length; i+=2) criteria.put(fnE.valueOf(pairs[i]).name(), pairs[i+1]);
          }
          row.put("raw_criteria", criteria);
          List<String> compiled = new ArrayList<>();
          Iterator<Map.Entry<fnE,amb>> it = item.gjd();
          while (it.hasNext()) {
            Map.Entry<fnE,amb> entry = it.next();
            compiled.add(entry.getKey().name());
            if (entry.getKey() == fnE.sGH) {
              row.put("native_exchange_result_null_context", entry.getValue().b(null, null, null, null));
            }
          }
          Collections.sort(compiled);
          row.put("compiled_criteria_actions", compiled);
          foS binding = item.gfM();
          foN initial = foP.b(binding);
          Map<String,Object> bind = new LinkedHashMap<>();
          bind.put("enum", binding.name());
          bind.put("id", binding.aKg());
          bind.put("native_gik", binding.gik());
          bind.put("native_bKs", binding.bKs());
          bind.put("default_eKo", initial.eKo());
          row.put("binding_template", bind);
          items.put(Integer.toString(raw.d()), row);
          counts[1]++;
        } catch (Throwable e) {
          counts[2]++;
          items.put(Integer.toString(raw.d()), Map.of("reference", raw.d(), "export_error", e.getClass().getName()+": "+String.valueOf(e.getMessage())));
        }
      }
    });
    Map<String,Object> result = new LinkedHashMap<>();
    result.put("source", "Installed aLO.cpz raw criteria + bIJ.f(aLO) compiled fnE map + fpC.gfM + foP.b(binding).eKo");
    result.put("raw_records", counts[0]);
    result.put("loaded_records", counts[1]);
    result.put("errors", counts[2]);
    result.put("items", items);
    Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
    System.out.println("raw="+counts[0]+" loaded="+counts[1]+" errors="+counts[2]+" refs="+items.size());
  }
}
