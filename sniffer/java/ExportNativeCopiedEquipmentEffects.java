import java.nio.file.Path;
import java.util.*;
import com.google.gson.Gson;

/** Offline snapshots of definitions consumed by eGj.PJ -> foA.Wc -> fnR.k. */
public class ExportNativeCopiedEquipmentEffects {
    static Map<String,Object> record(eVn effect, short level,
            Map<Integer,String> criteria, Map<Integer,int[]> groups, Set<Integer> ancestors) {
        int reference = effect.aZE();
        if (!ancestors.add(reference))
            throw new IllegalStateException("Cyclic copied equipment group " + reference);
        Map<String,Object> row = new LinkedHashMap<>();
        row.put("reference", reference);
        row.put("effect_class", effect.awM());
        row.put("variant", effect.aZR());
        row.put("minimum_level", effect.fKR());
        row.put("maximum_level", effect.fKS());
        row.put("parameters", effect.fKI());
        row.put("parameter_count", effect.fKJ());
        row.put("criterion_native", effect.fKT() == null ? null : effect.fKT().toString());
        row.put("criterion_raw", criteria.get(reference));
        row.put("metadata", ExportClassSummonEffectTrees.metadata(effect));
        List<Integer> values = new ArrayList<>();
        for (int index=0; index<effect.fKJ(); index++)
            values.add(effect.a(index, level, eVh.rpA));
        row.put("native_values_at_fresh_item_level", values);
        int[] children = groups.getOrDefault(reference, new int[0]);
        row.put("children", children.clone());
        List<Map<String,Object>> definitions = new ArrayList<>();
        for (int child : children) {
            eVn definition = bcA.dcX().AH(child);
            if (definition == null)
                throw new IllegalStateException("Missing copied equipment child " + child);
            definitions.add(record(definition, level, criteria, groups, new HashSet<>(ancestors)));
        }
        row.put("child_definitions", definitions);
        return row;
    }

    public static void main(String[] args) throws Exception {
        apw.bGL().dd("jar:file:" + Path.of("client/contents/bdata").toAbsolutePath()
            + "/%d.jar!/%d.bin");
        Gson gson = new Gson();
        Set<Integer> identities = new HashSet<>();
        Map<Integer,String> criteria = new HashMap<>();
        Map<Integer,int[]> groups = new HashMap<>();
        apw.bGL().a(new aKX(), new apB<aKX>() {
            public void load(aKX raw) { groups.put(raw.d(), raw.cku().clone()); }
        });
        apw.bGL().a(new aNw(), new apB<aNw>() {
            public void load(aNw raw) { criteria.put(raw.aZE(), raw.cyi()); }
        });
        apw.bGL().a(new aLO(), new apB<aLO>() {
            public void load(aLO raw) {
                // apw reuses its mutable input object: serialize inside load.
                if (!identities.add(raw.d()))
                    throw new IllegalStateException("Duplicate copied equipment identity " + raw.d());
                bJp definition = new bIJ().f(raw);
                if (definition.d() != raw.d())
                    throw new IllegalStateException("Invalid copied equipment identity " + raw.d());
                Map<String,Object> row = new LinkedHashMap<>();
                row.put("reference", definition.d());
                row.put("raw_roots", raw.cku().clone());
                row.put("category", definition.dLn() == null ? null : definition.dLn().aIX());
                row.put("level", definition.cmZ());
                fnR fresh = fnR.a(1L, definition);
                if (fresh == null || fresh.QF() != definition.d() || fresh.ecJ())
                    throw new IllegalStateException("Unexpected fresh fnR source " + raw.d());
                row.put("fresh_container_level", fresh.cmZ());
                row.put("container_type", fresh.aZY());
                List<Map<String,Object>> ordered = new ArrayList<>();
                // A fresh fnR has kal=null, hence iterator delegates to fpC.gjg.
                Iterator<eVn> iterator = fresh.iterator();
                while (iterator.hasNext()) {
                    eVn effect = iterator.next();
                    Map<String,Object> record = record(effect, fresh.cmZ(), criteria, groups, new HashSet<>());
                    record.put("ordinal", ordered.size());
                    record.put("reference", effect.aZE());
                    record.put("effect_class", effect.awM());
                    record.put("variant", effect.aZR());
                    record.put("minimum_level", effect.fKR());
                    record.put("maximum_level", effect.fKS());
                    record.put("parameters", effect.fKI());
                    record.put("parameter_count", effect.fKJ());
                    record.put("criterion_native", effect.fKT() == null ? null : effect.fKT().toString());
                    record.put("criterion_raw", criteria.get(effect.aZE()));
                    record.put("metadata", ExportClassSummonEffectTrees.metadata(effect));
                    List<Integer> values = new ArrayList<>();
                    for (int index = 0; index < effect.fKJ(); index++)
                        values.add(effect.a(index, fresh.cmZ(), eVh.rpA));
                    record.put("native_values_at_fresh_item_level", values);
                    ordered.add(record);
                }
                row.put("ordered_effects", ordered);
                System.out.println(gson.toJson(row));
            }
        });
        System.out.println(gson.toJson(Map.of("export_completed", true,
            "definition_count", identities.size())));
        System.err.println("Exported copied equipment definitions=" + identities.size());
    }
}
