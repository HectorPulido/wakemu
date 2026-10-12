import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.Set;
import java.util.TreeMap;

/** Exact aNr.cvc -> eQe.tz presence, independently of ownership and costs. */
public final class ExportNativeSpellVisibility {
    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (char ch : value.toCharArray()) {
            if (ch == '"' || ch == '\\') out.append('\\').append(ch);
            else if (ch < 32) out.append(String.format("\\u%04x", (int) ch));
            else out.append(ch);
        }
        return out.append('"').toString();
    }

    public static void main(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("--source-id")) {
            System.out.println(new aNr().bGI());
            return;
        }
        if (args.length != 2) throw new IllegalArgumentException("refs-file bdata-directory");
        Set<Integer> wanted = new HashSet<>();
        for (String line : Files.readAllLines(Path.of(args[0]))) {
            if (!line.isBlank() && !wanted.add(Integer.valueOf(line.strip())))
                throw new IllegalArgumentException("Duplicate spell reference");
        }
        TreeMap<Integer, String> rows = new TreeMap<>();
        apw.bGL().dd("jar:file:" + Path.of(args[1]).toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aNr(), new apB<aNr>() {
            public void load(aNr row) {
                int ref = row.d();
                if (!wanted.contains(ref)) return;
                String raw = row.cvc();
                // bPS uses this exact parser and assigns the resulting amb to fyT.l.
                // Reject parser errors instead of promoting absent/unknown metadata.
                amb criterion = eQe.tz(raw);
                String value = "{\"reference\":" + ref
                    + ",\"visibility_criterion_raw\":" + (raw == null ? "null" : quote(raw))
                    + ",\"native_criterion_present\":" + (criterion != null)
                    + ",\"native_parser\":\"eQe.tz\",\"native_consumer\":\"bPv.f.bPK.gtS\"}";
                if (rows.put(ref, value) != null)
                    throw new IllegalArgumentException("Duplicate native spell record");
            }
        });
        if (!rows.keySet().equals(wanted)) throw new IllegalStateException("Missing native spell references");
        for (String row : rows.values()) System.out.println(row);
    }
}
