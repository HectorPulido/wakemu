import java.nio.file.*;
import java.io.*;
import java.util.*;
import java.util.regex.*;
import java.util.zip.GZIPInputStream;
import com.google.gson.*;
/** Native objective coordinates with explicitly inferential localized NPC names. */
public class AuditNpcQuestTargetAnchors {
    public static void main(String[] args) throws Exception {
        JsonObject quests = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        JsonObject dialogues;
        try (Reader reader = new InputStreamReader(new GZIPInputStream(Files.newInputStream(Path.of(args[1]))), java.nio.charset.StandardCharsets.UTF_8)) {
            dialogues = JsonParser.parseReader(reader).getAsJsonObject();
        }
        JsonObject names = dialogues.getAsJsonObject("translations").getAsJsonObject("es");
        JsonObject texts = quests.getAsJsonObject("translations").getAsJsonObject("es");
        Map<String,List<Integer>> breeds = new TreeMap<>();
        for (JsonElement value : dialogues.getAsJsonArray("speakers")) {
            int ref = value.getAsJsonObject().get("ref").getAsInt();
            JsonElement name = names.get("content.7." + ref);
            if (name != null && name.getAsString().length() > 3) breeds.computeIfAbsent(name.getAsString(), key -> new ArrayList<>()).add(ref);
        }
        List<Object> result = new ArrayList<>();
        Pattern verb = Pattern.compile("^(?:Volver a hablar con |Hablar con |Habla con )");
        for (JsonElement value : quests.getAsJsonArray("definitions")) {
            JsonObject quest = value.getAsJsonObject();
            for (JsonElement objectiveValue : quest.getAsJsonArray("cjJ")) {
                JsonObject objective = objectiveValue.getAsJsonObject();
                JsonElement localized = texts.get("content.64." + objective.get("d").getAsInt());
                if (localized == null || objective.getAsJsonArray("ckd").isEmpty()) continue;
                String text = localized.getAsString();
                Matcher prefix = verb.matcher(text);
                if (!prefix.find()) continue;
                String subject = text.substring(prefix.end()).replaceFirst("^(?:el |la |los |las )", "");
                for (var entry : breeds.entrySet()) {
                    if (!Pattern.compile("^" + Pattern.quote(entry.getKey()) + "(?!\\w)", Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE).matcher(subject).find()) continue;
                    List<Integer> roots = new ArrayList<>();
                    for (JsonElement nodeValue : dialogues.getAsJsonArray("nodes")) {
                        JsonObject node = nodeValue.getAsJsonObject();
                        if (!node.get("criteria").getAsString().isEmpty()) continue;
                        for (int ref : entry.getValue()) {
                            if (node.get("native_cmT").getAsString().equals("npc" + ref)) roots.add(node.get("id").getAsInt());
                        }
                    }
                    for (JsonElement markerValue : objective.getAsJsonArray("ckd")) {
                        JsonObject marker = markerValue.getAsJsonObject();
                        Map<String,Object> row = new LinkedHashMap<>();
                        row.put("quest_id", quest.get("d").getAsInt());
                        row.put("objective_id", objective.get("d").getAsInt());
                        row.put("objective_text_es", text);
                        row.put("name", entry.getKey());
                        row.put("candidate_references", entry.getValue());
                        row.put("unique_speaker_name", entry.getValue().size() == 1);
                        row.put("candidate_unconditional_portrait_roots", roots);
                        row.put("map_id", marker.get("ckj").getAsLong());
                        row.put("x", marker.get("ckg").getAsInt());
                        row.put("y", marker.get("ckh").getAsInt());
                        row.put("z", marker.get("cki").getAsInt());
                        row.put("classification", "Native quest target XYZ/map; localized subject-name inference for breed. Not certified exact actor spawn or initial root.");
                        result.add(row);
                    }
                }
            }
        }
        Files.writeString(Path.of(args[2]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("named_native_target_records=" + result.size());
    }
}
