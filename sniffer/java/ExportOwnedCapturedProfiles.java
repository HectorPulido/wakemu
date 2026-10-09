import java.lang.reflect.Method;
import java.nio.file.*;
import java.util.*;
import com.google.gson.*;
/** Export only source-attested class profile seeds and their native books. */
public final class ExportOwnedCapturedProfiles {
    public static void main(String[] args) throws Exception {
        JsonObject input = JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        String schema = input.get("schema").getAsString();
        boolean captureDomain = schema.equals("native-capturable-class-profile-seeds-v1");
        boolean copyDomain = schema.equals("native-class-copy-profile-seeds-v1");
        boolean morphDomain = schema.equals("native-class-morph-profile-seeds-v1");
        boolean dependencyDomain = schema.equals("native-class-summon-dependency-seeds-v1");
        if (!captureDomain && !dependencyDomain && !morphDomain && !copyDomain && !schema.equals("owned-captured-profile-seeds-v1"))
            throw new IllegalArgumentException("Unverified scoped profile seed schema");
        Set<Integer> wanted = new TreeSet<>();
        for (JsonElement seed : input.getAsJsonArray("profile_ids")) wanted.add(seed.getAsInt());
        if (wanted.isEmpty()) throw new IllegalArgumentException("Actual captured profile seeds required");
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() { public void load(aKX raw) {} });
        apw.bGL().a(new aNw(), new apB<aNw>() { public void load(aNw raw) {} });
        if (dependencyDomain || morphDomain) {
            Set<Integer> attested = new TreeSet<>();
            for (JsonElement proof : input.getAsJsonArray("effect_profile_edges")) {
                JsonObject edge = proof.getAsJsonObject();
                eVn effect = bcA.dcX().AH(edge.get("effect_reference").getAsInt());
                int profile = edge.get("profile_id").getAsInt();
                if (effect == null || effect.awM() != (morphDomain ? 933 : 307) || effect.fKJ() < 1)
                    throw new IllegalArgumentException("Missing native307 dependency contract");
                boolean matched = false;
                for (short level = 0; level <= 245; level++)
                    matched |= (morphDomain ? (short) effect.a(0, level, eVh.rpA) : effect.a(0, level, eVh.rpA)) == profile;
                if (!matched) throw new IllegalArgumentException("Unattested native nested summon profile");
                attested.add(profile);
            }
            if (!attested.equals(wanted)) throw new IllegalArgumentException("Incomplete native nested profile proofs");
        }
        if (copyDomain) {
            for (JsonElement proof : input.getAsJsonArray("effect_descriptor_edges")) {
                eVn source = bcA.dcX().AH(proof.getAsJsonObject().get("effect_reference").getAsInt());
                if (source == null || source.awM() != 1002)
                    throw new IllegalArgumentException("Missing original class-copy effect owner");
            }
            Method descriptorMethod = eZw.class.getDeclaredMethod("fRo");
            descriptorMethod.setAccessible(true);
            faB descriptor = (faB) descriptorMethod.invoke(new eZw());
            if (!wanted.equals(Set.of((int) descriptor.aXA())) || descriptor.aXA() != 2382)
                throw new IllegalArgumentException("Unattested original eZw copy constructor profile");
            if (!input.get("reference_contract").getAsString().equals("eZw.fRo -> faB.aV -> faB.aXA"))
                throw new IllegalArgumentException("Missing original copy descriptor seed contract");
        }
        Method convert = bbo.class.getDeclaredMethod("a", aMb.class, short.class);
        convert.setAccessible(true);
        Map<String,Object> output = new TreeMap<>();
        int[] checks = {0};
        apw.bGL().a(new aMb(), new apB<aMb>() {
            public void load(aMb raw) {
                if (!wanted.contains(raw.d())) return;
                try {
                    // Conversion and copies happen inside callback: apw reuses raw.
                    blj profile = (blj) convert.invoke(null, raw, (short) raw.d());
                    if (captureDomain) {
                        boolean can = false, cannot = false;
                        for (int flag : profile.fsp()) { can |= flag == 40; cannot |= flag == 28; }
                        if (!can || cannot) throw new IllegalStateException("Profile is outside native class capture capability domain");
                    }
                    List<Object> abilities = new ArrayList<>();
                    for (ayB<bPK> pair : profile.dvR()) {
                        bPK definition = pair.aIy();
                        int reference = definition.d();
                        for (short level : new short[] {0, 1, 20, 200, 245}) {
                            ArrayList<ayB<bPK>> one = new ArrayList<>(); one.add(pair);
                            bPD book = new bPD(); book.a(one, level, null);
                            bPO action = morphDomain ? new bPO(definition, level, (long) reference, null) : book.js((long) reference);
                            int expected = Math.min(morphDomain || pair.bTV() == -1 ? level : pair.bTV(), definition.Fq());
                            if (action == null || action.LV() != reference || action.cmZ() != expected)
                                throw new AssertionError("Native captured action book mismatch");
                            checks[0]++;
                        }
                        abilities.add(Map.of("reference", reference, "casting_uid", (long) reference,
                            "override_level", pair.bTV(), "maximum_level", definition.Fq()));
                    }
                    Map<String,Object> row = new LinkedHashMap<>();
                    row.put("profile_id", raw.d());
                    row.put("abilities", abilities);
                    row.put("initial_state_triples", profile.cle().clone());
                    row.put("fight_properties", profile.fsp().clone());
                    row.put("world_properties", profile.fsq().clone());
                    row.put("minimum_level", profile.cqN());
                    row.put("descriptor_initial_hp", profile.fsr().b(ffw.sgC, profile.cqN()));
                    row.put("native_profile_name", profile.getName());
                    row.put("authority", copyDomain ? "original eZw.fRo faB.aV/aXA fixed constructor profile; eHI.R preserves native bPD base profile book" : morphDomain ? "native933 slot0 class morphology dependency -> bbo/blj.dvR; exact big.a bPO constructor level/referenceUID verified" : captureDomain ? "native class capture capability CAN40&&!CANNOT28 -> bbo/blj; bPq descriptor minimum-HP; native bPD verified" : dependencyDomain ? "native307 slot0 class-capture dependency -> bbo/blj; native bPD verified" : "actual_owned_roster_seed -> bbo/blj; bPq descriptor minimum-HP source; native bPD verified");
                    output.put(Integer.toString(raw.d()), row);
                } catch (Exception failure) { throw new RuntimeException("Captured profile " + raw.d(), failure); }
            }
        });
        if (output.size() != wanted.size()) throw new IllegalStateException("Missing requested actual captured profile");
        Files.writeString(Path.of(args[1]), new Gson().toJson(Map.of(
            "schema", copyDomain ? "native-class-copy-profiles-v1" : morphDomain ? "native-class-morph-profiles-v1" : "owned-captured-native-profiles-v1", "seed_identity", input,
            "profiles", output, "native_book_checks", checks[0])) + "\n");
        System.out.println("PASS owned_profiles=" + output.size() + " native_book_checks=" + checks[0]);
    }
}
