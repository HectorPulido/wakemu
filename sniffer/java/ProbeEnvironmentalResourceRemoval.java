import com.ankamagames.framework.graphics.engine.Anm2.Anm;
import com.google.gson.GsonBuilder;
import java.io.InputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.jar.JarFile;

/** Read original resource death clips; never edits assets or boots the game. */
public final class ProbeEnvironmentalResourceRemoval {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) throw new IllegalArgumentException("output-json resource-id...");
        Set<Integer> wanted = new LinkedHashSet<>();
        for (int index = 1; index < args.length; index++) wanted.add(Integer.parseInt(args[index]));
        Map<Integer, Map<String, Object>> definitions = new LinkedHashMap<>();
        Set<Integer> assets = new LinkedHashSet<>();
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aNl(), new apB<aNl>() {
            @Override public void load(aNl definition) {
                if (!wanted.contains(definition.d())) return;
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("resource_reference", definition.d());
                row.put("kind", definition.cvn());
                row.put("native_graphics_variants", definition.cvy());
                row.put("stage_ids", Arrays.stream(definition.cvw()).mapToInt(aNm::wp).toArray());
                List<Map<String, Object>> actions = new ArrayList<>();
                for (aNm stage : definition.cvw()) for (aNn action : stage.cvz())
                    actions.add(Map.of("stage", stage.wp(), "action_id", action.d(), "cvF", action.cvF()));
                row.put("native_stage_actions", actions);
                for (int[] variants : definition.cvy().values())
                    for (int asset : variants) assets.add(asset);
                definitions.put(definition.d(), row);
            }
        });
        Constructor<Anm> constructor = Anm.class.getDeclaredConstructor();
        constructor.setAccessible(true);
        Field assetPath = Anm.class.getDeclaredField("axV");
        assetPath.setAccessible(true);
        Method parse = Anm.class.getDeclaredMethod("dB", byte[].class);
        parse.setAccessible(true);
        List<Map<String, Object>> observations = new ArrayList<>();
        int nativeDeleteEvents = 0;
        try (JarFile jar = new JarFile("client/contents/animations/resources/resources.jar")) {
            for (int asset : assets) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("asset", asset + ".anm");
                var entry = jar.getJarEntry(asset + ".anm");
                if (entry == null) {
                    row.put("status", "missing_original_asset");
                    observations.add(row);
                    continue;
                }
                Anm animation = constructor.newInstance();
                assetPath.set(animation, Integer.toString(asset));
                try (InputStream stream = jar.getInputStream(entry)) {
                    parse.invoke(animation, (Object) stream.readAllBytes());
                }
                row.put("global_events", Arrays.stream(animation.bHd().aJt().aJw()).map(event -> Map.of("type", event.aJS().name(), "class", event.getClass().getName())).toList());
                row.put("clip_headers", Arrays.stream(animation.aJs().aKy()).map(header ->
                    Map.of("name", java.util.Objects.toString(header.getName(), ""), "id", header.aKw(), "index", header.aKt())).toList());
                row.put("timeline_names", animation.bHd().aJu().aJi().stream().map(clip ->
                    Map.of("name", java.util.Objects.toString(clip.getName(), ""), "id", clip.aIX(), "frames", clip.aJc(), "class", clip.getClass().getName())).toList());
                List<Map<String, Object>> clips = new ArrayList<>();
                for (Fy clip : animation.bHd().aJu().aJi()) {
                    String clipName = Arrays.stream(animation.aJs().aKy())
                        .filter(header -> header.aKw() == clip.aIX()).map(header -> java.util.Objects.toString(header.getName(), ""))
                        .findFirst().orElse(java.util.Objects.toString(clip.getName(), ""));
                    // Enumerate all native timelines; death clips can reference nested event timelines.
                    clip.a(animation.bHd().aJt());
                    Map<String, Object> clipRow = new LinkedHashMap<>();
                    clipRow.put("name", clipName);
                    clipRow.put("symbol_count", clip.aJc());
                    clipRow.put("stored_frames", clip.aJh());
                    clipRow.put("timeline_id", clip.aIX());
                    List<Map<String, Object>> events = new ArrayList<>();
                    for (int frame = 0; frame < clip.aJh(); frame++) {
                        ArrayList<EV> values = new ArrayList<>();
                        clip.a(frame, values);
                        if (values == null) continue;
                        for (EV event : values) {
                            Map<String, Object> eventRow = new LinkedHashMap<>();
                            eventRow.put("frame", frame);
                            eventRow.put("native_class", event.getClass().getName());
                            eventRow.put("type", event.aJS().name());
                            eventRow.put("native_type_byte", event.aJS().aKg());
                            if (event.aJS() == Fg.aAw) {
                                nativeDeleteEvents++;
                            }
                            events.add(eventRow);
                        }
                    }
                    clipRow.put("events", events);
                    clips.add(clipRow);
                }
                row.put("native_timelines", clips);
                row.put("status", "original_native_animation_parsed");
                observations.add(row);
            }
        }
        // Native stage packet decoder: x,y,z,stage,owner-account,int metadata.
        cAx packet = new cAx();
        byte[] body = ByteBuffer.allocate(24).putInt(10).putInt(11).putShort((short) 0)
            .putShort((short) 0).putLong(0).putInt(0).array();
        if (!packet.dp(body) || packet.d() != 12782 || packet.getX() != 10
                || packet.getY() != 11 || packet.ejo() != 0)
            throw new AssertionError("Original cAx stage0 contract differs");
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("authority", "Original installed aNl graphics variants + native ANM parser + actual asset EV decoded; bOm.g removal handling traced separately; no synthetic DELETE event");
        result.put("definitions", definitions);
        result.put("assets", observations);
        result.put("actual_asset_delete_events", nativeDeleteEvents);
        result.put("stage0_packet_hex", java.util.HexFormat.of().formatHex(body));
        result.put("stage0_packet_opcode", packet.d());
        result.put("limits", "Does not boot renderer or run a network client. Resource manager removal and stage-to-animation routing are separately traced in original bytecode.");
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result) + "\n");
        System.out.println("resource_definitions=" + definitions.size() + " assets=" + assets.size() + " actual_delete_events=" + nativeDeleteEvents);
        if (nativeDeleteEvents == 0) throw new AssertionError("No actual native asset DELETE event recovered");
        if (!definitions.keySet().equals(wanted)) throw new AssertionError("Missing requested original resource definition");
    }
}
