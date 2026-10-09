import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import com.google.gson.Gson;
/** Offline structural spell audit. TSV preserves native criteria, without evaluation. */
public class ExportSpellEffectTrees {
    static Map<Integer,int[]> groups=new HashMap<>();
    static Map<Integer,String> expressions=new HashMap<>();
    static Set<Integer> seen=new HashSet<>();
    static List<String> effects=new ArrayList<>(), spells=new ArrayList<>();
    static String ints(int[] values){return Arrays.toString(values).replace(" ","");}
    static Object mask(BitSet value) { return value == null ? null : value.stream().toArray(); }
    static Map<String,Object> metadata(eVn effect) {
        Map<String,Object> result=new LinkedHashMap<>();
        result.put("target_masks", Arrays.asList(mask(effect.aZG()),mask(effect.aZH()),
            mask(effect.aZI()),mask(effect.aZJ()),mask(effect.aZK()),mask(effect.aZL()),mask(effect.aZO())));
        amS selector = effect.aZF();
        if (selector == null) {
            result.put("native_target_selector", null);
        } else {
            Map<String,Object> selectorMetadata = new LinkedHashMap<>();
            selectorMetadata.put("class", selector.getClass().getName());
            if (selector instanceof fcE) {
                try {
                    var field = fcE.class.getDeclaredField("rXt");
                    field.setAccessible(true);
                    selectorMetadata.put("mask", field.getLong(selector));
                } catch (ReflectiveOperationException error) {
                    throw new IllegalStateException(error);
                }
            }
            result.put("native_target_selector", selectorMetadata);
        }
        Map<String,Object> triggers=new LinkedHashMap<>();
        for(String name:new String[]{"rzc","rzd","rze","rzf","rzg","rzh"}) {
            try {
                var field=eVE.class.getDeclaredField(name);field.setAccessible(true);
                Object value=field.get(effect);
                List<Map<String,Object>> records=new ArrayList<>();
                if(value!=null) for(Object item:(List<?>)value) {
                    OY trigger=(OY)item;
                    Map<String,Object> record=new LinkedHashMap<>();
                    record.put("id",trigger.d());record.put("type",trigger.aYb().toString());
                    record.put("native",trigger.toString());record.put("aYc",trigger.aYc());record.put("aYd",trigger.aYd());
                    records.add(record);
                }
                triggers.put(name,records);
            } catch(ReflectiveOperationException error) { throw new IllegalStateException(error); }
        }
        result.put("native_hmi_actions",triggers);
        List<Integer> flags = new ArrayList<>();
        for (eVl flag : eVl.values()) if (effect.a(flag)) flags.add((int)flag.fLK());
        result.put("native_effect_flags", flags);
        result.put("native_execution_mode", (int)effect.aZD());
        result.put("native_definition_class",effect.getClass().getName());
        Map<String,Object> timingDefinition=new LinkedHashMap<>();
        timingDefinition.put("clock_on_caster",effect.aZT());
        timingDefinition.put("clock_on_target",effect.aZU());
        String[] timingFields=effect.getClass()==eVy.class ? new String[]{"ryE","ryF","ryG","ryH","ryI","esr"} : effect.getClass()==eVH.class ? new String[]{"rzv","rzw"} : new String[]{};
        for(String name:timingFields) {
            try {var field=effect.getClass().getDeclaredField(name);field.setAccessible(true);timingDefinition.put(name,field.get(effect));}
            catch(ReflectiveOperationException error) {throw new IllegalStateException(error);}
        }
        result.put("native_timing_definition",timingDefinition);

        result.put("native_localization_enabled", effect.aZQ());
        result.put("application_flag",effect.aZV().toString());
        result.put("removal_flag",effect.aZW().toString());
        try {
            for(String name:new String[]{"ryP","ryQ"}) {
                var field=eVE.class.getDeclaredField(name);field.setAccessible(true);
                result.put(name.equals("ryP") ? "probability_base" : "probability_per_level",field.getFloat(effect));
            }
        } catch(ReflectiveOperationException error) { throw new IllegalStateException(error); }
        if(effect.aZP()!=null) {
            result.put("area_class",effect.aZP().getClass().getName());
            result.put("area_native",effect.aZP().bEm());
            if(effect.aZP() instanceof anE || effect.aZP() instanceof anJ) {
                List<List<Integer>> points=new ArrayList<>();
                for(int[] point:effect.aZP().bEl())points.add(List.of(point[0],point[1]));
                result.put("native_area_points",points);
            }
        }
        return result;
    }
    static void effect(int ref) {
        if(!seen.add(ref))return;
        eVn e=bcA.dcX().AH(ref);
        if(e==null)throw new IllegalStateException("Missing effect "+ref);
        int[] children=groups.getOrDefault(ref,new int[0]);
        StringBuilder row=new StringBuilder();
        row.append(ref).append('\t').append(e.awM()).append('\t').append(e.aZR())
           .append('\t').append(e.fKR()).append('\t').append(e.fKS()).append('\t')
           .append(Base64.getEncoder().encodeToString(expressions.getOrDefault(ref,"").getBytes(StandardCharsets.UTF_8)))
           .append('\t').append(Arrays.toString(e.fKI()).replace(" ",""))
           .append('\t').append(ints(children)).append('\t').append(e.fKJ());
        for(short l=1;l<=200;l++) {
            List<Integer> parameters=new ArrayList<>();
            for(int index=0;index<e.fKJ();index++)parameters.add(e.a(index,l,eVh.rpA));
            row.append('\t').append(e.eg(l)).append(':').append(ints(parameters.stream().mapToInt(Integer::intValue).toArray()));
        }
        row.append('\t').append("metadata:").append(Base64.getEncoder().encodeToString(
            new Gson().toJson(metadata(e)).getBytes(StandardCharsets.UTF_8)));
        effects.add(row.toString());
        for(int child:children)effect(child);
    }
    public static void main(String[] args)throws Exception {
        apw.bGL().dd("jar:file:"+Path.of("client/contents/bdata").toAbsolutePath()+"/%d.jar!/%d.bin");
        apw.bGL().a(new aKX(),new apB<aKX>(){public void load(aKX g){groups.put(g.d(),g.cku());}});
        apw.bGL().a(new aNw(),new apB<aNw>(){public void load(aNw e){expressions.put(e.aZE(),e.cyi());}});
        var field=fyF.class.getDeclaredField("twf");field.setAccessible(true);
        for(String idText:Files.readAllLines(Path.of(args[0]))) {
            int id=Integer.parseInt(idText);bPK s=bPS.elL().IP(id);fyP p=(fyP)field.get(s);
            StringBuilder row=new StringBuilder(idText).append('\t').append(p.cwL()).append('\t').append(p.cwM()).append('\t').append(p.cwU());
            for(short level=1;level<=200;level++) {
                List<Integer> roots=new ArrayList<>();var iterator=s.fG(level);
                while(iterator.hasNext()){int ref=iterator.next().aZE();roots.add(ref);effect(ref);}
                row.append('\t').append(p.gui().Qi(level)).append(',').append(p.guj().Qi(level)).append(':')
                   .append(roots.toString().replace(" ",""));
            }
            spells.add(row.toString());
        }
        Files.write(Path.of(args[1]+"-effects.tsv"),effects);
        Files.write(Path.of(args[1]+"-spells.tsv"),spells);
        System.out.println("Exported "+spells.size()+" native spell trees and "+effects.size()+" effects");
    }
}
