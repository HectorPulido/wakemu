import java.nio.file.*;
import java.lang.reflect.*;
import java.util.*;
import java.util.zip.*;
import com.google.gson.*;
/** Offline exhaustive quest/achievement definitions. Never executes quest actions. */
public class ExportNativeQuestDefinitions {
    static String sha(Path path) throws Exception {
        java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
        try (var source = Files.newInputStream(path)) {
            byte[] buffer = new byte[65536];
            int size;
            while ((size = source.read(buffer)) != -1) digest.update(buffer, 0, size);
        }
        return HexFormat.of().formatHex(digest.digest());
    }
    static Object raw(Object value) throws Exception {
        if (value == null || value instanceof Number || value instanceof Boolean || value instanceof String) return value;
        if (value.getClass().isArray()) {
            List<Object> values = new ArrayList<>();
            for (int i = 0; i < Array.getLength(value); i++) values.add(raw(Array.get(value, i)));
            return values;
        }
        Map<String,Object> result = new TreeMap<>();
        result.put("native_class", value.getClass().getName());
        Method[] methods = value.getClass().getDeclaredMethods();
        Arrays.sort(methods, Comparator.comparing(Method::getName));
        for (Method method : methods) {
            if (Modifier.isPublic(method.getModifiers()) && method.getParameterCount() == 0
                    && method.getReturnType() != Void.TYPE && !method.getName().equals("bGI")) {
                result.put(method.getName(), raw(method.invoke(value)));
            }
        }
        return result;
    }
    static <T extends apu> List<Object> table(T definition) {
        List<Object> result = new ArrayList<>();
        apw.bGL().a(definition, new apB<T>() {
            public void load(T row) {
                try { result.add(raw(row)); }
                catch (Exception error) { throw new RuntimeException(error); }
            }
        });
        return result;
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        Map<String,Object> output = new LinkedHashMap<>();
        output.put("schema_version", 1);
        output.put("source", "Installed native aJM/aJN/aJO/aJP/aJQ/aJR/aJS/aJU; offline apw loader");
        output.put("table_ids", Map.of("definitions", new aJM().bGI(), "categories", new aJR().bGI(), "lists", new aJS().bGI(), "variables", new aJU().bGI()));
        output.put("definitions", table(new aJM()));
        output.put("categories", table(new aJR()));
        output.put("lists", table(new aJS()));
        output.put("variables", table(new aJU()));
        List<Object> rewardTypes = new ArrayList<>();
        for (bdH type : bdH.values()) rewardTypes.add(Map.of("id", type.d(), "name", type.name(), "native_dee", type.dee(), "native_brO", type.brO()));
        output.put("reward_types", rewardTypes);
        Map<String,Object> translations = new LinkedHashMap<>();
        for (String language : List.of("en", "es", "fr", "pt")) {
            Properties all = new Properties();
            try (ZipFile zip = new ZipFile("client/contents/i18n/i18n_" + language + ".jar")) {
                all.load(new java.io.InputStreamReader(zip.getInputStream(zip.getEntry("texts_" + language + ".properties")), java.nio.charset.StandardCharsets.UTF_8));
            }
            Map<String,String> selected = new TreeMap<>();
            for (String key : all.stringPropertyNames()) {
                if (key.startsWith("content.62.") || key.startsWith("content.63.") || key.startsWith("content.64.") || key.startsWith("content.65.")) selected.put(key, all.getProperty(key));
            }
            translations.put(language, selected);
        }
        output.put("translations", translations);
        Map<String,String> hashes = new TreeMap<>();
        hashes.put("client/lib/wakfu-client.jar", sha(Path.of("client/lib/wakfu-client.jar")));
        hashes.put("sniffer/java/ExportNativeQuestDefinitions.java", sha(Path.of("sniffer/java/ExportNativeQuestDefinitions.java")));
        for (int tableId : List.of(new aJM().bGI(), new aJR().bGI(), new aJS().bGI(), new aJU().bGI())) {
            Path archive = Path.of("client/contents/bdata/" + tableId + ".jar");
            hashes.put(archive.toString(), sha(archive));
        }
        for (String language : List.of("en", "es", "fr", "pt")) {
            Path archive = Path.of("client/contents/i18n/i18n_" + language + ".jar");
            hashes.put(archive.toString(), sha(archive));
        }
        output.put("source_sha256", hashes);
        Path destination = Path.of(args[0]);
        Files.writeString(destination, new GsonBuilder().serializeNulls().create().toJson(output));
        System.out.println("definitions=" + ((List<?>)output.get("definitions")).size() + " categories=" + ((List<?>)output.get("categories")).size() + " lists=" + ((List<?>)output.get("lists")).size() + " variables=" + ((List<?>)output.get("variables")).size());
    }
}
