import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import com.google.gson.Gson;

/** Actual eZl.C descriptor construction for explicitly scoped class effects. */
public class ExportNativeClassSummonDescriptors {
    static class Caster extends bje {
        short level;
        Caster(short level) { this.level = level; }
        public long Sn() { return 7L; }
        public short cmZ() { return level; }
        public byte bcM() { return 0; }
        public aAS bcy() { return aAS.wL(3); }
        public Qf bax() { throw new UnsupportedOperationException("C descriptor probe has no caster Qf"); }
    }
    static void field(Object value, Class<?> owner, String name, Object content) throws Exception {
        Field field = owner.getDeclaredField(name); field.setAccessible(true); field.set(value, content);
    }
    static Object proxy(Class<?> type, String method, Object result) {
        return Proxy.newProxyInstance(type.getClassLoader(), new Class<?>[]{type}, (instance, called, args) -> {
            if (called.getName().equals(method)) return result;
            if (called.getName().equals("toString")) return "ExplicitNativeDescriptorContext";
            throw new UnsupportedOperationException(type.getName() + "." + called.getName());
        });
    }
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() { public void load(aKX record) {} });
        Set<Integer> wantedProfiles = new TreeSet<>();
        for (String text : Files.readAllLines(Path.of(args[1]))) wantedProfiles.add(Integer.parseInt(text));
        eGA<eGH> manager = new eGA<eGH>() {};
        Method convert = bbo.class.getDeclaredMethod("a", aMb.class, short.class); convert.setAccessible(true);
        Method curves = bbo.class.getDeclaredMethod("b", aMb.class); curves.setAccessible(true);
        Field frozen = fff.class.getDeclaredField("sfT"); frozen.setAccessible(true);
        Map<String, Object> profiles = new TreeMap<>();
        apw.bGL().a(new aMb(), new apB<aMb>() { public void load(aMb raw) {
            if (!wantedProfiles.contains(raw.d())) return;
            try {
                blj profile = (blj) convert.invoke(null, raw, (short) raw.d());
                manager.e(profile);
                @SuppressWarnings("unchecked")
                EnumMap<ffw, ayH<Integer, Float>> nativeCurves =
                    (EnumMap<ffw, ayH<Integer, Float>>) curves.invoke(null, raw);
                ffC base = new ffC(raw.cqN());
                for (var entry : nativeCurves.entrySet())
                    base.a(entry.getKey(), entry.getValue().getFirst(), entry.getValue().aIy());
                Map<String, Object> samples = new TreeMap<>();
                for (short level : new short[]{0, 1, 20, 200, 245}) {
                    ffx actual = new ffx(base, level);
                    Map<String, Object> values = new TreeMap<>();
                    for (ffw stat : ffw.values()) {
                        fff value = actual.e(stat);
                        values.put(Integer.toString(stat.aKg() & 255), Map.of(
                            "current", value.aYS(), "minimum", value.aYW(),
                            "maximum", value.aYU(), "frozen", frozen.getBoolean(value)));
                    }
                    samples.put(Short.toString(level), values);
                }
                profiles.put(Integer.toString(raw.d()), Map.of(
                    "minimum_level", profile.cqN(), "fight_properties", profile.fsp(),
                    "world_properties", profile.fsq(), "characteristics_at_levels", samples));
            } catch (Exception error) { throw new RuntimeException("profile " + raw.d(), error); }
        }});
        if (profiles.size() != wantedProfiles.size()) throw new AssertionError("Missing native profiles");
        eGM.a(manager);
        Map<String, Object> effects = new TreeMap<>();
        int checks = 0;
        for (String text : Files.readAllLines(Path.of(args[0]))) {
            int reference = Integer.parseInt(text);
            eVn effect = bcA.dcX().AH(reference);
            if (effect == null || effect.awM() != 307) throw new AssertionError(text);
            List<Integer> flags = new ArrayList<>();
            for (eVl flag : eVl.values()) if (effect.a(flag)) flags.add((int) flag.fLK());
            List<Object> evaluations = new ArrayList<>();
            for (int level = 0; level <= 245; level++) {
                List<Integer> parameters = new ArrayList<>();
                for (int index = 0; index < effect.fKJ(); index++)
                    parameters.add(effect.a(index, (short) level, eVh.rpA));
                eZl runner = new eZl();
                Caster caster = new Caster((short) level);
                field(runner, Qe.class, "bfp", effect);
                field(runner, Qe.class, "bfq", proxy(eVo.class, "cmZ", (short) level));
                field(runner, Qe.class, "bfr", caster);
                field(runner, Qe.class, "bfw", proxy(PN.class, "bae", proxy(PW.class, "baj", 901L)));
                Map<String, Object> result = new LinkedHashMap<>();
                result.put("evaluation_level", level); result.put("parameters", parameters);
                result.put("context", Map.of("caster_uid", 7L, "caster_level", level,
                    "caster_team", 0, "caster_direction", 3, "allocated_uid", 901L,
                    "actual_container_present", true));
                try {
                    runner.C(null);
                    result.put("descriptor_created", runner.rHG != null);
                    result.put("self_controlled", runner.rHI);
                    if (runner.rHG != null) {
                        eHD descriptor = runner.rHG;
                        Map<String, Object> data = new LinkedHashMap<>();
                        data.put("reference", descriptor.dsr()); data.put("level", descriptor.cmZ());
                        data.put("uid", descriptor.fwV()); data.put("team", descriptor.bcM());
                        data.put("direction", descriptor.bcy().dyI);
                        data.put("native_profile_present", descriptor.fwW() != null);
                        result.put("descriptor", data);
                        result.put("timeline", Map.of("anchor", runner.hwX.bhr().toString(),
                            "offset", runner.hwX.bhs(), "caster_uid", runner.hwX.bht()));
                        Map<String, Object> properties = new TreeMap<>();
                        for (byte key : runner.rHH.aZl())
                            properties.put(Byte.toString(key), (int) runner.rHH.aZm().get(key));
                        result.put("native_property_counters", properties);
                    }
                } catch (Throwable error) {
                    result.put("native_exception", error.toString());
                }
                evaluations.add(result); checks++;
            }
            Map<String, Object> record = new LinkedHashMap<>();
            record.put("raw_parameters", effect.fKI()); record.put("flags", flags);
            record.put("minimum_level", effect.fKR()); record.put("maximum_level", effect.fKS());
            record.put("evaluations", evaluations); effects.put(text, record);
        }
        try (java.io.Writer writer = Files.newBufferedWriter(Path.of(args[2]))) {
            new Gson().toJson(Map.of(
                "source", "Original eZl.C with explicit typed container/caster/PW allocation context; no creation or world execution",
                "profiles", profiles, "effects", effects, "native_descriptor_checks", checks), writer);
            writer.write("\n");
        }
        System.out.println("Exported class descriptors effects=" + effects.size() + " profiles=" + profiles.size() + " checks=" + checks);
    }
}
