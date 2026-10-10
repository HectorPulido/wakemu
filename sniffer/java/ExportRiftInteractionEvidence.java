import java.nio.ByteBuffer;
import java.nio.file.*;
import java.util.*;
import java.util.zip.ZipFile;
import com.google.gson.GsonBuilder;

/** Offline native descriptor export and decoder assertions for dimensional rifts. */
public class ExportRiftInteractionEvidence {
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        List<Map<String,Object>> descriptors = new ArrayList<>();
        aLl prototype = new aLl();
        apw.bGL().a(prototype, new apB<aLl>() {
            public void load(aLl value) {
                if (!Set.of(1456,1457,1458,1477).contains(value.d())) return;
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("descriptor_id", value.d());
                List<Map<String,Object>> groups = new ArrayList<>();
                int actionIndex = 0;
                for (aLo group : value.cnY()) {
                    Map<String,Object> g = new LinkedHashMap<>();
                    g.put("id", group.d()); g.put("clx", group.clx());
                    g.put("cod", group.cod()); g.put("coe", group.coe());
                    g.put("cof", group.cof()); g.put("cnd", group.cnd()); g.put("cog", group.cog());
                    List<Map<String,Object>> actions = new ArrayList<>();
                    for (aLn action : group.coh()) {
                        Map<String,Object> a = new LinkedHashMap<>();
                        a.put("wire_action", actionIndex++); a.put("native_id", action.d());
                        a.put("criterion", action.clT()); a.put("raw_cob", action.cob());
                        List<Map<String,Object>> effects = new ArrayList<>();
                        for (aLm effect : action.coc()) {
                            Map<String,Object> e = new LinkedHashMap<>();
                            e.put("action_reference", effect.awM()); e.put("effect_type", effect.cnZ());
                            e.put("criterion", effect.clT()); e.put("parameters", effect.coa());
                            effects.add(e);
                        }
                        a.put("effects", effects); actions.add(a);
                    }
                    g.put("actions", actions); groups.add(g);
                }
                row.put("groups", groups); descriptors.add(row);
            }
        });
        cwF notification = new cwF();
        byte[] wire = ByteBuffer.allocate(16).putInt(123).putInt(456).putInt(-1).putInt(7).array();
        if (!notification.dp(wire) || notification.d() != 13051 || notification.bhe() != 123
                || notification.cbc() != 456 || notification.eId() != -1 || notification.TP() != 7)
            throw new AssertionError("Native wave notification mismatch");
        cpF portal = new cpF();
        portal.nC(123L); portal.cJ((short) 11);
        byte[] portalWire = portal.aWH();
        byte[] expectedPortalBody = ByteBuffer.allocate(12).putLong(123L).putShort((short)11).array();
        // Nx.a adds the native message frame; verify the entire payload suffix.
        if (portalWire.length < 12 || !Arrays.equals(Arrays.copyOfRange(portalWire, portalWire.length - 12, portalWire.length), expectedPortalBody))
            throw new AssertionError("Native portal 12-byte body mismatch");
        if (QT.bjE.beb() != 11 || new cpF().d() != 12870)
            throw new AssertionError("Native portal action mismatch");
        if (descriptors.size() != 4) throw new AssertionError("Missing or ambiguous rift descriptors");
        Map<String,Object> result = new LinkedHashMap<>();
        result.put("binary_table", prototype.bGI()); result.put("descriptors", descriptors);
        result.put("native_wave_notification_assertion", "PASS");
        result.put("native_portal_action_assertion", "PASS");
        Map<String,Object> scripts = new LinkedHashMap<>();
        try (ZipFile archive = new ZipFile("client/contents/scripts/scripts.jar")) {
            Set<Integer> scriptIds = new TreeSet<>();
            for (Map<String,Object> descriptor : descriptors)
                for (Object group : (List<?>) descriptor.get("groups"))
                    for (Object action : (List<?>) ((Map<?,?>) group).get("actions"))
                        for (Object effect : (List<?>) ((Map<?,?>) action).get("effects"))
                            scriptIds.add((Integer)((Map<?,?>) effect).get("action_reference"));
            for (int id : scriptIds) {
                String name = "genericIEActions/" + id + ".lua";
                var entry = archive.getEntry(name);
                scripts.put(name, entry == null ? "NOT_SHIPPED" : new String(archive.getInputStream(entry).readAllBytes(), java.nio.charset.StandardCharsets.UTF_8));
            }
        }
        result.put("installed_lua_scripts", scripts);
        Files.writeString(Path.of(args[0]), new GsonBuilder().setPrettyPrinting().create().toJson(result));
        System.out.println("Exported four rift descriptors; native portal and wave decoder assertions PASS");
    }
}
