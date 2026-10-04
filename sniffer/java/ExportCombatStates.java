import java.nio.file.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import com.google.gson.Gson;

/** Offline state definitions and their effect trees, evaluated by the installed client. */
public class ExportCombatStates {
    record Definition(int id, short maximumLevel, boolean tickAtTurnEnd, int[] effects) {}
    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath() + "/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(), new apB<aKX>() {
            public void load(aKX group) { ExportSpellEffectTrees.groups.put(group.d(), group.cku()); }
        });
        apw.bGL().a(new aNw(), new apB<aNw>() {
            public void load(aNw effect) { ExportSpellEffectTrees.expressions.put(effect.aZE(), effect.cyi()); }
        });
        List<Definition> definitions = new ArrayList<>();
        apw.bGL().a(new aNv(), new apB<aNv>() {
            public void load(aNv state) {
                definitions.add(new Definition(state.d(), state.aWa(), state.cxg(),
                    state.cku() == null ? new int[0] : state.cku().clone()));
            }
        });
        fyZ.guX().a(new bbV());
        List<String> rows = new ArrayList<>();
        definitions.sort(Comparator.comparingInt(Definition::id));
        for (Definition definition : definitions) {
            fyW state = fyZ.guX().aax(definition.id());
            if (state == null) throw new IllegalStateException("Missing native state " + definition.id());
            StringBuilder row = new StringBuilder();
            row.append(definition.id()).append('\t').append(definition.maximumLevel())
                .append('\t').append(definition.tickAtTurnEnd()).append('\t')
                .append(ExportSpellEffectTrees.ints(definition.effects()));
            // Preserve roots outside levels 1..200 too (some states use level zero).
            for (int root : definition.effects()) ExportSpellEffectTrees.effect(root);
            for (short level = 1; level <= 200; level++) {
                List<Integer> roots = new ArrayList<>();
                for (eVn effect : state.fH(level)) {
                    roots.add(effect.aZE());
                    ExportSpellEffectTrees.effect(effect.aZE());
                }
                row.append('\t').append(state.aas(level)).append(':')
                    .append(ExportSpellEffectTrees.ints(roots.stream().mapToInt(Integer::intValue).toArray()));
            }
            Map<String,Object> metadata = new LinkedHashMap<>();
            metadata.put("clock_actor", state.guQ() ? "caster" : "target");
            metadata.put("additive", state.cxm());
            metadata.put("replace", state.cxi());
            metadata.put("refresh", state.guV());
            metadata.put("protected", state.guN());
            metadata.put("duration_base", state.tyu);
            metadata.put("duration_per_level", state.tyv);
            // eZk.Ty/bbX use gtL, guH and cxj together to classify retention.
            // A zero turn duration alone does not establish an instant state.
            metadata.put("realtime_duration_base", state.kBv);
            metadata.put("realtime_duration_per_level", state.tyw);
            metadata.put("skip_turn_timer", state.cxj());
            List<Integer> realtimeDurations = new ArrayList<>();
            List<Boolean> timerSkipFlags = new ArrayList<>();
            for (short level = 1; level <= 200; level++) {
                fyW selected = state.cu(level);
                realtimeDurations.add(selected.guH());
                timerSkipFlags.add(selected.cxj());
            }
            metadata.put("native_realtime_durations", realtimeDurations);
            metadata.put("native_skip_turn_timer_by_level", timerSkipFlags);
            List<Map<String,Object>> checks = new ArrayList<>();
            for(short requested:new short[]{0,201,400,32767}) {
                fyW selected=state.cu(requested);
                Map<String,Object> check = new LinkedHashMap<>();
                check.put("requested_level",requested);check.put("level",selected.cmZ());
                check.put("duration",selected.gtL());
                check.put("realtime_duration",selected.guH());
                check.put("skip_turn_timer",selected.cxj());
                List<Integer> roots = new ArrayList<>();
                for(eVn effect:selected.fH(selected.cmZ())) roots.add(effect.aZE());
                check.put("effects",roots);checks.add(check);
            }
            metadata.put("native_level_checks",checks);
            row.append('\t').append("metadata:").append(Base64.getEncoder().encodeToString(
                new Gson().toJson(metadata).getBytes(StandardCharsets.UTF_8)));
            rows.add(row.toString());
        }
        Files.write(Path.of(args[0] + "-states.tsv"), rows);
        Files.write(Path.of(args[0] + "-effects.tsv"), ExportSpellEffectTrees.effects);
        System.out.println("Exported " + rows.size() + " states and " + ExportSpellEffectTrees.effects.size() + " effects");
    }
}
